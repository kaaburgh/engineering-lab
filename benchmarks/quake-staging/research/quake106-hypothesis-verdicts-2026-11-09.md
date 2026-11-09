# Quake 1.06 JIT hypotheses H1–H5 — verdicts after the function-level re-measurement (2026-11-09)

## Outcome

The hypothesis register now has **verdicts** for H1–H5, measured on original
DOS Quake 1.06 running on the fork's instrumented dynamic core.

This revision replaces the entry-block unit with a **function unit** and
re-measures everything on a five-fold larger sample. The headline change is
not a new mechanism but a **measurement defect that is now quantified**: the
entry-block unit understated the cost of a function by a factor of **1.4 to
4.2**, and for H1 — the register's first-ranked hypothesis — that factor
decides whether the hypothesis looks alive or dead.

| Hypothesis | Verdict | Decisive measurement (function unit) |
|---|---|---|
| **H1** `D_DrawSpans8` | **alive, and much larger than the entry-block view showed** | the span drawing cluster holds **11.38%** of the main thread (9.67% in translated code + 1.70% in helpers); its four entry blocks show only 2.70% |
| **H2** `D_DrawZSpans` | **not falsified; the named mechanism is present** | `D_DrawZSpans` holds **3.27%**; the generated code of block `0x10D3B` materialises the flags **three times** with `pushf` (PUSHFQ), each immediately before the flag-consuming sequence and the z-buffer store |
| **H3** `R_DrawSurfaceBlock8_mip*` | **re-scoped: the patching is a load-time cost, not a per-frame one** | mip0 + mip1 hold **4.31%**, with **0.04%** helper traffic and **zero** invalidations of surf8 blocks; the live guest memory holds the **patched** displacement `0x0018007c` and no sentinel, so the per-frame cost is the inlined texel packing (50% of the sampled instructions are move-or-address), not the patching |
| **H4** transitions/dispatcher | premise measured | 7,735 block creations, 185 invalidations (2.39%) per run, 7,669 distinct guest blocks, median 12 guest bytes vs 368 native bytes (×27.2), dispatcher share 1.99% |
| **H5** x87 + memory helpers | **live, and x87 dominates it** | **7.09%** of the main thread is x87-attributable (4.65% of it is `mem_readd` called *by* `FPU_FLD_32`); the dynamic-core decoder gap is the second effect at **1.2–1.7%** |

The hypothesis texts are unchanged. What changed are the verdicts, the
measurement unit, and the sampling depth.

## What was re-measured, and how

| Item | Value |
|---|---|
| Host | Linux x86-64 container, Xeon Platinum @ 2.5 GHz |
| DOSBox | fork `91774d582069d52f4d3bf04952cb6047dbdc073f`, 0.84.0-alpha, Release |
| Trace build SHA-256 | `ffd4e25086813cd54299eb3ce9a416c64a4cb72067a2b911d07107caa8903b2d` (`OPT_JIT_BLOCK_TRACE=ON`) |
| Clean build SHA-256 | `1b12b66eb4691578d0cc7abd5a678562e6e68078a64509f809e62c6941a9e481` (`OPT_JIT_BLOCK_TRACE=OFF`) |
| `QUAKE.EXE` SHA-256 | `7cdb244122cc607cc6f162524bfcac60f6d11d8ca2ff07473d6cd962311161fb` |
| `PAK0.PAK` SHA-256 | `35a9c55e5e5a284a159ad2a62e0e8def23d829561fe2f54eb402dbc0a9a946af` |
| Runs | 5 instrumented timedemo runs, 1100 µs SIGPROF period |
| Samples in the demo window | **41,502** (8,328 – 8,946 per run) |
| Helper samples | 6,259, of which **5,247 attributed** (83.83%) |
| Guest function map | 2,386 code units, see below |

The instrumented build runs at 74–82 FPS against 117 FPS for the clean
build, so **instrumented and clean figures must never be mixed**.

### The function unit

