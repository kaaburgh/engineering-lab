# Quake 1.06 JIT hypotheses H1–H5 — verdicts from an instrumented local run (2026-11-09)

## Outcome

Five hypotheses were tested against original DOS Quake 1.06 running on the
fork's **instrumented** dynamic core. The result is not a ranking of
"fastest wins" but a set of **verdicts against the falsifiers** that the
register itself defined:

| Hypothesis | Verdict | Decisive measurement |
|---|---|---|
| **H1** `D_DrawSpans8` | **not falsified — the measurement unit was wrong** | the span region carries **22.8% of all helper traffic** (284 samples, 3.78% of the sampling window), but concentrated in **non-entry** blocks of the same functions |
| **H2** `D_DrawZSpans` | **falsifier met** | the whole `0x10D00–0x10E00` region accounts for **13 samples (1.05% of helper traffic)**; `0x10D3B` itself invokes helpers only twice |
| **H3** `R_DrawSurfaceBlock8_mip*` | **weak** | the whole `0x3E000–0x3FFFF` region accounts for **5 samples (0.07% of the window)** and **no** `surf8` block was ever invalidated |
| **H4** transitions/dispatcher | **premise measured** | 7,735 block creations and 185 invalidations (2.39%) per run, 7,669 distinct guest blocks, median **12 guest bytes** against **368 native bytes** (×27.2), dispatcher share 1.99% |
| **H5** x87 + memory helpers | **the only live hypothesis, and its content changed** | the renderer region carries **30.8% of helper traffic**, but the largest single identified cost is **not x87**: it is an **interpreter fallback caused by a gap in the dynamic core's decoder** |

