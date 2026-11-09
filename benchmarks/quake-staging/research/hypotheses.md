# DOSBox Staging x86 JIT — hypotheses driven by DOS Quake 1.06

**Status:** hypotheses to test, **not findings of inefficiency**. Research environment: DOSBox Staging 0.84.0-alpha, fork [kaaburgh/dosbox-staging#1](https://github.com/kaaburgh/dosbox-staging/pull/1), unmodified DOS Quake 1.06 `QUAKE.EXE` SHA-256 `7cdb244122cc607cc6f162524bfcac60f6d11d8ca2ff07473d6cd962311161fb`.

## Already established

Guest block mapping correlates sampled Linux host RIP with guest Quake CS:EIP using generation-aware JIT lifecycle timestamps. Multiple 0.83/0.84 profiles show reproducibly hot guest regions; see [hotspot-functions.md](hotspot-functions.md) and [Top-30 block/COFF map](quake106-top30-coff-function-map.csv). **Counts below are sampled entry blocks, not whole-function CPU shares**. Their order and counts are subject to sampling variance. Prior source attributions are high-confidence *for the named algorithm families*, but exact binary function boundaries remain to be verified.

The DOS Quake 1.06 executable has an embedded DJGPP COFF `.text` section and contains assembly sequences matching later id Software source. **Quake dynamically patches some displacement fields**, notably in `surf8.s`. Never assume on-disk x86 bytes are identical to instructions decoded by DOSBox at runtime.

## Research priority and falsifiable predictions

| ID | Candidate hotspot | Hypothesis / possible cost | Evidence needed | Falsifier or weaker result | Risk / relevance |
|---|---|---|---|---|---|
| H1 | `D_DrawSpans8`: 0x11216, 0x112CC, 0x11343, 0x1143F | Repeated guest 8-bit textured-span loads/stores lower to excessive TLB checks and/or native helper calls rather than fast inlined accesses | Guest bytes **captured from live guest memory**; actual native JIT disassembly; call targets and instruction counts; side exits; compare against decoder `dyn_read_byte`, `dyn_write_byte` and `X86_INLINED_MEMACCESS` | Fast path already inlined and inexpensive; hottest host RIPs land on texture-address arithmetic not memory handling | High priority: repeated hot blocks, potentially general across games |
| H2 | `D_DrawZSpans`: 0x10D3B | Sequence of integer shifts, masks, ORs and DWORD z-buffer writes has avoidable register shuffles, flag materialization, memory-helper transitions or redundant guest-address calculations | Trace generated native block (including slow paths); map guest instructions to host ranges; disassemble branch exits; count calls and JIT instructions per guest iteration | Clean straight-line x86-64 without costly helpers or redundant work; dominant cost is actual writes / cache misses | High priority: distinctive guest ASM loop and 20 sampled entry-block RIPs |
| H3 | `R_DrawSurfaceBlock8_mip0/mip1`: 0x3E233 / 0x3E29A / 0x3E3EF / 0x3E455 | Fixed-point texture loops with **runtime-patched memory displacements** trigger avoidable checks / code invalidation or poor x86 translation | Snapshot on-disk bytes **and compiled-time live guest bytes**; verify patched `0x12345678` placeholders; count block invalidations vs loop execution; compare native JIT | Live displacement is constant and generated native code is already efficient; invalidations limited to initial patching | High: strong id Software ASM match, special correctness risk due self-patching |
| H4 | Block transitions and dispatcher | Quake's numerous tiny loop blocks cause high linked-block/dispatch, cycle-check and cache-entry overhead compared with work done | Guest block size distribution; native block prologue/epilogue; host RIP clustering at links/dispatcher; dynamic count measurements (not samples alone) | Hot sampled RIPs predominantly within loop bodies; linked blocks bypass dispatcher | Medium: performance improvement may be general, but requires care with IRQ/cycle semantics |
| H5 | Guest x87 and memory helpers in vector/raster routines | Expensive x87 helper or state save/restore appears disproportionately in hot code | Verify actual Quake function for 0x306BD and 0x2F5CF; capture generated native calls to FPU helpers; inspect x87 state and guard costs | Helpers are rare; suspected blocks aren't x87-heavy; native FPU lowering already optimal | Medium: potentially valuable but much higher correctness surface |

## Concrete experiment protocol

1. **Snapshot live JIT compilation artifacts first**. For a narrowly selected `CS:EIP` list, emit exactly one record for each compilation generation: guest CS:EIP and linear address, the bytes of the guest code *as read in the compiler's address space*, the emitted native host bytes, host address interval, generation, code-availability flags, and hashes. Do not dump the whole DOS process. Never confuse a JIT block's complete native range (which may include deferred exception/slow paths) with a strict guest-instruction-to-host-instruction correspondence.
2. **Annotate and compare**: disassemble guest bytes with 32-bit x86 decoder and native bytes as x86-64; identify register accesses, memory helpers, `call` instructions, branch exits and apparently redundant code. Compare targeted locations against DOSBox `core_dyn_x86/decoder.h`, `dyn_cache.h` and id Software `d_draw.s` / `surf8.s`. Name host-side call targets only when verified (symbols/relocations), otherwise keep them as addresses.
3. **Choose one candidate modification** (prefer H1 or H2 depending on actual native code). First create a minimal DOS test with a known expected register/memory result, and test against both original and modified DOSBox. Include page crossings, protection faults, SMC, x87 state and changing CPU cycle counts as appropriate to the altered code path.
4. **Local evidence acceptance**: modified native code is demonstrably different in the expected way; all guest outputs agree with baseline; Quake 1.06 still completes `demo1`; no JIT lifecycle anomaly. Statistical sampling may reject *large* regressions, but noisy local FPS must not be treated as conclusive for small effects.
5. **Final A/B elsewhere**: same compiler/config, matched executable provenance, uninstrumented Quake 1.06, alternating runs and a stable host; one or more independent DOS workloads. Report confidence interval and regressions, not just best FPS.

## Counterexamples and failure modes to actively check

- A mapped guest block can include generated *deferred slow paths*. Naive raw RIP→guest instruction attribution via a contiguous interval is incorrect when emission order and branch repairs differ. Keep block-level claims separate from exact instruction mapping.
- Original `QUAKE.EXE` file offsets are **not** host RIPs. DJGPP `.text` offsets also do not cover dynamic relocations or runtime code patches.
- Reading guest bytes via a new emulator memory call can change memory-mapped I/O or trigger paging exceptions; a snapshot implementation should use already-decoded bytes or non-faulting existing readable TLB memory and explicitly say when bytes are unavailable.
- Host code cache addresses are reused: preserve per-generation mapping and never join by host RIP alone.
- Do not assume `X86_INLINED_MEMACCESS` is enabled in every build. Verify compile-time feature configuration.
- A helper being called does **not** alone prove it is an optimization opportunity. CPU state and page-fault semantics may require it.
- Local host load variance is large. Our prior 36-run FPS comparison is inconclusive on small overhead; avoid ranking hypotheses by differences smaller than noise.

## Artifacts and organization

- **DOSBox fork:** minimal optional feature for selected compile-time guest/native code snapshots and focused correctness tests; new stacked PR **on top of Guest block mapping PR #1**, not mixed into #1.
- **configs/research:** this hypothesis register, guest/host disassembly, source annotations, costs and experiment outcomes, plus local-only benchmarking harness.
- **Raw artifact:** filtered capture files and their hashes; do not commit proprietary Quake executable, `PAK0.PAK`, or unbounded logs.
- Keep hypotheses `H1`–`H5` stable. Record rejected hypotheses and why; never silently redefine success after measurements.

## Decision gate

Do **not** propose a JIT optimization before one concrete repeated guest block has (a) exact live bytes, (b) native generated bytes and code path, (c) a source-level explanation, (d) a minimal guest correctness test. The next PR is for **diagnostic evidence generation, not optimization**.

## First hypothesis-test evidence — 2026-11-07

A new, separate [selected JIT snapshots PR #2](https://github.com/kaaburgh/dosbox-staging/pull/2) built and ran original DOS Quake 1.06 locally twice. All nine requested guest/native block pairs were captured completely and linked to matching lifecycle generations. See [the evidence report](selected-guest-native-snapshots-2026-11-07.md).

- **H1 (stronger candidate, not yet confirmed as an inefficiency):** four textured-span blocks emit 2,219–3,160 native bytes each, with 28–42 *static* native call sites including deferred slow paths. Inline guest memory translation checks and helpers appear repeatedly in native disassembly. Next prove which locations execute before designing an optimization.
- **H2 (secondary candidate):** Z-span block emits 516 native bytes and four static call sites; its code contains a direct guest-memory fast path and conditional helper fallback. The static footprint alone does not show that this is more or less costly per executed guest instruction.
- **H3 (dynamic patching confirmed, performance conjecture still open):** four `surf8` blocks had 6, 7, 6, and 2 copies of on-disk `0x12345678` changed to live `0x0018007c`. The other five selected guest code snapshots matched the EXE. No evidence yet that these patches cause excessive JIT invalidations during rendering.
- **H4/H5:** no new evidence; remain untested.

Do not rank candidates by raw native code size alone: deferred slow paths and side exits might almost never execute. The next discriminating measurement is a **per-native-RIP sample histogram scoped to selected JIT generations**, plus verified helper attribution. This can be done here despite noisy FPS; use a stable external host only for final speedup estimates.


## Next discriminating step — 2026-11-07: native RIP offset tooling (PR #3)

[kaaburgh/dosbox-staging PR #3](https://github.com/kaaburgh/dosbox-staging/pull/3)
is stacked on snapshot PR #2. It adds a generation-aware profiler join:
SIGPROF samples (main TID, observed timedemo window) -> matching live JIT
generation -> native RIP offset -> selected snapshot's emitted-byte range.
Outputs are per-generation offset histograms and 16-byte buckets, including
selected-JIT/other-JIT/non-JIT sample denominators. **No new real Quake
RIP histogram was captured in this session**; the previous private raw
snapshot archive was not available locally. Six synthetic tests and one
end-to-end synthetic CLI check passed in the local environment; the new CI
and prior lifecycle-analyzer checks passed in GitHub Actions. No performance
improvement is claimed.

### H1 source inspection: important refinement

The actual 0.84-alpha x86-64 dynamic decoder
(src/cpu/core_dyn_x86/decoder.h) defines X86_INLINED_MEMACCESS.
Under that mode, dyn_read_byte and dyn_write_byte use inline per-access
guest-page shift + paging TLB table lookup + null check + direct native load
or store, with a conditional helper fallback. dyn_read_word/write_word
also test cross-page accesses and branch to separate unaligned helpers.
Therefore the interpretation **"each observed static call site means
an unconditional helper call" is false**. The H1 possibilities that remain
worth measuring are repeated inlined TLB translation/check instructions,
address calculations, occasional slow-path traffic, or expensive surrounding
guest arithmetic. A static native call count alone cannot rank them.

Before any JIT change, run unmodified Quake 1.06 with simultaneous
selected snapshots + SIGPROF using PR #3's documented runner; inspect
per-native-offset counts against the corresponding private native
disassembly, and determine whether helper execution outside the emitted
JIT needs a separate symbolized study. If H1 is mostly texture arithmetic
rather than TLB checks, lower H1 priority; test H2. Preserve H3's
self-patching correctness constraints regardless of which path is optimized.

See [native RIP experiment protocol](https://github.com/kaaburgh/dosbox-staging/blob/experiments/quake-native-rip-hotspots/extras/guest-block-mapping/NATIVE_RIP_HOTSPOTS.md).


## Native instruction offset validation — 2026-11-07 (stacked PR #4)

[kaaburgh/dosbox-staging PR #4](https://github.com/kaaburgh/dosbox-staging/pull/4)
adds a **validated linear x86-64 disassembly join** above PR #3's
generation-specific native RIP offset histograms. With the *same private*
snapshot bytes, original summary hashes and exact RIP CSV it:

- checks every native host blob SHA-256, size, generation and guest EIP;
- runs objdump on the native bytes, verifies full byte coverage and matches
  exact sampled RIP offsets to **linear-disassembly instruction starts**;
- records ambiguously decoded/non-start RIP samples separately, never
  attributing them to the preceding instruction;
- produces redacted instruction mnemonic/operand shapes and syntactic
  families, **not** raw native code or process addresses.

The tool's standalone CLI was run locally on synthetic x86-64 bytes; all
seven new tests plus six existing PR #3 tests passed, and GitHub Actions
passed both suites. No original Quake binaries or previous private
captures are mounted in this environment. Therefore **H1/H2 remain
unresolved**: no real Quake native-instruction histogram, executed helper
count, or FPS delta is claimed.

Linear objdump decoding is not an execution-traced CFG, and emitted
native blobs can contain deferred slow/exception code and alternate
entry points. A native-instruction family (move, predicate, branch,
arithmetic) is only syntax, not a verified TLB/texture-operation label.
The next informative test remains an **actual Quake 1.06 SIGPROF +
selected-snapshot run** followed by PR #3 then PR #4, with manual
control-flow review at sampled hot instruction offsets. Do not modify
the JIT solely from these synthetic tests.


## Original Quake run — real native RIP evidence (2026-11-07)

The full DOSBox Staging 0.84-alpha fork built under Debian 13 and the
unmodified original Quake 1.06 969-frame demo1 **passed twice** in
[CI run 42406911144](https://github.com/kaaburgh/dosbox-staging/actions/runs/42406911144).
All nine selected JIT generation snapshots were matched to lifecycle events;
161 of 161 selected native RIP samples resolved to linear-disassembly
instruction starts. The two sampling periods were 4,700/5,300 microseconds,
with 89/72 selected block samples. Non-selected JIT and non-JIT samples
were kept separate; zero profiler samples were lost.

The combined selected group samples were H1=61, H2=25 and H3=75. These
**are not total runtime shares for the Quake source functions**. Among
H1's observed instructions were 34 move/address, 9 branch, 8 integer
arithmetic, 4 flag-save and 3 x87 samples. This does **not** establish
that inline TLB checks or helper calls dominate. H3 has several
repeatably sampled native branch/flag-save offsets, but no evidence
of avoidable self-modifying-code invalidations yet.

The source revision actually tested was
\`c0f0c557d7dd8f6ce7c0b489d2f0de3b602acec7\`.
The complete reproducibility record, metadata corrections, per-EIP
counts and next gate are in
[official-quake-native-rip-2026-11-07.md](official-quake-native-rip-2026-11-07.md).
Native code blobs and proprietary game assets remain private.

**Decision:** move to source-level CFG and *actual helper/caller*
attribution before an H1/H2 JIT optimization. Do not treat repeated
\`mov\`, \`lea\`, \`pushf\` or \`jmp\` samples as proven redundant work.


## Local A/A timedemo stability — 2026-11-09 (stacked PR #6)

**Actual same-host, same-binary Quake 1.06 timedemo completed in the current
assistant Debian 13 container:** 4 warmups + 48 measured runs, all 969
frames; and four separate successful smoke runs. Imported original official
benchmark ZIP via the still-valid `kaaburgh/configs` Actions artifact, plus
the Release `OPT_JIT_BLOCK_TRACE=OFF` binary **previously built from the
fork** at `a090d30391785eb658650db2352b91029e5814fb`. This is a
*local execution of an archived fork build*, **not a claim that the
latest PR #5 branch was freshly rebuilt inside this container**.
Host AMD EPYC 9V74, CPU quota 4, Xvfb/SDL software texture, dynamic
core, Quake demo1 320×200. Quake SHA is the same original 1.06
`7cdb244122cc607cc6f162524bfcac60f6d11d8ca2ff07473d6cd962311161fb`.

Observed FPS median **189.15**, min/max **164.5/201.7**, p10/p90
**175.29/197.42**, CV **4.64%**, p10–p90 spread **11.70% of median**.
Four of 48 measured runs registered cgroup throttling (207.493 ms
cumulative), far too little to explain *all* the variation without
further evidence.

**Most discriminating test:** A/A *placebo*: two condition labels using
the same unmodified binary, assigned ABBA in 12 quartets. The observed
false A/B estimate was **−2.591%** with descriptive quartet-bootstrap
95% interval **[−5.093%, −0.080%]** (no true code difference). This is
an actual false positive and a strong empirical reason not to trust
a 1–3% FPS improvement from a naïve same-host comparison. Correlation
between quartets may invalidate the interval's nominal frequentist
coverage; do not mistake it for a calibrated significance test.

Source and dataset: [kaaburgh/dosbox-staging PR #6](https://github.com/kaaburgh/dosbox-staging/pull/6)
and [research report](https://github.com/kaaburgh/dosbox-staging/blob/experiments/quake-timedemo-stability/extras/guest-block-mapping/evidence/quake-aa-2026-11-09.md),
including a 52-sample compact CSV. The complete local CSV, manifest
and actual harness are also exported as a conversation ZIP, with no
game assets.

**Decision for H1–H5:** Continue correctness and instruction/helper
attribution; do not interpret local FPS shifts below several percent
as a real optimization until a much more stable target host or
a separately validated randomized/repeated paired A/B protocol
demonstrates adequate discrimination. The 2026-11-07 profiles
remain valid as *qualitative* code-path research, not precise runtime
fractions for whole guest functions.


### CPU-affinity follow-up (2026-11-09)

A second real local A/A series constrained DOSBox to virtual CPU 0 and
Xvfb to CPU 1 (same historical fork binary, same Quake 1.06). Four
warmups and 24 measured demo1 executions completed at 969 frames.
Compared with the unpinned 48-run series:

- Median FPS **169.45 vs 189.15** (not a paired or causal throughput
  comparison; the series ran sequentially).
- FPS CV **5.31% vs 4.64%**, p10–p90 spread / median **13.83% vs 11.70%**.
- Same-binary ABBA placebo observed **−1.84%** fake A/B difference
  (descriptive quartet-bootstrap 95% interval [−4.29%, +1.44%]).
- The data and caveats are in [PR #6 CPU-pinning follow-up](https://github.com/kaaburgh/dosbox-staging/blob/experiments/quake-timedemo-stability/extras/guest-block-mapping/evidence/quake-aa-2026-11-09.md).

**Simple whole-process CPU affinity failed to improve local FPS
precision.** Keep this host for correctness and exploratory hot-path
research, not small (<3%) JIT speedup claims.

## Hypothesis verdicts — 2026-11-09: instrumented local run with helper-caller attribution

The verdict report is
[quake106-hypothesis-verdicts-2026-11-09.md](quake106-hypothesis-verdicts-2026-11-09.md);
the per-block attribution data is
[quake106-helper-attribution-2026-11-09.csv](quake106-helper-attribution-2026-11-09.csv);
the analyzer is [../harness/attribute_helper_callers.py](../harness/attribute_helper_callers.py).

The "blind spot" that separated H1 from H5 — a profiler sample inside an
emulator helper with an unknown caller — was closed **without modifying the
emulator**: an extended SIGPROF preload also records eight stack words, and
the analyzer recovers the helper's return address from them. In a
21-block run over the timedemo window, **1,045 of 1,243 helper samples
(84.07%)** were attributed to a calling guest block.

The hypotheses keep their original wording; what changed is the **verdict**
against their own falsifiers:

- **H1 — not falsified, but the measurement unit was wrong.** The span
  region carries **22.8% of all helper traffic** (284 samples, 3.78% of
  the window), concentrated in **non-entry** blocks of the same functions
  (`0x10F4A` 54, `0x10CA0` 28, `0x110FB` 22, `0x10572` 21). A "hot entry
  block" systematically underestimates the cost, because the profiler lands
  in entry blocks while the cost mechanism lives in the other blocks of the
  same function. **Change the measurement unit to functions, not to
  hypothesis text.**
- **H2 — falsifier met.** The whole `0x10D00–0x10E00` region is 13
  samples (1.05% of helper traffic); `0x10D3B` itself calls helpers twice.
  Not worth pursuing for this guest.
- **H3 — weak.** 5 samples in `0x3E000–0x3FFFF` (0.07% of the window) and
  zero invalidations of `surf8` blocks.
- **H4 — premise measured.** 7,735 creations and 185 invalidations per
  run (2.39%), 7,669 distinct guest blocks, median 12 guest bytes against
  368 native bytes (×27.2), dispatcher share 1.99%, 0 of 11 selected blocks
  invalidated.
- **H5 — the only live hypothesis, and its content changed.** The renderer
  region carries 30.8% of helper traffic, but the largest single
  identified cost is **not x87**: the dynamic core does not implement
  `BT`/`BTS`/`BTR`/`BTC` at all (88 of 256 two-byte `0F` sub-opcodes are
  implemented), so Quake's per-plane BSP frustum-culling loop is executed
  by the **interpreter** through `gen_return(BR_Opcode)`. Measured share:
  38 samples (0.51% of the window) inside `CPU_Core_Normal_Run`, 19 of them
  at that block — a lower bound, because the round trip also breaks the
  dynamic core's block chain. The H5 requirement to identify the functions
  behind `0x306BD` and `0x2F5CF` is now closed: `R_ClipEdge` and
  `R_RecursiveWorldNode`.

The decoder gap, the guest regression test for that instruction family and
the acceptance criteria for closing it are in
[kaaburgh/dosbox-staging PR #11](https://github.com/kaaburgh/dosbox-staging/pull/11).
