#!/usr/bin/env python3
"""Instruction-family profile of the JIT-generated native code of selected blocks.

The sampled instruction families (PR #4) describe where the *profiler* landed.
This tool describes the whole generated block instead: every instruction of
the snapshot is classified with the same taxonomy, so the mix is a property of
the generated code rather than of the sample.

It also counts the flags-or-state instructions (pushf / setcc / lahf / sahf),
the call sites, the x87 instructions and the runtime-patched displacement
(0x0018007c) that survives into the native code.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess

FAMILIES = (
    ('flags-or-state', ('pushf', 'popf', 'lahf', 'sahf', 'set')),
    ('x87', ('f',)),
    ('call-site', ('call',)),
    ('branch', ('j', 'loop')),
    ('return', ('ret', 'iret')),
    ('move-or-address', ('mov', 'lea', 'cmov', 'push', 'pop')),
    ('predicate', ('cmp', 'test', 'bt')),
    ('arithmetic-or-bitwise', ('add', 'sub', 'adc', 'sbb', 'shr', 'shl', 'sar',
                               'and', 'or', 'xor', 'inc', 'dec', 'imul', 'mul',
                               'div', 'idiv')),
)


def classify(mnemonic: str) -> str:
    m = mnemonic.lower()
    if m.startswith(('pushf', 'popf', 'lahf', 'sahf', 'set')):
        return 'flags-or-state'
    if m.startswith('f'):
        return 'x87'
    if m.startswith('call'):
        return 'call-site'
    if m.startswith('j') or m.startswith('loop'):
        return 'branch'
    if m.startswith(('ret', 'iret')):
        return 'return'
    if m.startswith(('mov', 'lea', 'cmov', 'push', 'pop')):
        return 'move-or-address'
    if m.startswith(('cmp', 'test', 'bt')):
        return 'predicate'
    if m.startswith(('add', 'sub', 'adc', 'sbb', 'shr', 'shl', 'sar', 'and',
                     'or', 'xor', 'inc', 'dec', 'imul', 'mul', 'div', 'idiv')):
        return 'arithmetic-or-bitwise'
    return 'other'


def disassemble(path: Path):
    out = subprocess.run(
        ['objdump', '-D', '-b', 'binary', '-m', 'i386', '-M', 'intel', str(path)],
        capture_output=True, text=True, check=True).stdout
    insns = []
    for line in out.splitlines():
        m = re.match(r'^\s*([0-9a-f]+):\s+(?:[0-9a-f]{2} )+\s*\t(.*)$', line)
        if m:
            mm = re.match(r'^([a-z0-9.]+)\s*(.*)$', m.group(2).strip())
            if mm:
                insns.append((int(m.group(1), 16), mm.group(1), mm.group(2).strip()))
    return insns


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--snapshot-dir', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for j in sorted(a.snapshot_dir.glob('*.json')):
        d = json.loads(j.read_text())
        host = a.snapshot_dir / d['host_filename']
        guest = a.snapshot_dir / d['guest_filename']
        insns = disassemble(host)
        fam = Counter(classify(m) for _, m, _ in insns)
        hb = host.read_bytes()
        gb = guest.read_bytes()
        rows.append(dict(
            guest_eip=int(str(d['guest_eip']), 16),
            guest_bytes=len(gb),
            native_bytes=len(hb),
            native_instructions=len(insns),
            pushf=sum(1 for _, m, _ in insns if m.startswith('pushf')),
            setcc=sum(1 for _, m, _ in insns if m.startswith('set')),
            call_sites=fam.get('call-site', 0),
            x87=fam.get('x87', 0),
            patched_disp_host=sum(1 for i in range(len(hb) - 3)
                                  if hb[i:i + 4] == bytes.fromhex('7c001800')),
            sentinel_host=sum(1 for i in range(len(hb) - 3)
                              if hb[i:i + 4] == bytes.fromhex('78563412')),
            patched_disp_guest=sum(1 for i in range(len(gb) - 3)
                                   if gb[i:i + 4] == bytes.fromhex('7c001800')),
            sentinel_guest=sum(1 for i in range(len(gb) - 3)
                               if gb[i:i + 4] == bytes.fromhex('78563412')),
            families=fam,
        ))

    out = a.out_dir / 'native-block-profile.json'
    out.write_text(json.dumps(rows, indent=2, default=lambda o: dict(o)))

    hdr = ('guest_eip', 'native_B', 'insns', 'move%', 'arith%', 'branch%',
           'pred%', 'flags%', 'x87%', 'call', 'pushf', 'pat_disp')
    print(' '.join(f'{h:>10}' for h in hdr))
    for r in sorted(rows, key=lambda r: r['guest_eip']):
        n = max(1, r['native_instructions'])
        f = r['families']
        print(f'{r["guest_eip"]:>10x} {r["native_bytes"]:>10} {n:>10} '
              f'{100*f.get("move-or-address",0)/n:>9.1f}% '
              f'{100*f.get("arithmetic-or-bitwise",0)/n:>9.1f}% '
              f'{100*f.get("branch",0)/n:>9.1f}% '
              f'{100*f.get("predicate",0)/n:>9.1f}% '
              f'{100*f.get("flags-or-state",0)/n:>9.1f}% '
              f'{100*f.get("x87",0)/n:>9.1f}% '
              f'{r["call_sites"]:>10} {r["pushf"]:>10} {r["patched_disp_host"]:>10}')


if __name__ == '__main__':
    main()
