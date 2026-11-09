#!/usr/bin/env python3
"""Build a guest function map for DOS Quake 1.06 and aggregate samples per function.

Why this exists
---------------
The hypothesis register (kaaburgh/engineering-lab) measures guest *blocks*.
That unit systematically understates cost: the profiler lands in entry blocks
while the cost mechanism (helper calls) lives in the other blocks of the same
function. This tool segments the guest .text into functions and aggregates
both translated-code samples and helper samples per function.

Method
------
QUAKE.EXE embeds a DJGPP COFF image. Its .text section is disassembled
linearly from the section start; direct call targets (E8/E9 rel32 and
FF /2 indirect calls to known targets) are collected as function candidates.
Each candidate is walked forward along the linear disassembly until the first
`ret`, which bounds the function. Guest EIPs are in the same address space as
the COFF .text vaddr (file_offset = guest_eip - 0x800).

Nothing but guest code addresses and sizes is written to the output; no
proprietary bytes are emitted.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import re
import struct
import subprocess


def find_coff(blob: bytes):
    candidates = []
    for pos in range(len(blob) - 60):
        if blob[pos:pos + 2] != b'\x4c\x01':
            continue
        machine, count, timestamp, ptrsym, nsyms, opthdr, flags = struct.unpack_from(
            '<HHIIIHH', blob, pos)
        if not (1 <= count <= 15 and 0 <= opthdr <= 256
                and pos + 20 + opthdr + 40 * count <= len(blob)):
            continue
        sections = []
        for index in range(count):
            sp = pos + 20 + opthdr + 40 * index
            name, phys, vaddr, size, raw, relptr, lineptr, nrel, nline, secflags = \
                struct.unpack_from('<8sIIIIIIHHI', blob, sp)
            sections.append(dict(name=name.rstrip(b'\0').decode('ascii', 'replace'),
                                 vaddr=vaddr, size=size, file_offset=pos + raw, raw=raw))
        if any(sec['name'] == '.text' and sec['size'] > 10000
               and sec['file_offset'] + sec['size'] <= len(blob)
               for sec in sections):
            candidates.append((pos, sections))
    if len(candidates) != 1:
        raise ValueError(f'Expected one DJGPP COFF image, found {len(candidates)}')
    return candidates[0]


def disassemble(text: bytes, vaddr: int, workdir: Path):
    """Linear disassembly of the section; returns {addr: (mnemonic, operands, raw)}."""
    workdir.mkdir(parents=True, exist_ok=True)
    blob_path = workdir / 'guest-text.bin'
    blob_path.write_bytes(text)
    proc = subprocess.run(
        ['objdump', '-D', '-b', 'binary', '-m', 'i386', '-M', 'intel',
         f'--adjust-vma={vaddr:#x}', str(blob_path)],
        capture_output=True, check=True)
    insns = {}
    head = re.compile(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*\t(.*)$')
    for line in proc.stdout.decode('utf-8', 'replace').splitlines():
        m = head.match(line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        body = m.group(3).strip()
        mm = re.match(r'^([a-z0-9.]+)\s*(.*)$', body)
        if not mm:
            continue
        insns[addr] = (mm.group(1), mm.group(2).strip())
    return insns


CALL_RE = re.compile(r'^(call|jmp)\s+0x([0-9a-f]+)$')


SENTINEL = bytes.fromhex('78563412')     # 0x12345678 runtime-patched displacement


def build_functions(insns, text_start, text_end):
    """Segment .text into code units delimited by `ret`.

    Rationale. Quake 1.06 mixes C code with hand-written assembly
    (WinQuake/d_draw.s, WinQuake/surf8.s). A C function ends with a `ret`;
    an assembly routine group also ends with a `ret`, but may have several
    entry points reached by tail jumps (the renderer's function-pointer
    dispatch stubs). The unit that is meaningful for both is therefore the
    code between two `ret`s, with its entry points recorded separately.

    Every direct call target and every in-section jump target is recorded as
    an entry point of the segment that contains it.
    """
    ordered = sorted(insns)
    jump_re = re.compile(r'^jmp\s+0x([0-9a-f]+)$')
    call_re = re.compile(r'^call\s+0x([0-9a-f]+)$')

    segs = []
    cur = None
    for a in ordered:
        if cur is None:
            cur = a
        mnem, ops = insns[a]
        n = 1
        if mnem == 'ret' and ops.startswith('0x'):
            n = 1 + int(ops, 16)
        if mnem == 'ret':
            segs.append((cur, a + n))
            cur = None
    if cur is not None:
        segs.append((cur, text_end))

    # entry points per segment
    entry = {i: set() for i in range(len(segs))}
    called = {i: set() for i in range(len(segs))}
    starts = [s0 for s0, _ in segs]
    import bisect
    for a in ordered:
        mnem, ops = insns[a]
        m = call_re.match(f'{mnem} {ops}')
        tgt = None
        kind = None
        if m:
            tgt, kind = int(m.group(1), 16), 'call'
        else:
            m = jump_re.match(f'{mnem} {ops}')
            if m:
                tgt, kind = int(m.group(1), 16), 'jmp'
        if tgt is None or not (text_start <= tgt < text_end):
            continue
        i = bisect.bisect_right(starts, a) - 1
        if i < 0:
            continue
        if kind == 'call':
            called[i].add(tgt)
        else:
            entry[i].add(tgt)

    def lookup(addr):
        i = bisect.bisect_right(starts, addr) - 1
        if i < 0:
            return None
        s0, e0 = segs[i]
        return (s0, e0) if s0 <= addr < e0 else None
    return segs, lookup, entry, called


def segment_metrics(insns, raw, segs):
    """Per-segment counts of runtime-patched displacements and x87 instructions.

    The 0x12345678 sentinel is the displacement Quake patches at runtime in
    the software rasterizer; x87 instructions are counted because the
    register's H5 concerns the x87 path.
    """
    sentinel_sites = Counter()
    x87_count = Counter()
    starts = [s0 for s0, _ in segs]
    import bisect
    for i, (s0, e0) in enumerate(segs):
        for off in range(len(raw) - 3):
            pass
    # sentinel sites: byte offsets in .text
    for off in range(len(raw) - 3):
        if raw[off:off + 4] == SENTINEL:
            addr = segs[0][0] + off
            i = bisect.bisect_right(starts, addr) - 1
            if i >= 0 and segs[i][0] <= addr < segs[i][1]:
                sentinel_sites[i] += 1
    for a, (mnem, ops) in insns.items():
        if mnem.startswith('f') and mnem not in ('fs',):
            i = bisect.bisect_right(starts, a) - 1
            if i >= 0 and segs[i][0] <= a < segs[i][1]:
                x87_count[i] += 1
    return sentinel_sites, x87_count


def build_index(funcs):
    import bisect
    starts = [f[0] for f in funcs]
    def lookup(addr):
        i = bisect.bisect_right(starts, addr) - 1
        if i < 0:
            return None
        s, e, ret_end = funcs[i]
        return (s, e, ret_end)
    return lookup


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--exe', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--attribution', type=Path, default=None,
                   help='helper-attribution JSON to aggregate per function')
    args = p.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    blob = args.exe.read_bytes()
    off, sections = find_coff(blob)
    text = next(s for s in sections if s['name'] == '.text')
    raw = blob[text['file_offset']:text['file_offset'] + text['size']]
    insns = disassemble(raw, text['vaddr'], args.out_dir / 'work')
    funcs, lookup, entry, called = build_functions(
        insns, text['vaddr'], text['vaddr'] + text['size'])

    out_csv = args.out_dir / 'quake106-guest-functions.csv'
    with out_csv.open('w', newline='') as fh:
        w = csv.writer(fh)
        sentinel_sites, x87_count = segment_metrics(insns, raw, funcs)
        w.writerow(['guest_start', 'guest_end', 'size_bytes', 'entry_points',
                    'calls_out', 'sentinel_displacements', 'x87_instructions'])
        for idx, (s, e) in enumerate(funcs):
            w.writerow([f'0x{s:05x}', f'0x{e:05x}', e - s,
                        ' '.join(f'0x{x:05x}' for x in sorted(entry[idx])),
                        ' '.join(f'0x{x:05x}' for x in sorted(called[idx])),
                        sentinel_sites.get(idx, 0), x87_count.get(idx, 0)])
    print(f'функций: {len(funcs)}; инструкций разобрано: {len(insns)}; '
          f'.text vaddr={text["vaddr"]:#x} size={text["size"]:#x}')
    print('exe_sha256', hashlib.sha256(blob).hexdigest())

    # sanity check against the register's published identifications
    checks = {
        0x10D3B: 'D_DrawZSpans',
        0x11216: 'D_DrawSpans8 family',
        0x112CC: 'D_DrawSpans8 family',
        0x11343: 'D_DrawSpans8 family',
        0x1143F: 'D_DrawSpans8 family',
        0x3E233: 'R_DrawSurfaceBlock8_mip0',
        0x3E29A: 'R_DrawSurfaceBlock8_mip0',
        0x3E3EF: 'R_DrawSurfaceBlock8_mip1',
        0x3E455: 'R_DrawSurfaceBlock8_mip1',
        0x2F5CF: 'R_RecursiveWorldNode',
        0x306BD: 'R_ClipEdge',
    }
    print('\nсверка с картой реестра:')
    for eip, expect in checks.items():
        f = lookup(eip)
        where = f'0x{f[0]:05x}-0x{f[1]:05x} ({f[1]-f[0]} Б)' if f else 'НЕ НАЙДЕН'
        print(f'  0x{eip:05x}  {expect:28s} -> {where}')

    if args.attribution:
        d = json.loads(args.attribution.read_text())
        total = d['samples_in_window']
        helpers = d['samples_in_helpers_considered']
        jit = d.get('jit_samples_by_guest_block', {})
        by_helper = d['guest_blocks_by_helper_samples']

        def eip_of(key):
            return int(key.split('eip=')[1], 16)

        agg = {}
        for key, cnt in jit.items():
            eip = eip_of(key)
            f = lookup(eip)
            name = f'0x{f[0]:05x}' if f else 'unmapped'
            a = agg.setdefault(name, dict(jit=0, helper=0, blocks=0, helpers={}))
            a['jit'] += cnt
            a['blocks'] += 1
        for key, cnt in by_helper.items():
            eip = eip_of(key)
            f = lookup(eip)
            name = f'0x{f[0]:05x}' if f else 'unmapped'
            a = agg.setdefault(name, dict(jit=0, helper=0, blocks=0, helpers={}))
            n = sum(cnt.values())
            a['helper'] += n
            for h, c in cnt.items():
                a['helpers'][h] = a['helpers'].get(h, 0) + c

        size_of = {f'0x{s:05x}': e - s for s, e in funcs}
        rows = sorted(agg.items(), key=lambda kv: -(kv[1]['jit'] + kv[1]['helper']))
        out2 = args.out_dir / 'quake106-function-attribution.csv'
        with out2.open('w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['guest_function', 'guest_end', 'size_bytes', 'jit_samples',
                        'pct_of_window_jit', 'helper_samples', 'pct_of_window_helper',
                        'pct_of_helper_traffic', 'blocks', 'top_helpers'])
            for name, a in rows:
                top = ';'.join(f'{h}={c}' for h, c in
                               sorted(a['helpers'].items(), key=lambda kv: -kv[1])[:3])
                w.writerow([name, name, size_of.get(name, 0), a['jit'],
                            f'{a["jit"]/total*100:.4f}', a['helper'],
                            f'{a["helper"]/total*100:.4f}',
                            f'{a["helper"]/helpers*100:.4f}', a['blocks'], top])
        print(f'\nфункций с сэмплами: {len(rows)}; итого '
              f'{sum(a["jit"] for _, a in rows)} JIT + '
              f'{sum(a["helper"] for _, a in rows)} helper')
        print('\nтоп-15 по сумме (JIT + helper):')
        for name, a in rows[:15]:
            print(f'  {name} size={size_of.get(name,0):5d}  jit={a["jit"]:5d} '
                  f'({a["jit"]/total*100:5.2f}%)  helper={a["helper"]:4d} '
                  f'({a["helper"]/total*100:5.2f}%)  blocks={a["blocks"]}')
        print('\nтоп-10 по JIT:')
        for name, a in sorted(rows, key=lambda kv: -kv[1]['jit'])[:10]:
            print(f'  {name} jit={a["jit"]:5d} ({a["jit"]/total*100:5.2f}%) '
                  f'helper={a["helper"]:4d} blocks={a["blocks"]}')
        print('\nтоп-10 по helper:')
        for name, a in sorted(rows, key=lambda kv: -kv[1]['helper'])[:10]:
            print(f'  {name} helper={a["helper"]:4d} ({a["helper"]/total*100:5.2f}%) '
                  f'jit={a["jit"]:5d} blocks={a["blocks"]}')


if __name__ == '__main__':
    main()