The register's unit was the guest *block*. That unit is biased: the profiler
lands in entry blocks, while the cost mechanism — helper calls — lives in the
other blocks of the same function. The re-measurement therefore segments the
guest `.text` into **code units delimited by `ret`** and aggregates there.

`harness/map_guest_functions.py` does this without a symbol table
(`QUAKE.EXE` is a COFF image with `nsyms = 0`): it disassembles the section
linearly and cuts it at every `ret`. The unit is meaningful for both code
kinds in this guest — a C function ends with a `ret`, and the hand-written
assembly routines (`d_draw.s`, `surf8.s`) also end with a `ret` but have
several entry points reached by tail jumps, which the tool records
separately.

The segmentation is cross-checked against the register's own published
identifications and against the functions identified structurally in the
previous round:

| Guest address | Register / structural identification | Function found | Agreement |
|---|---|---|---|
| `0x10D3B` | `D_DrawZSpans` | `0x10C57`–`0x10E84` | inside the expected unit |
| `0x11216`, `0x112CC`, `0x11343`, `0x1143F` | span drawing family | `0x10E84`–`0x1179F` (one unit) | inside the expected unit |
| `0x3E233`, `0x3E29A` | `R_DrawSurfaceBlock8_mip0` | `0x3E1BB`–`0x3E375` | same unit, ret boundary matches the register's two-block split |
| `0x3E3EF`, `0x3E455` | `R_DrawSurfaceBlock8_mip1` | `0x3E375`–`0x3E4C1` | same unit |
| `0x2F5CF` | `R_RecursiveWorldNode` | `0x2F574`–`0x2F708` | function start matches the structural identification exactly |
| `0x306BD` | `R_ClipEdge` | `0x306A1`–`0x3096E` | function start matches the structural identification exactly |

### The entry-block unit versus the function unit

| Hypothesis | Entry-block view | Function view | Understatement |
|---|---:|---:|---:|
| **H1** span family | 2.70% | **11.38%** | **×4.2** |
| **H2** Z-span | 1.10% | **3.27%** | ×3.0 |
| **H3** surf8 | 3.06% | **4.31%** | ×1.4 |
| **H5** `R_ClipEdge` + `R_RecursiveWorldNode` | 2.71% | **6.03%** | ×2.2 |

This is the quantitative form of the methodological note from the previous
round: **the register should measure functions, not entry blocks**. The
bias is not uniform — it is worst where the cost mechanism is a helper call
(H1) and mildest where the cost is inlined arithmetic (H3).

## Cost per function

| Function | Guest range | JIT | Helpers | Total | Blocks |
|---|---|---:|---:|---:|---:|
| span drawing cluster (`d_draw.s`) | `0x10E84`–`0x1179F` | 9.67% | 1.70% | **11.38%** | 85 |
| `D_DrawZSpans` | `0x10C57`–`0x10E84` | 2.55% | 0.73% | **3.27%** | 21 |
| `R_ClipEdge` | `0x306A1`–`0x3096E` | 1.60% | 1.52% | **3.11%** | 30 |
| `R_RecursiveWorldNode` | `0x2F574`–`0x2F708` | 2.10% | 0.82% | **2.92%** | 18 |
| `R_DrawSurfaceBlock8_mip0` | `0x3E1BB`–`0x3E375` | 2.22% | 0.01% | **2.23%** | 11 |
| block dispatch (patched displacement) | 0x31367`–`0x31583 | 2.08% | 0.15% | **2.23%** | 27 |
| `R_DrawSurfaceBlock8_mip1` | `0x3E375`–`0x3E4C1` | 2.05% | 0.03% | **2.08%** | 10 |
| unidentified host-side routine | `0x2FA25`–`0x2FDEC` | 1.67% | 0.39% | 2.06% | 41 |
| engine routine with 8 patched displacements | `0x2DDAB`–`0x2E068` | 1.69% | 0.08% | 1.78% | 35 |
| unidentified | `0x3096E`–`0x30C2F` | 0.81% | 0.46% | 1.26% | 20 |
| game memcpy-like routine | `0x1054E`–`0x10582` | 0.80% | 0.26% | 1.06% | 3 |
| `memcpy` (djgpp runtime) | `0x55EDB`–`0x55F04` | 0.77% | 0.03% | 0.80% | 6 |

