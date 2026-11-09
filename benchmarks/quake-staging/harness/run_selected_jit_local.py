#!/usr/bin/env python3
"""Execute selected JIT code captures on this Linux host, never in CI.

Uses the fork's existing Quake timedemo runner, with extra environment
variables for optional live guest/native snapshots. Do not publicly commit
the captured guest machine-code bytes or proprietary game assets.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fork", required=True, type=Path)
    p.add_argument("--dosbox", required=True, type=Path)
    p.add_argument("--game", required=True, type=Path)
    p.add_argument("--libraries", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--eips", default="0x10d3b,0x11216,0x112cc,0x11343,0x1143f,0x3e233,0x3e29a,0x3e3ef,0x3e455")
    p.add_argument("--max-snapshots", type=int, default=16)
    a = p.parse_args()
    folder = a.output.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    snapshots = folder / "snapshots"
    snapshots.mkdir(mode=0o700)
    # The existing timedemo runner looks for ID1/QCONSOLE.LOG using
    # uppercase ID1; official zip uses lowercase id1 on case-sensitive Linux.
    guest_source = folder / "game-source"
    shutil.copytree(a.game.resolve(), guest_source)
    lower = guest_source / "id1"
    if lower.exists() and not (guest_source / "ID1").exists():
        lower.rename(guest_source / "ID1")
    runner = a.fork.resolve() / "extras/guest-block-mapping/run_guest_trace.py"
    analyzer_path = a.fork.resolve() / "extras/guest-block-mapping"
    sys.path.insert(0, str(analyzer_path))
    from analyze_trace import classify, events_from_csv, reject_recorder_io_errors
    env = dict(os.environ, DOSBOX_JIT_SNAPSHOT_DIR=str(snapshots),
               DOSBOX_JIT_SNAPSHOT_EIPS=a.eips,
               DOSBOX_JIT_SNAPSHOT_MAX=str(a.max_snapshots))
    command = [sys.executable, str(runner),
               "--dosbox", str(a.dosbox.resolve()),
               "--game", str(guest_source),
               "--out", str(folder / "run"),
               "--sdk-lib-dir", str(a.libraries.resolve()),
               "--renderer", "texture", "--timeout", "100"]
    # DOSBox Staging 0.84 resolves Unicode mapping resources relative to its
    # working directory. Without resources/mapping/*.TXT the mounted DOS
    # directory can appear empty and QUAKE.EXE becomes an "illegal command".
    subprocess.run(command, env=env, cwd=a.fork.resolve(), check=True)
    run = folder / "run"
    reject_recorder_io_errors(run / "dosbox.log")
    events = events_from_csv(run / "jit-blocks.csv")
    summary, _ = classify(events, [])
    known = {e.generation: e.block for e in events if e.block is not None}
    rows = []
    for file in sorted(snapshots.glob("*.json")):
        record = json.loads(file.read_text())
        generation = record["generation"]
        if generation not in known:
            raise RuntimeError(f"Snapshot generation {generation} missing from lifecycle CSV")
        block = known[generation]
        if (record["host_begin"] != hex(block.host_begin)
                or record["host_end"] != hex(block.host_end)):
            raise RuntimeError(f"Snapshot native interval disagrees with lifecycle: {generation}")
        g = snapshots / record["guest_filename"]
        h = snapshots / record["host_filename"]
        if len(g.read_bytes()) != record["guest_captured_bytes"]:
            raise RuntimeError(f"Guest length mismatch: {generation}")
        if len(h.read_bytes()) != record["host_bytes"]:
            raise RuntimeError(f"Native length mismatch: {generation}")
        rows.append(dict(generation=generation, guest_eip=record["guest_eip"],
                         guest_complete=record["guest_complete"],
                         guest_sha256=digest(g), native_sha256=digest(h),
                         guest_bytes=g.stat().st_size, native_bytes=h.stat().st_size))
    if not rows:
        raise RuntimeError("No targeted selected snapshots were produced")
    output = dict(schema=1, dosbox_sha256=digest(a.dosbox),
                  quake_sha256=digest(a.game / "quake.exe"),
                  trace_summary=summary, snapshots=rows)
    (folder / "capture-validation.json").write_text(json.dumps(output, indent=2) + "\n")
    print(f"Validated {len(rows)} generation-bound snapshots locally: {folder}")


if __name__ == "__main__":
    main()
