# How to read this archive

Produced by extras/jit-audit/validate/phase2_validate.py (DOSBox Staging,
kaaburgh/dosbox-staging). It validates the Phase 2 x86-64 dynamic-core
pull requests #14 (C4), #15 (C1a), #16 (C2), #17 (C6), the measurement-only
integration build all4 (C4+C1a+C2+C6) and optionally #18 (C3) and #19 (C1b)
against main at 27b1b7c.

Start with summary.md (human readable) and summary.json (machine readable).

- metadata.json: host, CPU topology (L3 groups ~ CCDs), governor/boost,
  power/thermal state where readable, tool versions, runner arguments.
- sources.json: exact commit of every variant, whether it equals the Phase 2
  head, files changed relative to the baseline.
- builds.json: CMake preset, compiler, flags, the compile command of
  core_dyn_x86.cpp, SHA-256 of every binary, rebuild check.
- tests/verdicts.json and tests/<variant>/<core>/<TEST>.txt: raw output of
  every guest test (DOS .COM programs built with NASM from
  extras/jit-audit/tests) and the verdict. Expected values come from the Intel
  SDM, not from comparison with the normal core. KNOWN marks two documented
  deviations of the unmodified emulator: x87 #PF imprecision in the dynamic
  core (pushed EIP = block start, stale registers) and the normal core's
  wrong EIP for a faulting CALL push. Both must be identical to the baseline.
- bench/runs.csv: every Quake run (label, guest frames/seconds/fps, main
  thread CPU seconds for the demo window, affinity, sensors);
  bench/manifest.json (seed, schedule, binary hashes); bench/stats.json
  (bootstrap CIs, A/A placebo); bench/determinism.json.
- diagnostics/: logs of failed tests, deviating or failed benchmark runs (with
  one normal run of the same label for comparison), build logs.

Questions worth checking independently:
1. Do all variants meet the architectural expectations, with no output
   differing from the baseline?
2. Is the A/A placebo consistent with zero, and is its CI narrow enough to
   resolve the claimed effects?
3. Are the guest results deterministic and equal to the Phase 2 reference
   (969 frames, 326.7 fps; 326.9 fps for c6/all4, explained in PR #17)?
4. Are the speed-ups consistent with Phase 2 (Intel Emerald Rapids VM,
   Linux): C4 +11.1%, C1a +9.1%, C6 +8.8%, C2 +3.4%, all4 +37.1%?

Not included on purpose: game files, emulator binaries, JIT dumps, local paths
(replaced by <HOME>, <WORK>, <REPO>, <TMP>, <USER>, <HOST>).