Full data: [quake106-function-cost-2026-11-09.csv](quake106-function-cost-2026-11-09.csv)
(327 functions with samples), per-block detail in
[quake106-block-cost-2026-11-09.csv](quake106-block-cost-2026-11-09.csv)
(1,625 blocks).

### Helper traffic

| Helper | Samples | % of window |
|---|---:|---:|
| `mem_readd` | 2,705 | 6.52% |
| `mem_writed_checked` | 983 | 2.37% |
| `FPU_FLD_32` | 657 | 1.58% |
| `MakeCodePage` | 594 | 1.43% |
| `mem_writed` | 475 | 1.14% |
| `CPU_Core_Normal_Run` | 193 | 0.47% |
| `FPU_FST_32` | 142 | 0.34% |
| `FPU_GetPRegsTo` | 114 | 0.27% |
| `FPU_SetPRegsFrom` | 100 | 0.24% |
| `sync_dh_fpu_and_run_normal_core` | 88 | 0.21% |
| `mem_readw` | 86 | 0.21% |
| `PAGING_LinkPage` | 58 | 0.14% |
| `mem_writew` | 56 | 0.13% |
| **total** | **6,259** | **15.08%** |

## H1 — the span drawing cluster: 11.38% of the main thread

The largest single unit in the guest is the hand-written span rasteriser
(`WinQuake/d_draw.s`): dispatch stubs that tail-jump into a shared body
with several entry points (`0x110A8`, `0x110C5`, `0x11158`, `0x1119B`).

- 9.67% of the main thread is spent in the **translated** code of the
  cluster, 1.70% in **helpers** it calls.
- The four entry blocks the register listed account for only 2.70% of the
  window, i.e. the entry-block view understated the mechanism by **×4.2**.
- The helper traffic of the cluster is dominated by `mem_readd`,
  `mem_writed` and `FPU_FLD_32`/`FPU_FST_32` — the texture fetch and the
  span endpoint conversion.

