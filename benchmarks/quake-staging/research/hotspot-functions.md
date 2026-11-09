# Quake 1.06 guest JIT hotspots → original COFF and id Software source

## Provenance and method

- Unmodified DOS Quake 1.06 (`QUAKE.EXE` SHA-256 `7cdb244122cc607cc6f162524bfcac60f6d11d8ca2ff07473d6cd962311161fb`).
- Source comparison: `id-Software/Quake` at `bf4ac424ce754894ac8f1dae6a3981954bc9852d` (later 1.09-era engine; **not** 1.06 exact source).
- Demo-only 0.84-alpha profile from `kaaburgh/dosbox-staging` commit `edf22e77de501200192fbaf595e8d016490d53d3`: 553 native JIT samples attributed to guest code, out of 959 main-thread samples.
- Embedded COFF image begins at file offset `0x800`. Its `.text` virtual address is `0x10A8`, raw file offset `0x8A8`, size `0x5A158`.
- For guest EIPs in `.text`, **original file offset = guest EIP − 0x800**. All 30 leading demo-only guest blocks mapped to this section.
- The profiler's guest `CS=00A7` has a linear base of `0x10000000` in this run. We do **not** interpret guest linear `0x10010D3B` itself as a COFF virtual address.
- `harness/map_quake_coff.py` validates the COFF header and performs the conversion without any Quake recompilation. Binutils `objdump -b binary -m i386 -M intel --adjust-vma=0x10a8` can disassemble the extracted `.text` bytes.
- No Quake binaries/assets are stored in this repository.

## Strongly supported source correspondence

| Guest EIP(s) | Demo JIT samples | Candidate source function | Evidence | Confidence |
|---|---:|---|---|---|
| `0x10D3B` | 20 | `D_DrawZSpans` | Repeated integer z-buffer packing: `shr eax,16`, `and esi,0xffff0000`, `or eax,esi`, two DWORD stores, `dec ecx; jnz`. Matches `WinQuake/d_draw.s` lines ~790–915, especially `LFMiddleLoop` | High: distinctive exact instruction sequence |
| `0x11216, 0x112CC, 0x11343, 0x1143F` | 37 combined | Software textured span drawing, consistent with `D_DrawSpans8` | Unrolled 8-bit writes, `adc esi,advancetable[ecx*4]`, fixed-point texture steps and x87 setup in `WinQuake/d_draw.s` lines ~92–760 | High for algorithm family; medium for exact function boundary |
| `0x3E233, 0x3E29A` | 17 combined | `R_DrawSurfaceBlock8_mip0` | `sar ebp,4`, packed texel lookup through the sentinel displacement `0x12345678`, byte packing into DWORDs; matches `WinQuake/surf8.s` lines ~46–270 | High for source algorithm |
| `0x3E3EF, 0x3E455` | 15 combined | `R_DrawSurfaceBlock8_mip1` | Similar surf8 lookup, but `sar ebp,3`, matching the mip1 block implementation in `WinQuake/surf8.s` lines ~272–442 | High for source algorithm |

**Do not sum these counts into an overall function CPU percentage.** They count only sampled *entry blocks* among the top rows; other blocks in each function are excluded, and native helper CPU time is not attributed.

## Still unresolved, explicitly not assigned to functions

| Guest EIP | Samples | Verified machine-code behavior |
|---|---:|---|
| `0x306BD` | 12 | x87 vector arithmetic (`fld`, `fmul`, `faddp`); specific Quake function unproven |
| `0x55EF6` | 11 | Optimized aligned memory copy with `rep movsd` / `rep movsb`; may be a runtime library routine |
| `0x2F5CF` | 11 | Table-driven indexed reads and integer-to-x87 conversion; function not identified |
| `0x0E5D8` | 7 | 32-bit indexed copy loop; function not identified |

## Critical complication: runtime-patched machine code

`WinQuake/surf8.s` includes hardcoded `0x12345678` displacements patched during runtime. The original **1.06 COFF .text also contains those sentinel bytes** at the matched addresses.

Therefore static file-offset mapping is valuable for **function identification**, but a complete mapping of **executed guest instruction bytes → JIT output** requires a snapshot of guest executable memory *after runtime patching*. It would be incorrect to treat the static `0x12345678` displacement as the actual source address used during timedemo.

## Next evidence milestone

Obtain the corresponding live guest-memory bytes at the four hotspot families while leaving the original `QUAKE.EXE` unchanged. This is a narrowly scoped follow-up to guest instruction mapping; it should be a separate PR from the minimal lifecycle instrumentation.

Source links:

- [D_DrawZSpans in id Software's d_draw.s](https://github.com/id-Software/Quake/blob/master/WinQuake/d_draw.s)
- [R_DrawSurfaceBlock8_mip* in id Software's surf8.s](https://github.com/id-Software/Quake/blob/master/WinQuake/surf8.s)
- [Original JIT-mapping evidence](https://github.com/kaaburgh/dosbox-staging/pull/1)
