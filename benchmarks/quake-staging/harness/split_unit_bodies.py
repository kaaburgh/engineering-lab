#!/usr/bin/env python3
"""Split a guest code unit into bodies at its entry points and attribute cost.

The span rasteriser of Quake 1.06 is a routine group with many entry points
(the renderer calls into it through a function-pointer table). A routine group
is a valid cost unit, but it is not an actionable one: the next step is to
know which body inside the group carries the cost.

For a given code unit this tool partitions the address range at every
recorded entry point, attributes the pooled samples of every guest block to
the body that contains it, and prints a short structural preview of each
body so the body can be named from its machine-code shape.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import re
import subprocess
from pathlib import Path


def load_map(path: Path):
    out = {}
    with path.open(newline='') as fh:
        for row in csv.DictReader(fh):
            out[int(row['guest_start'], 16)] = row
    return out


def load_samples(paths):
    window = 0
    jit = Counter()
    helper = Counter()
    for p in paths:
        d = json.loads(Path(p).read_text())
        window += d['samples_in_window']
        for k, n in d.get('jit_samples_by_guest_block', {}).items():
            jit[k] += n
        for k, c in d.get('guest_blocks_by_helper_samples', {}).items():
            for h, n in c.items():
                helper[k] += n
    return window, jit, helper


def eip_of(key: str) -> int:
    return int(key.split('eip=')[1], 16)


def disassemble(text: bytes, vaddr: int, workdir: Path):
    workdir.mkdir(parents=True, exist_ok=True)
    blob = workdir / 'guest-text.bin'
    blob.write_bytes(text)
    out = subprocess.run(
        ['objdump', '-D', '-b', 'binary', '-m', 'i386', '-M', 'intel',
         f'--adjust-vma={vaddr:#x}', str(blob)],
        capture_output=True, text=True, check=True).stdout
    insns = {}
    for line in out.splitlines():
        m = re.match(r'^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} )+\s*\t(.*)$', line)
        if m:
            mm = re.match(r'^([a-z0-9.]+)\s*(.*)$', m.group(2).strip())
            if mm:
                insns[int(m.group(1), 16)] = (mm.group(1), mm.group(2).strip())
    return insns


def preview(insns, lo, hi, limit=6):
    out = []
    for a in sorted(insns):
        if lo <= a < hi:
            out.append(f'{a:#07x} {insns[a][0]} {insns[a][1]}')
            if len(out) >= limit:
                break
    return ' | '.join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--function-map', type=Path, required=True)
    p.add_argument('--attribution', type=Path, nargs='+', required=True)
    p.add_argument('--unit', required=True, help='guest_start of the code unit')
    p.add_argument('--text-blob', type=Path, required=True,
                   help='raw .text bytes (private)')
    p.add_argument('--text-vaddr', default='0x10a8')
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--top', type=int, default=25)
    a = p.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)

    fmap = load_map(a.function_map)
    unit = int(a.unit, 16)
    row = fmap[unit]
    lo, hi = int(row['guest_start'], 16), int(row['guest_end'], 16)
    eps = sorted({int(x, 16) for x in row['entry_points'].split() if x})
    bounds = [lo] + [e for e in eps if lo < e < hi] + [hi]

    window, jit, helper = load_samples(a.attribution)
    insns = disassemble(a.text_blob.read_bytes(), int(a.text_vaddr, 16),
                        a.out_dir / 'work')

    parts = []
    for i in range(len(bounds) - 1):
        s, e = bounds[i], bounds[i + 1]
        j = sum(v for k, v in jit.items() if s <= eip_of(k) < e)
        h = sum(v for k, v in helper.items() if s <= eip_of(k) < e)
        nb = len([k for k in jit if s <= eip_of(k) < e])
        helpers = Counter()
        for k, v in helper.items():
            if s <= eip_of(k) < e:
                helpers[k] += v
        parts.append(dict(start=s, end=e, size=e - s, jit=j, helper=h,
                          blocks=nb, total=(j + h) / window * 100,
                          helpers=helpers))

    parts.sort(key=lambda d: -d['total'])
    out = a.out_dir / 'bodies.csv'
    with out.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['body_start', 'body_end', 'size_bytes', 'jit_samples',
                    'helper_samples', 'pct_of_window', 'blocks', 'preview'])
        for d in sorted(parts, key=lambda d: d['start']):
            w.writerow([f'0x{d["start"]:05x}', f'0x{d["end"]:05x}', d['size'],
                        d['jit'], d['helper'], f'{d["total"]:.4f}', d['blocks'],
                        preview(insns, d['start'], d['end'])])
    print(f'единица 0x{lo:05x}–0x{hi:05x}, тел: {len(parts)}, окно: {window}')
    print(f'{"тело":<21} {"размер":>6} {"JIT":>6} {"хелп":>5} {"всего%":>7} {"блоков":>6}')
    for d in parts[:a.top]:
        print(f'0x{d["start"]:05x}-0x{d["end"]:05x} {d["size"]:>6} {d["jit"]:>6} '
              f'{d["helper"]:>5} {d["total"]:>7.2f} {d["blocks"]:>6}')
    print('\nструктурный вид top-8:')
    for d in parts[:8]:
        print(f'  0x{d["start"]:05x}: {preview(insns, d["start"], d["end"], 8)}')


if __name__ == '__main__':
    main()
