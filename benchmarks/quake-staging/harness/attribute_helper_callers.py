#!/usr/bin/env python3
"""Attribute DOSBox helper samples to the guest JIT block that called them.

The fork's SIGPROF sampler records only the interrupted instruction pointer.
When that pointer is inside a JIT-emitted block, the block is known from the
lifecycle trace and the guest block follows. When the pointer is inside a
DOSBox helper (mem_readd, mem_writed_checked, FPU_FLD_32, ...) the caller is
unknown - and that is exactly the attribution the hypothesis register needs to
separate H1 (guest memory translation) from H5 (x87 helpers and state
save/restore).

This analyzer consumes the *extended* sampler stream, which additionally
carries eight words of the interrupted thread's stack. For a helper sample it
scans those words upwards from RSP and takes the first one that lies inside a
JIT block that is live at that moment; that word is the return address of the
helper call, so the caller guest block follows from the lifecycle trace.

The inference is heuristic and is reported as such: an unattributed share
means the stack window did not contain a usable return address.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import struct
import os
import subprocess
import sys

FORK = Path('/workspace/dosbox-pr7')
sys.path.insert(0, str(FORK / 'extras/guest-block-mapping'))

from analyze_trace import events_from_csv, LiveMap  # noqa: E402

REC = struct.Struct('<QQII8Q')
STACK_WORDS = 8

HELPERS = ('mem_readd', 'mem_writed_checked', 'mem_readd_checked', 'mem_writed',
           'mem_readb_checked', 'mem_writeb_checked', 'mem_readw', 'mem_writew',
           'mem_writed_checked_dcx64', 'FPU_FLD_32', 'FPU_FST_32',
           'FPU_GetPRegsTo', 'FPU_SetPRegsFrom', 'CPU_Core_Normal_Run',
           'sync_dh_fpu_and_run_normal_core', 'MakeCodePage', 'PAGING_LinkPage')


def load_symbols(binary: Path) -> list[tuple[int, int, str]]:
    syms = []
    for line in subprocess.check_output(['nm', '-n', '-S', '-C', '--defined-only',
                                         str(binary)], text=True, errors='replace').splitlines():
        parts = line.split(maxsplit=3)
        if len(parts) == 4 and parts[2] in ('t', 'T', 'w', 'W'):
            try:
                syms.append((int(parts[0], 16), int(parts[1], 16), parts[3]))
            except ValueError:
                pass
    return syms


def resolve(syms: list[tuple[int, int, str]], addr: int) -> str:
    import bisect
    if not syms:
        return '[unknown]'
    addrs = [s[0] for s in syms]
    i = bisect.bisect_right(addrs, addr) - 1
    if i >= 0 and addr < syms[i][0] + syms[i][1]:
        return syms[i][2]
    return '[unresolved]'


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace', type=Path, required=True)
    p.add_argument('--samples', type=Path, required=True)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--maps', type=Path, required=True,
                   help='captured /proc/<pid>/maps of the sampled process')
    p.add_argument('--pid', type=int, required=True)
    p.add_argument('--start-ns', type=int, required=True)
    p.add_argument('--end-ns', type=int, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()

    events = events_from_csv(a.trace)
    live = LiveMap()
    syms = load_symbols(a.binary)
    # The DOSBox binary is position independent: a runtime address must be
    # converted to a file offset before it can be resolved against nm output.
    mappings = []
    for line in a.maps.read_text().splitlines():
        parts = line.split(maxsplit=5)
        lo, hi = (int(x, 16) for x in parts[0].split('-'))
        off = int(parts[2], 16)
        path = parts[5] if len(parts) > 5 else '[anonymous]'
        mappings.append((lo, hi, off, path))

    binary_real = os.path.realpath(a.binary)

    def is_binary(path: str) -> bool:
        if path.startswith('/'):
            return os.path.realpath(path) == binary_real
        return False

    def to_file_offset(rip: int) -> int | None:
        for lo, hi, off, path in mappings:
            if lo <= rip < hi and is_binary(path):
                return rip - lo + off
        return None

    data = a.samples.read_bytes()
    if len(data) % REC.size:
        raise SystemExit(f'incomplete extended sample record in {a.samples}')

    cursor = 0
    total = 0
    in_jit = 0
    helper_total = 0
    helper_attributed = 0
    per_guest: dict[tuple[int, int], Counter] = defaultdict(Counter)
    # (guest_cs, guest_eip) -> Counter[(return_offset_in_block, helper)]
    call_sites: dict[tuple[int, int], Counter] = defaultdict(Counter)
    helper_by_symbol: Counter = Counter()
    non_jit_symbols: Counter = Counter()
    unattributed_by_symbol: Counter = Counter()
    stack_words_seen: Counter = Counter()
    jit_per_guest: Counter = Counter()
    helper_by_immediate_caller: Counter = Counter()
    # (guest_cs, guest_eip) -> Counter[(helper, immediate helper caller)]
    per_guest_immediate: dict[tuple[int, int], Counter] = defaultdict(Counter)

    for ts, rip, tid, _pad, *stack in REC.iter_unpack(data):
        if tid != a.pid or not a.start_ns <= ts <= a.end_ns:
            continue
        total += 1
        while cursor < len(events) and events[cursor].timestamp_ns <= ts:
            live.apply(events[cursor])
            cursor += 1

        block = live.locate(rip)
        if block is not None:
            in_jit += 1
            jit_per_guest[(block.guest_cs, block.guest_eip)] += 1
            continue

        file_off = to_file_offset(rip)
        symbol = resolve(syms, file_off) if file_off is not None else '[outside-executable]'
        non_jit_symbols[symbol] += 1
        helper = next((h for h in HELPERS if h in symbol), None)
        if helper is None:
            continue
        helper_total += 1
        helper_by_symbol[helper] += 1

        caller = None
        words = 0
        immediate_caller = None
        for word in stack:
            if not word:
                continue
            candidate = live.locate(word)
            if candidate is not None:
                caller = candidate
                words += 1
                break
            # The interrupted helper may itself have been called from another
            # helper (for example FPU_FLD_32 -> mem_readd). The first stack
            # word inside a known helper identifies that immediate caller.
            if immediate_caller is None:
                off = to_file_offset(word)
                if off is not None:
                    sym = resolve(syms, off)
                    if any(h in sym for h in HELPERS):
                        immediate_caller = sym
        stack_words_seen[words] += 1
        if immediate_caller is not None:
            helper_by_immediate_caller[(helper, immediate_caller)] += 1
        if caller is None:
            unattributed_by_symbol[helper] += 1
            continue
        helper_attributed += 1
        per_guest[(caller.guest_cs, caller.guest_eip)][helper] += 1
        if immediate_caller is not None:
            per_guest_immediate[(caller.guest_cs, caller.guest_eip)][
                (helper, immediate_caller)] += 1
        # The stack word is the return address: it points just past the call
        # instruction, so it identifies the exact native call site.
        call_sites[(caller.guest_cs, caller.guest_eip)][
            (word - caller.host_begin, helper)] += 1

    total_helpers_considered = helper_total
    result = {
        'samples_in_window': total,
        'samples_inside_jit_blocks': in_jit,
        'samples_in_helpers_considered': total_helpers_considered,
        'helper_samples_attributed_to_a_jit_caller': helper_attributed,
        'helper_samples_unattributed': helper_total - helper_attributed,
        'attribution_rate_pct': round(100 * helper_attributed / helper_total, 2)
        if helper_total else None,
        'helper_samples_by_symbol': helper_by_symbol.most_common(),
        'non_jit_samples_by_symbol_top': non_jit_symbols.most_common(15),
        'unattributed_by_symbol': unattributed_by_symbol.most_common(),
        'stack_words_used_histogram': dict(stack_words_seen),
        'call_sites_by_guest_block': {
            f'cs=0x{cs:04x} eip=0x{eip:05x}': [
                {'return_offset': off, 'helper': helper, 'samples': n}
                for (off, helper), n in sorted(counts.items(),
                                               key=lambda kv: (-kv[1], kv[0]))
            ]
            for (cs, eip), counts in sorted(
                call_sites.items(), key=lambda kv: -sum(kv[1].values()))
        },
        'jit_samples_by_guest_block': {
            f'cs=0x{cs:04x} eip=0x{eip:05x}': n
            for (cs, eip), n in jit_per_guest.most_common()
        },
        'helper_samples_by_immediate_caller_per_guest_block': {
            f'cs=0x{cs:04x} eip=0x{eip:05x}': {
                f'{helper} <- {caller}': n
                for (helper, caller), n in cnt.most_common()
            }
            for (cs, eip), cnt in sorted(per_guest_immediate.items())
        },
        'helper_samples_by_immediate_caller': {
            f'{helper} <- {caller}': n
            for (helper, caller), n in helper_by_immediate_caller.most_common()
        },
        'guest_blocks_by_helper_samples': {
            f'cs=0x{cs:04x} eip=0x{eip:05x}': dict(counts)
            for (cs, eip), counts in sorted(
                per_guest.items(), key=lambda kv: -sum(kv[1].values()))
        },
        'note': 'helper attribution uses the first stack word inside a live JIT '
                'block as the return address of the interrupted helper call; '
                'it is a heuristic and the unattributed share is reported',
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
