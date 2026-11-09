# Quake 1.06 JIT hypotheses H1–H5 — verdicts from an instrumented local run (2026-11-09)

## Outcome

Five hypotheses were tested against original DOS Quake 1.06 running on the
fork's **instrumented** dynamic core. The result is a set of **verdicts
against the falsifiers** that the register itself defined.

| Hypothesis | Verdict | Decisive measurement |
|---|---|---|
| **H1** `D_DrawSpans8` | **not falsified — the measurement unit was wrong** | the span region carries **22.8% of all helper traffic** and **18.2% of the main thread in translated code** |
| **H2** `D_DrawZSpans` | **not falsified — the mechanism is visible** | helper traffic is small (1.05% of helpers), but the region holds **1.8% of the window in translated code**, and the native code materialises the flags with `PUSHFQ` before each z-buffer store |
| **H3** `R_DrawSurfaceBlock8_mip*` | **the helper-only view underestimates it** | almost no helper traffic and **zero** invalidations, but the region holds **4.6% of the window in translated code** |
| **H4** transitions/dispatcher | **premise measured** | 7,735 block creations and 185 invalidations (2.39%) per run, 7,669 distinct guest blocks, median **12 guest bytes** against **368 native bytes** (×27.2), dispatcher share 1.99% |
| **H5** x87 + memory helpers | **live, and x87 dominates it** | **7.05%** of the window is x87-attributable (5.17% of it is `mem_readd` called from `FPU_FLD_32`); the dynamic-core decoder gap is the second-largest effect at **1.2–1.7%** |

The hypothesis texts are unchanged. What changed are the verdicts, and two
methodological points that the first version of this report got wrong:

* **A region's cost must be measured in both the translated code and the
  helpers.** Counting only helper samples makes H2 and H3 look negligible
  when they in fact hold 1.8% and 4.6% of the main thread.
* **"x87 = 1.88%" was wrong by an order of magnitude.** 74% of the
  `mem_readd` traffic is called *by* `FPU_FLD_32`, so it belongs to x87,
  not to plain guest memory access.

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

These figures describe **this** host. They are not a property of the guest
or of the fork, and a quieter host (for example one with a lower jitter
floor) would detect smaller effects with the same number of runs. Any
performance claim should therefore be reported together with a fresh A/A
control on the host that produced it.

## What made the attribution possible

The register's open problem was the "blind spot" of helper samples: when
the profiler interrupts the emulator inside `mem_readd` or `FPU_FLD_32`, the
caller is unknown, so H1 and H5 could not be separated.

That was closed **without modifying the emulator**: an extended SIGPROF
preload additionally records eight stack words, and
[harness/attribute_helper_callers.py](harness/attribute_helper_callers.py)
scans them for the return address of the helper call, which maps the
helper sample to the live dynamic-core block and therefore to the guest
CS:EIP that called it. The analyzer now also resolves **nested** helper
calls, i.e. it can tell a `mem_readd` that was issued by `FPU_FLD_32` from
one that the guest issued directly — which is what makes the x87 share
measurable.

| Quantity | Value |
|---|---:|
| Samples inside the timedemo window | 7,520 |
| Samples inside dynamic-core blocks | 3,871 (51.5%) |
| Samples inside emulator helpers | 1,243 (16.5%) |
| Helper samples attributed to a calling guest block | **1,045 (84.07%)** |

The per-block breakdown is in
[quake106-helper-attribution-2026-11-09.csv](quake106-helper-attribution-2026-11-09.csv)
(424 rows, no proprietary data), and the per-region split of translated and
helper time is in
[quake106-region-time-2026-11-09.csv](quake106-region-time-2026-11-09.csv).

Helper traffic:

| Helper | Samples | % of window |
|---|---:|---:|
| `mem_readd` | 525 | 6.98% |
| `mem_writed_checked` | 194 | 2.58% |
| `FPU_FLD_32` | 122 | 1.62% |
| `mem_writed` | 108 | 1.44% |
| `CPU_Core_Normal_Run` | 42 | 0.56% |
| `FPU_GetPRegsTo` | 29 | 0.39% |
| `mem_readw` | 24 | 0.32% |
| `FPU_FST_32` | 19 | 0.25% |
| `FPU_SetPRegsFrom` | 19 | 0.25% |

## Time per guest region

