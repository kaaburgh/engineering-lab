#!/usr/bin/env python3
"""Validate local selected JIT snapshots and generate a two-architecture report.

Raw snapshots and the optional full disassembly may contain proprietary code:
keep them private; do not commit to public GitHub.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from map_quake_coff import find_coff, map_eip

CANDIDATES = {0x10d3b:"D_DrawZSpans / H2",
              0x11216:"D_DrawSpans8 / H1", 0x112cc:"D_DrawSpans8 / H1",
              0x11343:"D_DrawSpans8 / H1", 0x1143f:"D_DrawSpans8 / H1",
              0x3e233:"R_DrawSurfaceBlock8_mip0 / H3",
              0x3e29a:"R_DrawSurfaceBlock8_mip0 / H3",
              0x3e3ef:"R_DrawSurfaceBlock8_mip1 / H3",
              0x3e455:"R_DrawSurfaceBlock8_mip1 / H3"}
FENCE = chr(96) * 3


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def child_file(directory: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).name != name:
        raise ValueError("Unsafe snapshot filename: " + repr(name))
    return directory / name


def disasm(path: Path, machine: str, address: int) -> str:
    process = subprocess.run(
        ["objdump", "-D", "-b", "binary", "-m", machine, "-M", "intel",
         f"--adjust-vma=0x{address:x}", str(path)],
        check=True, text=True, capture_output=True)
    index = process.stdout.find("<.data>:")
    return process.stdout[index:] if index >= 0 else process.stdout


def inspect(meta_path: Path, quake: bytes | None, coff_pos, sections,
            include_disasm: bool) -> tuple[dict, str]:
    m = json.loads(meta_path.read_text())
    expected = ("generation", "guest_eip", "guest_linear_begin", "guest_linear_end",
                "host_begin", "host_end", "host_bytes", "guest_expected_bytes",
                "guest_captured_bytes", "guest_complete", "guest_filename",
                "host_filename")
    for field in expected:
        if field not in m:
            raise ValueError(f"{meta_path}: missing {field}")
    gp = child_file(meta_path.parent, m["guest_filename"])
    hp = child_file(meta_path.parent, m["host_filename"])
    guest, host = gp.read_bytes(), hp.read_bytes()
    gl, gr = int(m["guest_linear_begin"], 0), int(m["guest_linear_end"], 0)
    hl, hr = int(m["host_begin"], 0), int(m["host_end"], 0)
    if (gr - gl != m["guest_expected_bytes"] or len(guest) != m["guest_captured_bytes"]
            or hr - hl != len(host) or len(host) != m["host_bytes"]):
        raise ValueError(f"{meta_path}: interval/blob length mismatch")
    eip = int(m["guest_eip"], 0)
    disk_differences = None
    first_diffs = []
    if quake is not None:
        _, offset = map_eip(eip, coff_pos, sections)
        if offset is not None and offset + len(guest) <= len(quake):
            disk = quake[offset:offset+len(guest)]
            first_diffs = [i for i,(x,y) in enumerate(zip(guest,disk)) if x != y]
            disk_differences = len(first_diffs)
    summary = dict(generation=m["generation"], guest_eip=m["guest_eip"],
                   guest_cs=m.get("guest_cs"), guest_complete=m["guest_complete"],
                   candidate=CANDIDATES.get(eip,"unassigned"),
                   guest_bytes=len(guest), native_bytes=len(host),
                   guest_sha256=sha(guest), native_sha256=sha(host),
                   disk_differences=disk_differences,
                   first_changed_offsets=first_diffs[:32],
                   includes_deferred_slow_paths=True)
    lines = [f"### Generation {m['generation']} — {m.get('guest_cs')}:{m['guest_eip']}",
             f"Candidate: {summary['candidate']} (not proven by snapshot).",
             f"Guest bytes: {len(guest)}, complete={m['guest_complete']}, SHA256={sha(guest)}.",
             f"Native bytes: {len(host)}, SHA256={sha(host)}.",
             f"Guest vs Quake 1.06 on-disk byte differences: {disk_differences}, offsets: {first_diffs[:32]}.",
             "The native block may include deferred helper/exception code."]
    if include_disasm:
        lines += ["", "Guest x86 (snapshot after decode):", "",
                  FENCE+"asm", disasm(gp, "i386", eip).rstrip(), FENCE,
                  "", "Native x86-64 (entire emitted block):", "",
                  FENCE+"asm", disasm(hp, "i386:x86-64", hl).rstrip(), FENCE]
    return summary, "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshots", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--summary", type=Path, required=True)
    p.add_argument("--quake-exe", type=Path)
    p.add_argument("--include-disassembly", action="store_true",
                   help="local/private report only; may contain game machine code")
    args = p.parse_args()
    quake = args.quake_exe.read_bytes() if args.quake_exe else None
    coff, sections = find_coff(quake) if quake is not None else (None, None)
    files = sorted(args.snapshots.glob("*.json"))
    if not files:
        raise ValueError("No selected snapshots found")
    items, sections_markdown = [], []
    for file in files:
        item, section = inspect(file, quake, coff, sections,
                                args.include_disassembly)
        items.append(item)
        sections_markdown.append(section)
    args.summary.write_text(json.dumps(
        dict(schema=1, count=len(items),
             quake_exe_sha256=sha(quake) if quake is not None else None,
             snapshots=items), indent=2) + "\n")
    args.report.write_text(
        "# Selected Quake x86 and DOSBox native JIT blocks\n\n"
        "Block-level correspondence only; not guest-instruction to native-instruction mapping.\n\n"
        + "\n\n".join(sections_markdown) + "\n")
    print(f"Validated {len(items)} snapshots; report: {args.report}")


if __name__ == "__main__":
    main()