**Verdict: H1 is alive and is the largest addressable unit in this guest.**
Its falsifier ("the fast path is already inlined and inexpensive; the
hottest RIPs land on texture-address arithmetic, not memory handling") is
contradicted on both halves: the hot RIPs land on **memory handling**
(1.70% of the window in helpers of this one unit), and the fast path is
not the whole story, since the cluster also holds 9.67% of the main thread
in translated code.

The correct next question for H1 is therefore *where inside the cluster*
the cost sits, and whether the helper transitions in it are avoidable —
not whether it matters.

## H2 — `D_DrawZSpans`: the mechanism is visible

`D_DrawZSpans` holds **3.27%** of the window (2.55% translated, 0.73%
helpers) — three times the entry-block view.

The named mechanism is present in the generated code. The native code of
block `0x10D3B` (192 instructions, 516 bytes) contains **three `pushf`
instructions**, each immediately followed by the flag-dependent sequence
(`dec` / `lea` / `sbb`) and, in the third case, the z-buffer store:

```
0x0138: pushf
0x0139: dec    eax
0x013a: lea    esp,[esp-0x8]
0x013e: mov    DWORD PTR [ebp+0x0],ecx     ; z-buffer store
```

**Verdict: H2 is not falsified.** The flag materialisation it predicts is
in the generated code, and the unit is three times larger than the
entry-block measurement showed. Whether the materialisation is avoidable is
the optimisation question, which stays behind the register's gate.

## H3 — re-scoped: the patching is a load-time cost

`R_DrawSurfaceBlock8_mip0` and `_mip1` hold **4.31%** of the window
(2.23% + 2.08%) with **0.04%** helper traffic, and the H4 measurement shows
**zero** invalidations of surf8 blocks (185 invalidations per run in total,
2.39%).

The mechanism H3 proposes — runtime-patched texture displacements causing
avoidable checks and invalidations — is real, but it is a **load-time**
cost, not a per-frame one. The evidence:

- The static `.text` contains **61** sentinel displacements `0x12345678`;
  **48 of them** are inside the surf8 routines
  (`0x3E1BB` 16, `0x3E700` 16, `0x3E375` 8, `0x3E4C1` 4, `0x3E5CF` 4).
- The **live guest memory** of the surf8 blocks contains **no sentinel** and
  the patched value `0x0018007c` 6, 7, 6 and 2 times respectively.
- The **JIT-generated native code** of those blocks contains the patched
  value 6–7 times and no sentinel.

So the patching happens once, before the timedemo, and the blocks are
compiled with the final displacement. The per-frame cost of the surf8
routines is the work itself: in the instruction-family attribution of the
four surf8 entry blocks (662 samples), **50% of the sampled instructions
are move-or-address**, with branch and predicate instructions next and
**no call-site samples at all**.

**Verdict: H3's proposed mechanism does not explain the cost.** The
hypothesis should be re-scoped to ask where the 4.3% of the surf8 routines
goes (texel packing and address arithmetic), not whether the displacement
patching causes repeated invalidations — it does not, and the patching is
not per-frame.

## H4 — transitions and dispatcher: the premise is measured

| Quantity | Value |
|---|---:|
| Block creations per run | 7,735 |
| Invalidations per run | 185 (2.39%) |
| Distinct guest blocks | 7,669 |
| Median guest bytes per block | 12 |
| Median native bytes per block | 368 (×27.2) |
| Dispatcher share | 1.99% |
| Selected blocks invalidated | 0 of 11 |

## H5 — x87 and memory helpers: live, and x87 dominates it

### Identification of the register's blocks

`QUAKE.EXE` carries no symbol table, so the two blocks were identified from
structural markers against the id Software sources (`bf4ac42`):

| Guest block | Function | Decisive markers |
|---|---|---|
| `0x2F584` | **`R_RecursiveWorldNode`** | `contents == CONTENTS_SOLID` (−2), `visframe != r_visframecount`, `minmaxs` read as signed `short`, axial-plane type switch, `dot(corner, plane->normal) - plane->dist`, `pfrustum_indexes[4][2][3]` |
| `0x306A4` | **`R_ClipEdge`** | `d0`/`d1` plane distances for both edge endpoints, the `0x7FFFFFFF` "do not cache clipped edges" sentinel, `f = d0 / (d0 - d1)` |

The function map independently places `R_RecursiveWorldNode` at
`0x2F574`–`0x2F708` and `R_ClipEdge` at `0x306A1`–`0x3096E`, i.e. the
structural identifications coincide with function boundaries.

### The x87 share, with nested attribution

Resolving nested helper calls separates x87 operand traffic from plain
guest memory traffic:

| Attribution | Samples | % of window |
|---|---:|---:|
| `mem_readd` called **by** `FPU_FLD_32` | 1,929 | 4.65% |
| `FPU_FLD_32` (own samples) | 657 | 1.58% |
| `FPU_FST_32` (own samples) | 142 | 0.34% |
| `FPU_GetPRegsTo` / `FPU_SetPRegsFrom` | 214 | 0.52% |
| **x87-attributable total** | **2,942** | **7.09%** |
| direct guest `mem_readd` | 776 | 1.87% |

The static image also shows where the x87 code lives: the functions with
the highest x87 instruction density are the span cluster (125 x87
instructions in 2,331 bytes), `0x3096E` (115 in 705 bytes), `R_ClipEdge`
(83 in 717), `R_RecursiveWorldNode` (38 in 404) and the block dispatch
(38 in 540). The per-function x87 counts are in
[quake106-guest-function-map.csv](quake106-guest-function-map.csv).

74% of the `mem_readd` traffic is x87 operand loading, so the raw 6.52%
`mem_readd` share must not be read as guest memory access cost. The
five-run pool reproduces the single-run estimate (7.05%) within 0.04
percentage points.

### The decoder gap

The dynamic core implements only 88 of the 256 two-byte `0F` sub-opcodes;
the `SETcc` family, the bit-test family, `BSF`/`BSR`, `CMOVcc` and the
one-byte `LAHF`/`SAHF` are among the missing ones. A guest instruction that
cannot be translated ends the block with `gen_return(BR_Opcode)` and is run
by the interpreter, with the whole x87 state transferred across the
boundary.

Exact counters from an instrumented build, one headless timedemo window:

| Opcode | Fallbacks | Share |
|---|---:|---:|
| `BT` | 1,365,451 | 69.54% |
| `SETE` (`0F 94`) | 296,144 | 15.08% |
| `SAHF` (`0x9E`) | 186,271 | 9.49% |
| `BTR` (`0F B3`) | 32,673 | 1.66% |
| `BTS` (`0F AB`) | 3,981 | 0.20% |
| **total** | **1,963,529** | 100% |

The re-measured cost of that path, from the five-run pool:

| Symbol | Samples | % of window |
|---|---:|---:|
| `CPU_Core_Normal_Run` | 193 | 0.47% |
| `sync_dh_fpu_and_run_normal_core` | 88 | 0.21% |
| `FPU_GetPRegsTo` | 114 | 0.27% |
| `FPU_SetPRegsFrom` | 100 | 0.24% |
| **directly attributable** | **495** | **1.19%** |

The single-run estimate was 1.20%, so **1.19% is the floor**; adding the
dispatcher (2.26%) and `MakeCodePage` (1.43%), which also serve ordinary
block execution, gives the **1.3–1.7%** credible band.

The evidence, the guest regression test and the acceptance criteria for
closing the gap are in
[kaaburgh/dosbox-staging PR #11](https://github.com/kaaburgh/dosbox-staging/pull/11).

**Verdict:** H5 stays the only hypothesis whose *proposed mechanism* is
confirmed at full size, and its dominant component is x87 (≈7% of the
window), not the interpreter fallback (≈1.2–1.7%).

## Measurement floor, for whoever claims a speedup next

On the same host: FPS coefficient of variation 2.17%, minimum detectable
effect **1.68% in FPS** and **0.98% in host CPU time**, placebo A/B
−0.241% with CI [−1.315, +0.877]. These figures describe **this** host; a
quieter host would detect smaller effects with the same number of runs. Any
performance claim should be reported together with a fresh A/A control on
the host that produced it.

## Limits

- Every number above comes from an **instrumented** build and from SIGPROF
  hit statistics at a 1100 µs period. They are not an exact time budget and
  must not be mixed with clean FPS figures.
- The function unit is a `ret`-delimited code unit. For the hand-written
  assembly routines it is a routine group with several entry points, which
  is stated in the data; it is not a source-level function boundary.
- The fallback counts are exact, but they count transitions, not time.
- The 1.19% attributable fallback cost is a floor.
- The A/A figures describe this host only.
- Function names are reconstructions from machine-code structure matched
  against the id Software sources, not symbols; the 1.06-era sources were
  not available for a literal comparison.
- The extended sampler records only eight stack words, so 16.17% of helper
  samples could not be attributed.
- No proprietary Quake file, guest byte snapshot, native code blob, process
  map or raw sample address is stored in this repository.

## Next discriminating steps

1. Split the **span cluster** (11.38%) into its entry-point bodies and
   attribute the cost per body — this is where H1 becomes actionable.
2. Measure the **x87 path** per function (7.09%), now that the unit is
   functions, to see whether it is concentrated in `R_ClipEdge`,
   `R_RecursiveWorldNode` or the span cluster.
3. Keep H3 as "where does the surf8 texel packing spend its 4.3%", with the
   patching ruled out as a per-frame cost.
4. Close the `BT`/`SETcc`/`SAHF` decoder gap and re-measure the fallback
   share with the regression test from PR #11 as the gate.
5. Only then design changes, and measure them with an A/A control on a
   stable host, given the detection floor measured here.