| Region | JIT-block samples | % of window | Helper samples | % of window |
|---|---:|---:|---:|---:|
| `0x10A8–0x12FFF` (span region) | 1,368 | 18.19% | 284 | 3.78% |
| `0x2F000–0x31FFF` (renderer) | 1,060 | 14.10% | 383 | 5.09% |
| `0x3E000–0x3FFFF` (`surf8`) | 346 | **4.60%** | 5 | 0.07% |
| `0x10D00–0x10E00` (Z-span) | 137 | **1.82%** | 13 | 0.17% |
| `0x30600–0x30800` (`R_ClipEdge`) | 96 | 1.28% | 133 | 1.77% |

## H1 — `D_DrawSpans8`: not falsified, and the measurement unit was wrong

H1 predicted that repeated guest 8-bit textured-span loads/stores lower to
excessive TLB checks or native helper calls, with the falsifier "fast path
already inlined and inexpensive; hottest host RIPs land on texture-address
arithmetic not memory handling".

**The falsifier is not met.** The span region holds **22.8% of all helper
traffic** and **18.2% of the main thread in translated code**, and the
leading blocks are not the entry blocks the register listed:

| Guest block | Helper samples | Mix |
|---|---:|---|
| `0x10F4A` | 54 | `mem_readd` 39, `FPU_FLD_32` 15 |
| `0x10CA0` | 28 | `mem_readd` 22, `FPU_FLD_32` 6 |
| `0x110FB` | 22 | `mem_writed` 14, `FPU_FST_32` 8 |
| `0x10572` | 21 | `mem_writed_checked` 21 |
| `0x112CC` | 14 | `mem_readd` 10, `FPU_FLD_32` 4 |

The **methodological consequence** matters more than the verdict: a "hot
entry block" systematically **underestimates** the cost, because the
profiler lands in entry blocks while the cost mechanism — the helper calls
— lives in the *non-entry* blocks of the same functions. H1's hypothesis
text is left unchanged; the register should change its **measurement unit**
from entry blocks to whole functions.

## H2 — `D_DrawZSpans`: the mechanism is visible

The register's falsifier for H2 is "clean straight-line x86-64 without
costly helpers; the dominant cost is the actual writes". On the helper
side the falsifier holds: the region `0x10D00–0x10E00` accounts for 13 of
1,243 helper samples (1.05%), the listed entry block `0x10D3B` itself
invokes helpers twice, and the instruction mix is move-or-address 53%,
arithmetic 20%, branch 19%.

But the region's **own** translated code holds **1.82% of the window**, and
the generated native code of `0x10D3B` shows the mechanism H2 names: the
flags are materialised with a `PUSHFQ` before each z-buffer store, followed
by the TLB check and the store itself.

So H2 is **not falsified**: the flag materialisation it predicts is present
in the generated code. Whether that materialisation is avoidable is the
optimisation question, which stays behind the register's gate.

## H3 — `R_DrawSurfaceBlock8_mip*`: the helper-only view underestimates it

The `surf8` region shows **5 helper samples (0.07% of the window)** and
**zero** invalidations of `surf8` blocks, so neither invalidation churn nor
helper traffic supports the hypothesis' proposed mechanism.

However, the region holds **346 samples in translated code = 4.60% of the
window** — more than the Z-span region and more than the whole `R_ClipEdge`
region. The hypothesis is therefore not "weak", it is **mis-targeted**: the
code is hot, but the hotness is in the translated code itself, not in
helper calls or invalidations. The register should re-scope H3 to ask where
the `surf8` code spends its 4.6%, instead of looking for helper churn.

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

The guest block population does not churn, the per-block expansion factor is
measurable, and H4's falsifier can now be tested directly against the
per-native-RIP histogram.

## H5 — x87 and memory helpers: live, and x87 dominates it

The H5 requirement to "verify actual Quake function for `0x306BD` and
`0x2F5CF`" is closed. `QUAKE.EXE` has no symbol table, so the two blocks
were identified from structural markers against the id Software sources
(`bf4ac42`):

| Guest block | Function | Decisive markers |
|---|---|---|
| `0x2F584` | **`R_RecursiveWorldNode`** | `contents == CONTENTS_SOLID` (−2), `visframe != r_visframecount`, `minmaxs` read as signed `short`, axial-plane type switch, `dot(corner, plane->normal) - plane->dist`, `pfrustum_indexes[4][2][3]` |
| `0x306A4` | **`R_ClipEdge`** | `d0`/`d1` plane distances for both edge endpoints, the `0x7FFFFFFF` "do not cache clipped edges" sentinel, `f = d0 / (d0 - d1)` |

