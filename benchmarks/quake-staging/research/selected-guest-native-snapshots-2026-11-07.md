# Selected DOS Quake 1.06 guest/native JIT captures — local investigation, 2026-11-07

## Result

**Both independent local runs successfully completed the 969-frame Quake 1.06 `demo1`** with DOSBox Staging 0.84.0-alpha built from [stacked fork PR #2](https://github.com/kaaburgh/dosbox-staging/pull/2).

- DOSBox source commit actually built and tested: `630e0533c344fed69b0838d3d71c373a1545d5f6`; compiled with `OPT_JIT_BLOCK_TRACE=ON`.
- Executable: unmodified DOS Quake 1.06, SHA-256 `7cdb244122cc607cc6f162524bfcac60f6d11d8ca2ff07473d6cd962311161fb`.
- Environment: assistant's **local** Debian 13 Linux container, Xvfb, SDL software texture renderer; GitHub Actions was used **only to build and export the matching DOSBox executable**, not to run Quake.
- First run: 7,845 JIT CREATE + 185 INVALIDATE; second run: 7,850 CREATE + 185 INVALIDATE.
- All **nine selected blocks** were captured in both runs; each had `guest_complete=true`.
- Every snapshot generation ID, guest CS:EIP, guest linear interval and native start/end interval matched its corresponding `CREATE` event in the same run's lifecycle CSV. Blob sizes also matched metadata.
- **Nine of nine** live guest-byte sequences reproduced *exactly* in the second run. Native machine-code **mnemonic sequences and lengths** reproduced exactly as well. Raw native bytes differ between runs owing to process-specific host addresses, so their SHA-256 hashes should not be expected to match.
- No gameplay binaries or raw snapshots are committed. Raw records are available privately in the conversation artifact `quake106-selected-jit-snapshots-private-2026-11-07.zip`.

## Captured evidence (first run; reproduced in the second)

| Guest EIP | Source candidate | Guest bytes | Native bytes | Static native `call` sites | Differences vs on-disk guest bytes |
|---|---|---:|---:|---:|---:|
| `0x10D3B` | `D_DrawZSpans` | 49 | 516 | 4 | 0 |
| `0x11216` | `D_DrawSpans8` family | 119 | 3,160 | 42 | 0 |
| `0x112CC` | `D_DrawSpans8` family | 119 | 2,504 | 36 | 0 |
| `0x11343` | `D_DrawSpans8` family | 130 | 3,123 | 42 | 0 |
| `0x1143F` | `D_DrawSpans8` family | 126 | 2,219 | 28 | 0 |
| `0x3E233` | `R_DrawSurfaceBlock8_mip0` | 103 | 2,059 | 32 | 24 |
| `0x3E29A` | `R_DrawSurfaceBlock8_mip0` | 103 | 2,080 | 32 | 28 |
| `0x3E3EF` | `R_DrawSurfaceBlock8_mip1` | 102 | 2,058 | 32 | 24 |
| `0x3E455` | `R_DrawSurfaceBlock8_mip1` | 71 | 1,581 | 20 | 8 |

**Caution:** the `call` counts above are from linear disassembly of *all emitted native bytes*, **including deferred slow/exception code**. They are **not executed-call counts**, nor do they prove an optimization. No precise guest-instruction-to-native-instruction relation has been established yet.

## Confirmed dynamic patching in Quake (H3)

Original Quake 1.06's on-disk x86 ASM in `R_DrawSurfaceBlock8_mip*` uses the distinctive 32-bit displacement `0x12345678`. In the live guest code recorded **after** DOSBox decoded the hot blocks, it had been replaced with **`0x0018007c`**.

All observed changes in these four captured blocks are at the little-endian four-byte displacement sites:

| Guest EIP | Original placeholder occurrences | Live patched displacement occurrences | Changed bytes |
|---|---:|---:|---:|
| `0x3E233` | 6 | 6 | 24 |
| `0x3E29A` | 7 | 7 | 28 |
| `0x3E3EF` | 6 | 6 | 24 |
| `0x3E455` | 2 | 2 | 8 |

**This confirms Quake runtime modification, NOT an unnecessary DOSBox JIT invalidation.** We would need to count actual invalidation events caused by the patching and identify whether they occur only during initialization; do not infer the full H3 performance effect.

The other five selected blocks exactly match the on-disk `QUAKE.EXE` bytes, making the static binary a reliable reference for *these particular snapshots*.

## First native-code observations

- `D_DrawZSpans` (`0x10D3B`) shows a relatively compact block. The disassembly includes an inline guest-memory fast path and a conditional fallback to a native helper for a 32-bit Z-buffer store. This suggests evaluating the **fast-path address checks**, not assuming helper calls execute unconditionally.
- `D_DrawSpans8` (`0x11216`, `0x112CC`, `0x11343`, `0x1143F`) emits long groups of TLB lookup, boundary checks, conditional branches and deferred helper paths for loads/stores. This is a promising **H1 diagnostic target**, but linearly counted static calls cannot identify runtime CPU hotspots.
- The surface mip blocks also emit numerous guest-memory fast/slow paths. They are particularly useful for evaluating H3 correctness because captured guest displacements differ from the executable image.

One representative emitted native fast path checks a 4 KiB guest page boundary, reads a TLB pointer, tests it, performs a native memory operation on success, and conditionally jumps to helper code otherwise. This is directly visible in the generated x86-64, not inferred merely from the C++ source.

## Next experimental decision

**Priority: resolve H1's actual executed native hot path before changing DOSBox.** Join per-thread SIGPROF RIP samples to the selected block generations (using the already proven generation/lifetime mapping), compute **per-native-address or short-range sample histograms** inside each selected block, and annotate addresses against the JIT disassembly. Verify which TLB checks and fallback helpers are actually executed, especially inside `D_DrawSpans8`.

Two alternative results should change the plan:

1. If native samples cluster in tight fast-path TLB checks / address calculation, evaluate an equivalent, shorter lowering with a focused DOS memory-correctness test.
2. If native samples cluster in C++ helpers outside generated code, block RIP profiling alone misses that time; add helper-call attribution, not an unsupported JIT fast-path optimization.

H2 (`D_DrawZSpans`) is a second candidate; H3 code patching is confirmed but its **performance** hypothesis remains open.

## Methodological limits

Snapshots use direct TLB mappings immediately after decoding, **not** a tap into every decoder fetch. We observed complete, stable Quake snapshots here, but this method may be incomplete for unusual mapped memory. The complete native range includes side exits and slow paths. No timing-based optimization claim is made; the local host has substantial FPS variability. Final performance comparisons belong on a dedicated stable host.

Raw guest code and generated JIT blocks are not uploaded to GitHub. Store local artifacts privately and keep their hashes/derived statistics alongside code provenance.
