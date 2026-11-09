#!/usr/bin/env python3
"""Map dynamic-core fallback addresses to the guest opcode that caused them.

The instrumented build records every runtime fallback into the dynamic core's
interpreter with the guest CS:EIP of the instruction that could not be
translated. This script resolves those addresses to opcodes using the guest
image's .text section and prints the distribution.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

# префиксы, которые нужно пропустить перед определением опкода
PREFIXES = {0x26, 0x2E, 0x36, 0x3E, 0x64, 0x65, 0x66, 0x67,
            0xF0, 0xF2, 0xF3}

ONE_BYTE_NAMES = {
    0x9E: 'SAHF', 0x9F: 'LAHF', 0x9C: 'PUSHF', 0x9D: 'POPF',
}
TWO_BYTE_NAMES = {
    0x90: 'SETO', 0x91: 'SETNO', 0x92: 'SETB', 0x93: 'SETAE',
    0x94: 'SETE', 0x95: 'SETNE', 0x96: 'SETBE', 0x97: 'SETA',
    0x98: 'SETS', 0x99: 'SETNS', 0x9A: 'SETP', 0x9B: 'SETNP',
    0x9C: 'SETL', 0x9D: 'SETGE', 0x9E: 'SETLE', 0x9F: 'SETG',
    0xA3: 'BT', 0xAB: 'BTS', 0xB3: 'BTR', 0xBB: 'BTS',
    0xBA: 'BT/BTS/BTR/BTC',
    0xBC: 'BSF', 0xBD: 'BSR',
    0x40: 'CMOVO', 0x44: 'CMOVAE', 0x45: 'CMOVNE', 0x42: 'CMOVB',
    0x46: 'CMOVBE', 0x47: 'CMOVA', 0x43: 'CMOVAE/NB',
    0x4C: 'CMOVL', 0x4E: 'CMOVGE', 0x4D: 'CMOVNGE', 0x4F: 'CMOVG',
    0xB0: 'CMPXCHG', 0xB1: 'CMPXCHG',
}


def decode_opcode(code: bytes, off: int) -> tuple[str, int]:
    """Return (mnemonic, instruction length) for the instruction at off."""
    i = off
    while i < len(code) and code[i] in PREFIXES:
        i += 1
    if i >= len(code):
        return ('[truncated]', 1)
    op = code[i]
    if op == 0x0F:
        if i + 1 >= len(code):
            return ('[truncated-0f]', 1)
        sub = code[i + 1]
        name = TWO_BYTE_NAMES.get(sub, f'0F{sub:02X}')
        return (name, 2)
    name = ONE_BYTE_NAMES.get(op, f'{op:02X}')
    return (name, 1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--counters', type=Path, required=True)
    ap.add_argument('--text', type=Path, required=True,
                    help='guest .text blob (file offset 0 == vaddr --text-vaddr)')
    ap.add_argument('--text-vaddr', type=lambda v: int(v, 0), default=0x10A8)
    ap.add_argument('--guest-cs', type=lambda v: int(v, 0), default=0xA7)
    ap.add_argument('--top', type=int, default=25)
    args = ap.parse_args()

    text = args.text.read_bytes()
    by_opcode: Counter = Counter()
    by_addr: list[tuple[int, int, int]] = []
    total = 0
    for line in args.counters.read_text().splitlines():
        kind, _, rest = line.partition(',')
        if kind == 'total':
            total = int(rest)
        elif kind == 'addr':
            key, _, cnt = rest.partition(',')
            value = int(key, 16)
            cs = (value >> 32) & 0xffff
            eip = value & 0xffffffff
            count = int(cnt)
            off = eip - args.text_vaddr
            if cs == args.guest_cs and 0 <= off < len(text):
                name, _ = decode_opcode(text, off)
            else:
                name = f'[cs=0x{cs:04x}]'
            by_opcode[name] += count
            by_addr.append((count, cs, eip))

    print(f'total fallbacks: {total}')
    print(f'guest CS 0x{args.guest_cs:04x}: {sum(v for k, v in by_opcode.items() if not k.startswith("[cs"))}')
    print()
    print(f'{"opcode":22s} {"fallbacks":>10s} {"share":>8s}')
    for name, count in by_opcode.most_common(args.top):
        share = count / total * 100 if total else 0
        print(f'{name:22s} {count:10d} {share:7.2f}%')
    print()
    print('top addresses:')
    for count, cs, eip in sorted(by_addr, reverse=True)[:args.top]:
        off = eip - args.text_vaddr
        name = decode_opcode(text, off)[0] if 0 <= off < len(text) else '?'
        print(f'  cs=0x{cs:04x} eip=0x{eip:05x} {name:20s} {count:9d}')


if __name__ == '__main__':
    main()
