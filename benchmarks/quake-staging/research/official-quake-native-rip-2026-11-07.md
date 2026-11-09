# Real Quake 1.06 native JIT RIP profiles — 2026-11-07

## Outcome

**Two original DOS Quake 1.06 runs finished**: exactly 969 frames each.
This is a real emulated DOS game execution, not a synthetic decoder fixture.
The reproducible test workflow is in
[dosbox-staging PR #5](https://github.com/kaaburgh/dosbox-staging/pull/5).
Passing [GitHub Actions run 42406911144](https://github.com/kaaburgh/dosbox-staging/actions/runs/42406911144);
[derived-only artifact (7-day retention)](https://github.com/kaaburgh/dosbox-staging/actions/runs/42406911144/artifacts/13587699027).
No Quake executable, PAK, native code blobs or raw SIGPROF samples were uploaded.

Environment: GitHub-hosted Ubuntu 24.04 runner with Debian trixie container,
Xvfb, SDL texture software renderer, x86-64 dynamic CPU core,
`OPT_JIT_BLOCK_TRACE=ON`. The source revision that **actually ran**
was `c0f0c557d7dd8f6ce7c0b489d2f0de3b602acec7` (PR #5,
stacked on PRs #1–#4). Compiled DOSBox SHA-256
`8a99ce4072c1d38079adc80164b46de20572f4371de30e4c1f2a2f2ebe5ac908`;
SIGPROF preload SHA-256
`9edffde3bcd0170e5187e9dcd138f8f66d896252aacef6d46b74f223ba255853`.
Original `QUAKE.EXE` SHA-256
`7cdb244122cc607cc6f162524bfcac60f6d11d8ca2ff07473d6cd962311161fb`;
`ID1/PAK0.PAK` SHA-256
`35a9c55e5e5a284a159ad2a62e0e8def23d829561fe2f54eb402dbc0a9a946af`.
Original upstream benchmark ZIP SHA-256 (independently recorded by the earlier
pre-DPMI-handoff run)
`bd928b86e3bd1dc7ffeea88b11e757005be38bc8971aa228ee004d5d23a35a60`.

**Manifest correction:** the successful run's archived
`QUAKE_PROVENANCE.json` mistakenly puts the optional `CWSDPMI.EXE`
hash into `benchmark_archive_sha256` because of variable shadowing in the
harness. This is a **metadata bug**, not an asset mismatch: the archive's
real SHA is the preceding `bd928…35a60` from the earlier run. The
preparer was corrected *after* this successful run in PR #5. Treat this
document as the authoritative corrected provenance until re-execution.

The earlier run [42405912875](https://github.com/kaaburgh/dosbox-staging/actions/runs/42405912875)
built DOSBox and verified the exact executable but timed out before
Quake started (180 seconds). For the successful run, the preparer
also copied the original `CWSDPMI.EXE` from the same benchmark archive.
Its addition coincided with Quake starting successfully, but this is
not an isolated causal test of the DPMI helper requirement.

## Observations

| Period | demo1 frames | FPS (diagnostic only) | main-thread samples | JIT samples | non-JIT samples | selected 9-block samples |
|---|---:|---:|---:|---:|---:|---:|
| 4,700 μs | 969 | 165.8 | 1,078 | 604 | 474 | 89 |
| 5,300 μs | 969 | 168.4 | 947 | 524 | 423 | 72 |
| **Combined** | — | **not an A/B estimate** | **2,025** | **1,128** | **897** | **161** |

All nine specified JIT generation snapshots completed in both runs.
Their provenance and host bounds matched lifecycle events. All 161
selected JIT RIP samples matched an instruction start in the checked
linear x86-64 disassembly. Both SIGPROF recorders exited with `lost=0`.
Zero ambiguous samples does **not** independently establish a
control-flow graph or exclude unobserved side exits.

| Hypothesis selected guest entry blocks | 4,700 μs samples | 5,300 μs samples | Combined |
|---|---:|---:|---:|
| H1 `D_DrawSpans8`: 0x11216, 0x112CC, 0x11343, 0x1143F | 34 | 27 | 61 |
| H2 `D_DrawZSpans`: 0x10D3B | 14 | 11 | 25 |
| H3 surface mip blocks: 0x3E233, 0x3E29A, 0x3E3EF, 0x3E455 | 41 | 34 | 75 |

Across runs, the top selected EIP by sampled count was
`0x10D3B` (25), then `0x3E455` (24), `0x3E29A` (23),
`0x11343` (19), `0x1143F` (17), `0x3E3EF` (17),
`0x112CC` (13), `0x11216` (12), `0x3E233` (11).
These counts are **not shares of full Quake functions**: the snapshots
cover only nine guest basic-block entry points, and 967 other JIT
samples fall outside those selected blocks.

### More useful H1/H2/H3 instruction clues

The original PR #4 instrument classified mnemonic families syntactically.
An inspection of the saved per-instruction CSV suggests a corrected,
more diagnostic breakdown (the family classifier was revised **after
the run**; raw sample offsets/counts are unchanged):

| Selected group | move/LEA | branch | predicate | integer arithmetic | flags (`pushf`) | x87 (`fxch`) | other |
|---|---:|---:|---:|---:|---:|---:|---:|
| H1 | 34 | 9 | 3 | 8 | 4 | 3 | 0 |
| H2 | 17 | 1 | 3 | 4 | 0 | 0 | 0 |
| H3 | 33 | 23 | 10 | 2 | 5 | 0 | 2 |

Repeatable individual native offsets include:
- H3 EIP `0x3E455` native offset `1067` (`pushf`): 5 combined samples,
  and offset `1068` (`lea rsp,[rsp-imm]`): 5.
- H3 EIP `0x3E29A` offset `110` (`jmp`): 4.
- H1 EIP `0x11343` offset `2142` (`pushf`): 4.
- H2 EIP `0x10D3B` offset `318` (`mov`): 5.
- H1 EIP `0x112CC` offset `83` (`fxch`): 3.

These offsets and mnemonics are **observations**, not established
source-level attribution of individual TLB checks, CPU flags, or guest
operations. In particular, `pushf` and `fxch` demonstrate that flag
and x87 machinery is sampled, but are not evidence by themselves that
either lowering is redundant.

**Second parser fix:** the original instruction-output operand
redaction occasionally turned register `r12` into `r1IMM`. That
did not affect native RIP offsets, hashes or mnemonic labels. The
regex was corrected with regression tests in PRs #4 and #5.

## Interpretation / next decision

- The simple premise **"the many static native `call` sites in H1
  execute continuously"** remains unsupported: runtime samples
  are present in moves/addressing, branches, arithmetic, flag paths
  and a few x87 instructions, but an instruction-start sample is not
  a retired-call counter. A time-consuming helper may be in the 897
  main-thread samples **outside JIT**; no reliable caller attribution
  exists yet.
- No evidence warrants changing JIT memory translation yet.
  Prioritize an extended **helper / caller attribution experiment** or
  a trace that can distinguish inline fast TLB lookup from slow-path
  branches in selected native blocks. Record native CFG/instruction
  layout privately and preserve exception/SMC semantics.
- H3 surface-loop candidates have many sampled branches and
  flag-save instructions, but patch-related excess code invalidation
  remains unproven; do not equate its 75 selected samples with
  whole-function runtime share.
- The sample counts are sparse (89/72 selected per run) and
  periodic sampling may be phase-correlated. Repeat with more samples
  and distinct CPU-time periods if the choice between H1 and H3
  hinges on small count differences.
- Neither 165.8 nor 168.4 FPS is a measured optimization result:
  instrumentation remains enabled and the runner is shared.
