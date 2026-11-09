# Historical caller-attribution harness

These are the scripts and preload source used in the 2026-11-09 local
experiment. They preserve the actual instrumentation and analysis, including
local example paths; adapt the paths to the DOSBox fork and build before reuse.
`analyze_stacks.py` and `attribute_fpu.py` depend on the fork's
`extras/guest-block-mapping` analyzers and require private same-process trace,
map, sample and snapshot inputs. The raw inputs are not published here.

The stack sampler uses Linux `/proc/self/mem` and frame pointers; its output is
not a complete unwind and candidate call sites require independent verification.
See [the evidence report](../../research/caller-attribution-2026-11-09.md).
