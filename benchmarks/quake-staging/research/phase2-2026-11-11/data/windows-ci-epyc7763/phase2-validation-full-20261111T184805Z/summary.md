# Phase 2 validation — phase2-validation-full-20261111T184805Z

**Overall: OK**

Mode **full**, runner v1, Windows AMD64, CPU: AMD EPYC 7763 64-Core Processor

## Builds

| Variant | Commit | Phase 2 head | Binary SHA-256 | Build |
|---|---|---|---|---|
| base | 27b1b7ca719c | same | af93e7ca0cf9a9fb | ok |
| c4 | 5bacbd99f135 | same | ba68554a53e14dd9 | ok |
| c1a | 22ad052dfe80 | same | 15be7c4e74f68b76 | ok |
| c2 | 4619d41d6b8f | same | 0257b71337088c13 | ok |
| c6 | f8e39504ca4e | same | 9f3768d6848f856f | ok |
| all4 | 911ccc052628 | same | 8cc089baed619121 | ok |
| c3 | c861a8b02e46 | same | db15b61150c91d19 | ok |
| c1b | dfed705a3607 | same | e787c1c683b15c10 | ok |

Incremental rebuild check (baseline rebuilt last): identical code (differs only in link timestamp/checksum/debug directory)

## Guest tests (architectural expectations)

PASS = SDM-derived expectation met; KNOWN = documented pre-existing deviation, identical to the baseline; FAIL = unexpected.

| Variant | Core | PASS | KNOWN | FAIL | differs from base |
|---|---|---|---|---|---|
| all4 | dynamic | 8 | 2 | 0 | - |
| all4 | normal | 9 | 1 | 0 | - |
| base | dynamic | 8 | 2 | 0 | - |
| base | normal | 9 | 1 | 0 | - |
| c1a | dynamic | 8 | 2 | 0 | - |
| c1a | normal | 9 | 1 | 0 | - |
| c1b | dynamic | 8 | 2 | 0 | - |
| c1b | normal | 9 | 1 | 0 | - |
| c2 | dynamic | 8 | 2 | 0 | - |
| c2 | normal | 9 | 1 | 0 | - |
| c3 | dynamic | 8 | 2 | 0 | - |
| c3 | normal | 9 | 1 | 0 | - |
| c4 | dynamic | 8 | 2 | 0 | - |
| c4 | normal | 9 | 1 | 0 | - |
| c6 | dynamic | 8 | 2 | 0 | - |
| c6 | normal | 9 | 1 | 0 | - |

Negative controls (deliberately wrong expectations, must be reported): all detected

## Quake 1.06 timedemo demo1 (fixed 1,000,000 cycles)

Determinism: **OK** (0 deviating, 0 failed runs); guest results match Phase 2 reference (MSVC ABI (clang-cl/MSVC): c6/all4 326.8): yes

A/A placebo (base vs base2): -0.05% [-0.42, +0.35] — consistent with zero; resolution ≈ ±0.39% (limit 3.0%)

Timing: **CONCLUSIVE**

| Label | Speed-up vs base [95% CI] | Blocks | Median demo CPU s | CV % | Phase 2 (Intel VM) |
|---|---|---|---|---|---|
| all4 | +19.88% [+19.25, +20.55] | 20 | 3.8906 | 1.09 | +37.1% [+29.5, +44.2] |
| base | -0.03% [-0.21, +0.17] | 20 | 4.6562 | 0.6 |  |
| base2 | +0.03% [-0.17, +0.21] | 20 | 4.6562 | 0.96 |  |
| c1a | +6.96% [+5.87, +7.82] | 20 | 4.3359 | 2.22 | +9.1% [+7.0, +11.3] |
| c1b | +1.40% [+0.98, +1.83] | 20 | 4.5938 | 0.87 | +1.6% [-0.4, +3.5] |
| c2 | +2.86% [+2.31, +3.37] | 20 | 4.5156 | 1.1 | +3.4% [+1.2, +5.8] |
| c3 | +2.14% [+1.36, +2.79] | 20 | 4.5469 | 1.58 | +2.0% [-0.1, +4.2] |
| c4 | +3.05% [+2.62, +3.51] | 20 | 4.5156 | 0.78 | +11.1% [+8.8, +13.4] |
| c6 | +5.76% [+5.13, +6.45] | 20 | 4.4141 | 1.06 | +8.8% [+6.8, +11.0] |

Same analysis with QueryThreadCycleTime (cycle-accurate; GetThreadTimes above has clock-tick resolution): all4 +19.81% [+19.35, +20.27], c1a +6.89% [+5.92, +7.65], c1b +1.61% [+1.30, +1.94], c2 +2.84% [+2.27, +3.29], c3 +2.00% [+1.17, +2.57], c4 +2.79% [+2.44, +3.16], c6 +5.62% [+5.13, +6.11]

Speed-up = geometric mean over blocks of (reference CPU time / variant CPU time) − 1, reference = geometric mean of base and base2 in the same block; percentile bootstrap.

