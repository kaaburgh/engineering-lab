# Guest block mapping — DOSBox Staging v0.83.0

An opt-in, Linux/x86-64 diagnostic patch to map DOSBox Staging dynamic-core native JIT addresses back to guest **CS:EIP** and **linear address**. For original DOS Quake 1.06, not a replacement for the performance benchmark.

## Source and build

- Target: [dosbox-staging/dosbox-staging v0.83.0](https://github.com/dosbox-staging/dosbox-staging/tree/v0.83.0), commit `7b40053b7ac580843d0461eba8c36a47a990e66c`.
- Apply `dosbox-staging-v0.83.0-guest-block-mapping.patch` with `git apply` to the **upstream DOSBox repository root**.
- Configure with `-DOPT_JIT_BLOCK_TRACE=ON` (default OFF) and compile a Release binary.
- Set `DOSBOX_JIT_BLOCK_TRACE=/absolute/non-existing/path/block-events.csv` for one run. Logging does not activate unless the environment variable is set. Exclusive-create prevents overwriting or combining runs.
- Records `C` (created) and `D` (invalidated) events with monotonic ns timestamps, process ID, unique **generation**, guest CS:EIP, linear guest address interval, and half-open host native-code interval.
- The address in `guest_linear_begin` is DOSBox `SegPhys(cs)+reg_eip` (not a file offset or host physical address). Generated native code may be reused: a timestamp-aware generation key is **required**.

The patch changes `CMakeLists.txt`, `core_dyn_x86.cpp`, `core_dyn_x86/decoder.h`, `dyn_cache.h` and adds `jit_block_trace.h`. It does **not** modify CPU opcode behavior. The source patch intentionally omits host-specific Debian SDK/MIDI compatibility changes that were used to compile it in an offline container.

## Instrumented Quake 1.06 integration tests

Unmodified Quake 1.06 shareware, SHA-256 of `QUAKE.EXE`:
`7cdb244122cc607cc6f162524bfcac60f6d11d8ca2ff07473d6cd962311161fb`.
Linux Xeon container, 969-frame `timedemo demo1`, dynamic CPU core, Pentium type, real-mode cycles 3000 and protected-mode cycles max, **SDL software texture backend** (to isolate JIT from Mesa llvmpipe overhead).

| Trial | FPS | Blocks created | Invalidations | Main-thread samples within demo | Mapped JIT samples |
|---|---:|---:|---:|---:|---:|
| 1 | 145.2 | 7,724 | 185 | 1,173 | 659 |
| 2 | 141.7 | 7,722 | 185 | 1,188 | 655 |

Two profiles agree on recurrent guest hotspots:

| Guest CS:EIP | Run 1 | Run 2 |
|---|---:|---:|
| `00A7:0002F5CF` | 22 | 18 |
| `00A7:00011343` | 18 | 14 |
| `00A7:0003E455` | 15 | 11 |
| `00A7:00010D3B` | 13 | 13 |

Overlapping simultaneously live native-code intervals: **none found**. Multiple generations can share a host address at different times. 9 unit tests pass (generation reuse, lifecycle and malformed events, overlap detection, thread/time filtering, guest aggregation). The original game and all proprietary binaries remain outside this repository.

## Analyze a trace

The Python analyzer in `tools/analyze_trace.py` expects:

- DOSBox trace CSV from this patch;
- optional little-endian 24-byte `SIGPROF` records `<QQII>` = monotonic_ns, host RIP, Linux TID, reserved;
- optionally `--start-ns` and `--end-ns` to restrict the samples to timedemo. The Linux main thread's TID is the same as the DOSBox PID, so Mesa workers are excluded.
- `--output` for per-generation counts and `--output-guest` for aggregated guest address hot spots.

Example:
```bash
python3 tools/analyze_trace.py --trace jit-blocks.csv --samples samples.bin \
  --start-ns 1000000000 --end-ns 2000000000 \
  --output generations.csv --output-guest guest-hotspots.csv
python3 -m unittest discover -s tools -p test_analyze_trace.py -v
```
These timestamp numbers are placeholders; use monotonic time from the actual run.

## Known limits and review points

1. **Only native JIT RIP samples are attributed.** Time in `mem_readd`, FPU native helpers, rendering code or other C++ routines is intentionally **not** attributed to a guest instruction. Follow-up work can record helper call context.
2. The `SIGPROF` profiler's sampling is statistical; no exact block invocation counts. Present tests use a 5ms per-thread CPU-time interval.
3. Quake's DOS-extender loads code at runtime. Guest CS:EIP is **not** directly an offset into `QUAKE.EXE`, whose 1.06 release lacks COFF symbols.
4. Cache clearing is instrumented through `CacheBlock::Clear()` and generation replacement. Further correctness reviews should test cache resets, self-modifying programs and other DOS titles, not only Quake.
5. Changes to wall-clock FPS are not reliably determined in a shared container. We observed ~99 vs ~139 FPS between nearby control runs due to host variability. The patch is **not** claimed to accelerate DOSBox or have zero measurement overhead.
6. This is a **staging PR in kaaburgh/configs**, not an upstream DOSBox Staging PR; an upstream fork is not connected.

Raw event logs, sample streams, C helper source, Quake launch scripts and compiler log are packaged separately in the downloadable evidence archive from the analysis conversation.

## Executable local reproduction

From this directory (after the patched DOSBox binary is built), compile the sampling helper:

```bash
cc -O2 -shared -fPIC -o tools/preload_sigprof_thread.so tools/preload_sigprof_thread.c -ldl -pthread
python3 tools/run_guest_trace.py --dosbox /path/to/patched/dosbox \
  --game /path/to/original/quake106-extracted --out ./local-1 \
  --profiler tools/preload_sigprof_thread.so --renderer texture
python3 tools/analyze_trace.py --trace local-1/jit-blocks.csv --samples local-1/samples.bin \
  --start-ns "$(python3 -c 'import json;print(json.load(open("local-1/result.json"))["demo_start_observed_ns"])')" \
  --end-ns "$(python3 -c 'import json;print(json.load(open("local-1/result.json"))["demo_end_observed_ns"])')" \
  --output-guest ./local-1/guest-hotspots.csv
```

For a clean performance control using the same instrumented executable but no event logging, omit `--profiler` and add `--no-trace`. Use a different `--out` directory for every run.
