# DOSBox Staging × DOS Quake 1.06 — local correctness research

This directory is the **external experiment harness**, not part of the DOSBox
Staging emulator. The actual source instrumentation and minimal regression
programs are maintained in
[kaaburgh/dosbox-staging#1](https://github.com/kaaburgh/dosbox-staging/pull/1).

## What is verified (2026-11-07)

The original DOS Quake 1.06 was executed on DOSBox Staging 0.84 with
guest-to-host JIT block mapping; the event-based analyzer accepted all
lifecycles. For stronger correctness evidence, standalone DOS tests were
executed on the **local** Linux x86-64 host:

| Check | Evidence |
|---|---|
| Self-modifying code | `SMC.COM`: checksum validated; block invalidations logged |
| Cross-page x86 instruction mutation | `XPG.COM`: 4 KiB boundary modification; old JIT generation invalidated |
| Native JIT cache wraps | `WRAP.COM`: 3 guest executions, all checksum markers valid; 48,062 JIT generations; 39,968 invalidations; **5 real native cache wraps** in a 1 MiB temporary cache |
| Guest-address map | 16,000/16,000 independently known COM guest block EIPs recorded; zero real-mode `CS:EIP` mapping errors |
| No false-positive wrap detection | 8 MiB native cache correctly **rejected** by `--require-reuse`; 1 MiB cache correctly **accepted** (8,535 native start addresses reused) |
| Trace output I/O | Forced `ENOSPC` reported and recording disabled; malformed records rejected |
| Three trace states | 9 local guest executions (SMC, XPG, WRAP × OFF, INACTIVE, ACTIVE), all returned correct guest checksums; no logger file in OFF/INACTIVE |
| Quake mapping to source | 30 demo-only EIPs mapped to original DJGPP COFF offsets; several strong matches to `D_DrawZSpans`, `D_DrawSpans8` and `R_DrawSurfaceBlock8_mip*` |

Detailed, checksummed wraparound results:
[local cache-wrap evidence in the fork](https://github.com/kaaburgh/dosbox-staging/blob/experiments/quake-guest-block-mapping/extras/guest-block-mapping/evidence/p0-local-cache-wrap-2026-11-07.md).

## Repository layout

- `harness/run_wrap_local.py`: run the deterministic DOS correctness test
  **on the current host**, preserving the trace, logs, hashes and markers.
- `harness/semantic_modes_local.py`: compare guest results under compiled-out,
  compiled-in/inactive and active tracing. Nine local test executions passed;
  no trace file was written in the OFF and INACTIVE modes.
- `harness/local_ab.py`: interleaved instrumented/uninstrumented Quake
  timedemo, used only for an estimate of recorder overhead.
- `harness/map_quake_coff.py`: static x86 EIP → COFF `.text` file offsets.
- `research/hotspot-functions.md`: source attribution with explicit confidence
  levels and caveats around runtime self-patching.
- `research/quake106-top30-coff-function-map.csv`: compact per-block reference
  (no game code, binaries or proprietary assets).

Historical build/export workflows and an early CI benchmarking workflow are
preserved as **inactive references** in [`workflows/archive/`](workflows/archive/).
The local correctness and JIT experiments summarized here used recorded Linux
build environments; see the linked evidence and manifests for exact versions,
binary hashes, and the distinction between local and CI measurements.

## Reproduce cache-wrap correctness locally

You need the DOSBox 0.84 fork built with `OPT_JIT_BLOCK_TRACE=ON` and a
temporary `CACHE_TOTAL=(1024*1024*1)`, the `WRAP.COM` generated from
`extras/guest-block-mapping/cache_wrap_stress.asm`, matching runtime
libraries, Xvfb and the fork's trace verifier. Example:

```bash
python3 benchmarks/quake-staging/harness/run_wrap_local.py \
  --dosbox /path/to/dosbox-smallcache \
  --libraries /path/to/matching-runtime-libraries \
  --com /path/to/WRAP.COM \
  --verifier /path/to/fork/extras/guest-block-mapping/verify_wrap_trace.py \
  --cwd /path/to/fork \
  --output /path/to/new-output-directory \
  --passes 3 \
  --require-reuse
```

The output directory must not already exist. The runner requires success
markers from **all three guest executions**, then the verifier independently
checks exact guest EIPs, real-mode linear address mapping, proper
invalidate-before-reuse order and absence of simultaneously-live native
interval overlaps.

For a negative control, build the regular 8 MiB JIT cache and run the same
command with one pass but without `--require-reuse`. Calling the verifier
separately **with** `--require-reuse` against that control trace must fail.

## Performance data is intentionally not a correctness criterion

36 local original Quake 1.06 timedemo runs were completed across tracing
compiled-out, compiled-but-inactive, and actively recording variants. Shared
host performance varied too widely to infer precise profiler overhead.
FPS numbers should not be used to claim an optimization or regression here.
The work is now focused on guest semantics, lifecycle invariants and mapping
correctness. Exact timing comparisons should be performed later on a
controlled dedicated machine.

**Limitations:** The synthetic DOS checks exercise real cache recycling and
important guest instruction paths, not every x86 instruction or hardware
device. The native JIT block mapping intentionally does not yet attribute
time spent in C++ memory/FPU helpers to a particular guest instruction.