### The x87 share

Resolving nested helper calls changes the picture:

| Attribution | Samples | % of window |
|---|---:|---:|
| `FPU_FLD_32` → `mem_readd` | 389 | 5.17% |
| `FPU_FLD_32` (own samples) | 122 | 1.62% |
| `FPU_FST_32` (own samples) | 19 | 0.25% |
| **x87-attributable total** | **530** | **7.05%** |
| direct guest `mem_readd` | 136 | 1.81% |

74% of the `mem_readd` traffic is x87 operand loading, so the raw 6.98%
`mem_readd` share must not be read as guest memory access cost. The x87
path is the largest single effect measured in this guest.

### The decoder gap

The dynamic core implements only 88 of the 256 two-byte `0F` sub-opcodes;
the `SETcc` family, the bit-test family, `BSF`/`BSR`, `CMOVcc` and the
one-byte `LAHF`/`SAHF` are among the missing ones. A guest instruction that
cannot be translated ends the block with `gen_return(BR_Opcode)` and is run
by the interpreter, with the whole x87 state transferred across the
boundary.

Exact counters from an instrumented build, one headless timedemo window:
The counters come from a local instrumented build that is **not** part of
this PR: a counter is incremented in `case BR_Opcode:` of
`src/cpu/core_dyn_x86.cpp`, keyed by the guest `CS:EIP` of the instruction
that could not be translated, and the table is written out at exit. The
host-side mapping from guest addresses to opcodes is a ten-line lookup in
the guest image's `.text` section.


| Opcode | Fallbacks | Share |
|---|---:|---:|
| `BT` | 1,365,451 | 69.54% |
| `SETE` (`0F 94`) | 296,144 | 15.08% |
| `SAHF` (`0x9E`) | 186,271 | 9.49% |
| `BTR` (`0F B3`) | 32,673 | 1.66% |
| `BTS` (`0F AB`) | 3,981 | 0.20% |
| **total** | **1,963,529** | 100% |

SIGPROF-visible cost of the fallback path: `CPU_Core_Normal_Run` 0.56%,
`FPU_GetPRegsTo` 0.39%, `FPU_SetPRegsFrom` 0.25% — **1.20% of the window
directly attributable**, plus part of the dispatcher (2.26%) and of
`MakeCodePage` (1.52%), so **1.3–1.7% is a credible total**.

The evidence, the guest regression test and the acceptance criteria for
closing the gap are in
[kaaburgh/dosbox-staging PR #11](https://github.com/kaaburgh/dosbox-staging/pull/11).

**Verdict:** H5 stays the only hypothesis whose *proposed mechanism* is
confirmed at full size, and its dominant component is x87 (≈7% of the
window), not the interpreter fallback (≈1.2–1.7%). The x87 part is already
being explored separately in
[PR #10](https://github.com/kaaburgh/dosbox-staging/pull/10).

## Limits

* Every number above comes from an **instrumented** build and from SIGPROF
  hit statistics at a 1100 µs period. They are not an exact time budget and
  must not be mixed with clean FPS figures.
* The fallback counts are exact, but they count transitions, not time.
* The 1.20% attributable fallback cost is a floor.
* The A/A figures in "measurement floor" describe this host only.
* Function names are reconstructions from machine-code structure matched
  against the id Software sources, not symbols; the 1.06-era sources were
  not available for a literal comparison.
* The extended sampler records only eight stack words, so 15.93% of helper
  samples could not be attributed.
* No proprietary Quake file, guest byte snapshot, native code blob, process
  map or raw sample address is stored in this repository.

## Next discriminating steps

1. Re-run the attribution with a **function-level** unit for H1, so that
   the span functions can be compared as wholes.
2. Re-scope H3 from "helper churn" to "where does the `surf8` code spend
   its 4.6%".
3. Design the x87 measurement for H5 on the **nested** attribution, since
   the plain helper table understates it by a factor of four.
4. Close the `BT`/`SETcc`/`SAHF` decoder gap and re-measure the fallback
   share with the regression test from PR #11 as the gate.
5. Only then design changes, and measure them with an A/A control on a
   stable host, given the detection floor measured here.