H5's refinement is the most actionable result of this round and is
documented in [kaaburgh/dosbox-staging PR #11](https://github.com/kaaburgh/dosbox-staging/pull/11):
the `BT`/`BTS`/`BTR`/`BTC` opcodes are **not implemented at all** by the
dynamic core, so the Quake BSP frustum-culling loop is executed by the
interpreter.

## Measurement environment

| Item | Value |
|---|---|
| Host | Linux x86-64 container, Xeon Platinum @ 2.5 GHz |
| DOSBox | fork `91774d582069d52f4d3bf04952cb6047dbdc073f`, 0.84.0-alpha, Release |
| Clean build SHA-256 | `1b12b66eb4691578d0cc7abd5a678562e6e68078a64509f809e62c6941a9e481` (`OPT_JIT_BLOCK_TRACE=OFF`) |
| Trace build SHA-256 | `ffd4e25086813cd54299eb3ce9a416c64a4cb72067a2b911d07107caa8903b2d` (`OPT_JIT_BLOCK_TRACE=ON`) |
| `QUAKE.EXE` SHA-256 | `7cdb244122cc607cc6f162524bfcac60f6d11d8ca2ff07473d6cd962311161fb` |
| `PAK0.PAK` SHA-256 | `35a9c55e5e5a284a159ad2a62e0e8def23d829561fe2f54eb402dbc0a9a946af` |
| Sampler | SIGPROF preload, 1100 µs period, **extended**: also captures 8 words of the interrupted thread's stack |

The instrumented build runs at 87–114 FPS against 117 FPS for the clean
build, so **instrumented and clean figures must never be mixed**.

### The environment's measurement floor

The same host was characterised separately: over 32+32+32+32 and a pooled
64+64 uninstrumented A/A runs the FPS coefficient of variation is 2.17%
and the minimum detectable effect is **1.68% in FPS** and **0.98% in host
CPU time**; a placebo A/B produced −0.241% with a CI of [−1.315, +0.877].
Any future performance claim for this guest must therefore be larger than
roughly 2% on this host, or must be taken on a quieter one.

## What made the attribution possible

The register's open problem was the "blind spot" of helper samples: when
the profiler interrupts the emulator inside `mem_readd` or `FPU_FLD_32`, the
caller is unknown, so H1 and H5 could not be separated.

That was closed **without modifying the emulator**: an extended SIGPROF
preload additionally records eight stack words, and
[harness/attribute_helper_callers.py](harness/attribute_helper_callers.py)
scans them for the return address of the helper call, which maps the
helper sample to the live dynamic-core block and therefore to the guest
CS:EIP that called it.

| Quantity | Value |
|---|---:|
| Samples inside the timedemo window | 7,520 |
| Samples inside dynamic-core blocks | 3,871 (51.5%) |
| Samples inside emulator helpers | 1,243 (16.5%) |
| Helper samples attributed to a calling guest block | **1,045 (84.07%)** |

The per-block breakdown is in
[quake106-helper-attribution-2026-11-09.csv](quake106-helper-attribution-2026-11-09.csv)
(424 rows, no proprietary data).

Helper traffic:

| Helper | Samples | % of window |
|---|---:|---:|
| `mem_readd` | 525 | 6.98% |
| `mem_writed_checked` | 194 | 2.58% |
| `FPU_FLD_32` | 122 | 1.62% |
| `mem_writed` | 108 | 1.44% |
| `CPU_Core_Normal_Run` | 38 | 0.51% |
| `mem_readw` | 24 | 0.32% |
| `FPU_FST_32` | 19 | 0.25% |
| `mem_writew` | 13 | 0.17% |
| `mem_readb_checked` | 2 | 0.03% |

By guest region:

| Region | Samples | % of helper traffic | % of window |
|---|---:|---:|---:|
| `0x2F000–0x31FFF` (renderer, x87-heavy) | 383 | 30.8% | 5.09% |
| `0x10A8–0x12FFF` (span region) | 284 | 22.8% | 3.78% |
| `0x30600–0x30800` (`R_ClipEdge`) | 133 | 10.7% | 1.77% |
| `0x10D00–0x10E00` (`D_DrawZSpans`) | 13 | 1.05% | 0.17% |
| `0x3E000–0x3FFFF` (`surf8` region) | 5 | 0.40% | 0.07% |

## H1 — `D_DrawSpans8`: the falsifier was aimed at the wrong unit

H1 predicted that repeated guest 8-bit textured-span loads/stores lower
to excessive TLB checks or native helper calls, with the falsifier
"fast path already inlined and inexpensive; hottest host RIPs land on
texture-address arithmetic not memory handling".

**The falsifier is not met.** Within the span region the helper traffic is
dominated by real memory-helper calls, and the leading blocks are not the
entry blocks the register listed:

| Guest block | Helper samples | Mix |
|---|---:|---|
| `0x10F4A` | 54 | `mem_readd` 39, `FPU_FLD_32` 15 |
| `0x10CA0` | 28 | `mem_readd` 22, `FPU_FLD_32` 6 |
| `0x110FB` | 22 | `mem_writed` 14, `FPU_FST_32` 8 |
| `0x10572` | 21 | `mem_writed_checked` 21 |
| `0x112CC` | 14 | `mem_readd` 10, `FPU_FLD_32` 4 |

The **methodological consequence** is more important than the verdict: a
"hot entry block" systematically **underestimates** the cost, because the
profiler lands in entry blocks while the cost mechanism — the helper calls
— lives in the *non-entry* blocks of the same functions. H1's hypothesis
text is left unchanged; the register should change its **measurement unit**
from entry blocks to whole functions.

## H2 — `D_DrawZSpans`: falsifier met

The register's falsifier for H2 is "clean straight-line x86-64 without
costly helpers; the dominant cost is the actual writes". The region
`0x10D00–0x10E00` accounts for **13 of 1,243 helper samples (1.05%)**, of
which 11 belong to a single block `0x10D6C`; the listed entry block
`0x10D3B` itself invokes helpers only twice. The instruction mix measured
for the block is move-or-address 53%, arithmetic 20%, branch 19% — exactly
the straight-line profile the falsifier predicts. **H2 is not worth
pursuing** for this guest: the cost is not in helpers and is not
JIT-addressable.

## H3 — `R_DrawSurfaceBlock8_mip*`: weak

The `surf8` region shows **5 helper samples (0.07% of the window)** across
the whole run and **zero** invalidations of `surf8` blocks, so neither
invalidation churn nor helper traffic supports H3. The hypothesis stays
open but weak; the register's own priority ("High") is not justified by
these measurements.

## H4 — transitions and dispatcher: the premise is now measured

| Quantity | Value |
|---|---:|
| Block creations per run | 7,735 |
| Invalidations per run | 185 (2.39%) |
| Distinct guest blocks | 7,669 |
| Median guest bytes per block | 12 |
| Median native bytes per block | 368 (×27.2) |
| Dispatcher share | 1.99% |
| Selected blocks invalidated | 0 of 11 |

The guest block population does not churn, the per-block expansion factor
is measurable, and H4's falsifier ("hot sampled RIPs predominantly within
loop bodies; linked blocks bypass the dispatcher") can now be tested
directly against the per-native-RIP histogram.

## H5 — x87 and memory helpers: live, but the cause is not x87

The H5 requirement to "verify actual Quake function for `0x306BD` and
`0x2F5CF`" is now closed. `QUAKE.EXE` has no symbol table, so the two
blocks were identified from structural markers against the id Software
sources (`bf4ac42`):

| Guest block | Function | Decisive markers |
|---|---|---|
| `0x2F584` | **`R_RecursiveWorldNode`** | `contents == CONTENTS_SOLID` (−2), `visframe != r_visframecount`, `minmaxs` read as signed `short`, axial-plane type switch, `dot(corner, plane->normal) - plane->dist`, `pfrustum_indexes[4][2][3]` |
| `0x306A4` | **`R_ClipEdge`** | `d0`/`d1` plane distances for both edge endpoints, the `0x7FFFFFFF` "do not cache clipped edges" sentinel, `f = d0 / (d0 - d1)` |

Both are in the **client-side software renderer**, and both are x87-heavy
by construction: the BSP culling loop converts `short` corner coordinates
with `fild` and accumulates the plane distance in the x87 stack, while
`R_ClipEdge` computes two plane distances and an interpolation factor in
x87.

That is only part of the story. The **largest single identified cost in
this region is an interpreter fallback**: the dynamic core's decoder
implements 88 of the 256 two-byte `0F` sub-opcodes and the bit-test family
(`0F A3`, `0F AB`, `0F B3`, `0F BB`, `0F BA /4../7`) is **entirely
missing**. A guest bit-test instruction therefore ends the block with
`gen_return(BR_Opcode)` and is executed by `CPU_Core_Normal_Run()`.

Quake uses `BT` and `BTR` inside the per-plane loop of
`R_RecursiveWorldNode`, so a node visit costs several interpreter round
trips. Measured share in the timedemo window: **38 samples (0.51%)** in
`CPU_Core_Normal_Run`, 19 of them at that block. This is a **lower
bound**, because the round trip also breaks the dynamic core's block chain
and that dispatcher cost is invisible as interpreter time.

Evidence, the guest regression test for the instruction family, and the
acceptance criteria for a possible implementation are in
[kaaburgh/dosbox-staging PR #11](https://github.com/kaaburgh/dosbox-staging/pull/11).

**Verdict:** H5 stays the only live hypothesis, but its actionable part is
a **decoder gap**, not FPU state management. The x87 part is real
(`FPU_FLD_32` 122 + `FPU_FST_32` 19 samples, 1.88% of the window) and is
already being explored separately in
[PR #10](https://github.com/kaaburgh/dosbox-staging/pull/10).

## Limits

* Every number above comes from an **instrumented** build and from
  SIGPROF hit statistics at a 1100 µs period. They are not an exact time
  budget and must not be mixed with clean FPS figures.
* The 0.51% interpreter share is a lower bound on the real cost.
* Function names are reconstructions from machine-code structure matched
  against the id Software sources, not symbols; the 1.06-era sources were
  not available for a literal comparison.
* The extended sampler records only eight stack words, so 15.93% of helper
  samples could not be attributed.
* No proprietary Quake file, guest byte snapshot, native code blob, process
  map or raw sample address is stored in this repository.

## Next discriminating steps

1. Re-run the same attribution with a **function-level** unit for H1, so
   that the span functions can be compared as wholes.
2. Close the `BT`/`BTS`/`BTR`/`BTC` decoder gap and re-measure the
   interpreter share with the existing regression test as the gate.
3. Only then design an x87-related change, and measure it with an A/A
   control on a stable host, given the 1.68% FPS detection floor measured
   here.
