#!/usr/bin/env python3
"""Pool several instrumented runs and aggregate the cost per guest function.

This is the corrected methodology for the hypothesis register:

  * the unit is a guest *function* (code unit), not a hot entry block;
  * a function's cost is the sum of its translated-code samples AND its
    helper samples - counting only helpers understates H1 and H3;
  * helper samples are attributed through the nested caller chain, so x87
    operand traffic is separated from plain guest memory traffic.

Input: the helper-attribution JSONs of one or more runs + the guest function
map produced by map_guest_functions.py.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path


def load_map(path: Path):
    """guest_start -> (guest_end, size) from the function map CSV."""
    out = {}
    with path.open(newline='') as fh:
        for row in csv.DictReader(fh):
            s = int(row['guest_start'], 16)
            e = int(row['guest_end'], 16)
            out[s] = (e, e - s)
    starts = sorted(out)

    import bisect
    def lookup(addr):
        i = bisect.bisect_right(starts, addr) - 1
        if i < 0:
            return None
        s = starts[i]
        e, size = out[s]
        return (s, e, size) if s <= addr < e else None
    return lookup, out


def eip_of(key: str) -> int:
    return int(key.split('eip=')[1], 16)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--attribution', type=Path, nargs='+', required=True)
    p.add_argument('--function-map', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--labels', type=Path, default=None,
                   help='optional CSV: guest_start,label,source')
    a = p.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)

    lookup, raw_map = load_map(a.function_map)

    labels = {}
    if a.labels:
        with a.labels.open(newline='') as fh:
            for row in csv.DictReader(fh):
                labels[int(row['guest_start'], 16)] = (row['label'], row['source'])

    window = 0
    jit = Counter()
    helper = Counter()
    helpers_by_block = defaultdict(Counter)
    nested = Counter()
    helper_symbols = Counter()
    unattributed = 0
    considered = 0
    attributed = 0
    runs = 0

    for path in a.attribution:
        d = json.loads(path.read_text())
        runs += 1
        window += d['samples_in_window']
        considered += d['samples_in_helpers_considered']
        attributed += d['helper_samples_attributed_to_a_jit_caller']
        unattributed += d['helper_samples_unattributed']
        for sym, n in d.get('helper_samples_by_symbol', []):
            helper_symbols[sym] += n
        for key, n in d.get('jit_samples_by_guest_block', {}).items():
            jit[key] += n
        for key, cnt in d.get('guest_blocks_by_helper_samples', {}).items():
            helpers_by_block[key].update(cnt)
        for key, n in d.get('helper_samples_by_immediate_caller', {}).items():
            nested[key] += n

    # per function
    agg = {}
    def bucket(eip):
        f = lookup(eip)
        name = f'0x{f[0]:05x}' if f else 'unmapped'
        return agg.setdefault(name, dict(jit=0, helper=0, blocks=0, helpers=Counter()))

    for key, n in jit.items():
        b = bucket(eip_of(key))
        b['jit'] += n
        b['blocks'] += 1
    for key, cnt in helpers_by_block.items():
        b = bucket(eip_of(key))
        b['helper'] += sum(cnt.values())
        b['helpers'].update(cnt)

    rows = []
    for name, b in agg.items():
        s = int(name, 16) if name != 'unmapped' else 0
        size = raw_map.get(s, (0, 0))[1]
        label, source = labels.get(s, ('', ''))
        rows.append(dict(
            guest_function=name, label=label, source=source, size_bytes=size,
            jit_samples=b['jit'], helper_samples=b['helper'], blocks=b['blocks'],
            pct_jit=b['jit'] / window * 100,
            pct_helper=b['helper'] / window * 100,
            pct_helper_traffic=b['helper'] / considered * 100 if considered else 0,
            total_pct=(b['jit'] + b['helper']) / window * 100,
            top_helpers=';'.join(f'{h}={c}' for h, c in
                                 b['helpers'].most_common(4))))
    rows.sort(key=lambda r: -r['total_pct'])

    out = a.out_dir / 'quake106-function-cost.csv'
    with out.open('w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f'{v:.4f}' if isinstance(v, float) else v)
                        for k, v in r.items()})

    summary = dict(
        runs=runs, samples_in_window=window,
        helper_samples_considered=considered,
        helper_samples_attributed=attributed,
        helper_samples_unattributed=unattributed,
        attribution_rate_pct=round(attributed / considered * 100, 2) if considered else 0,
        jit_samples_in_blocks=sum(jit.values()),
        functions_with_samples=len(rows),
        helper_symbols=helper_symbols.most_common(),
        nested_callers=nested.most_common(),
    )
    (a.out_dir / 'pooled-summary.json').write_text(json.dumps(summary, indent=2))

    print(f'прогонов: {runs}; сэмплов в окне: {window}; '
          f'атрибуция хелперов: {attributed}/{considered} '
          f'({summary["attribution_rate_pct"]}%)')
    print(f'функций с сэмплами: {len(rows)}\n')
    print(f'{"функция":<10} {"метка":<34} {"размер":>6} {"JIT%":>7} {"хелп%":>7} {"всего%":>7} {"блоков":>7}')
    for r in rows[:25]:
        print(f'{r["guest_function"]:<10} {r["label"][:33]:<34} {r["size_bytes"]:>6} '
              f'{r["pct_jit"]:>7.2f} {r["pct_helper"]:>7.2f} {r["total_pct"]:>7.2f} '
              f'{r["blocks"]:>7}')
    print('\nвложенные вызовы (x87):')
    for k, v in summary['nested_callers'][:8]:
        print(f'  {k}: {v} ({v/window*100:.2f}% окна)')


if __name__ == '__main__':
    main()
