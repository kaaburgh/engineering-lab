# Provenance: Quake / DOSBox research migration

The Quake/DOSBox material in this directory was **copied** (not moved) from the private `kaaburgh/configs` repository on 2026-11-09. The original branches are preserved there.

| Source branch | Source commit | Imported content |
| --- | --- | --- |
| `bench/quake-p0-p1-local-builds` | `e86ba6cf8a55c8dd8abd7e26867a77dbacb5340f` | study README, `research/`, `harness/`, and six historical workflows |
| `bench/quake-guest-block-mapping-pr1` | `4e9535f90221c5de6614f7821640282dedd28827` | `guest-block-mapping/` and its historical workflow |
| `bench/dosbox-084-guest-mapping-validate` | `5af20331e8856d8b1ee3008bb29fb914f589d4c3` | three historical workflows |
| `bench/dosbox-local-source-2026-11-07` | `41aa743b7b79069dd01c200ca2003203eccb7948` | three historical workflows |
| `bench/quake-staging-2026-11-06` | `965824821b2c5a8f328ac106dc2c86bb21d7454b` | early historical Quake performance workflow |

The source repository is private; its direct links are not publicly viewable. The open-source DOSBox instrumentation, implementation work, and correctness probes have their own provenance in [the public DOSBox fork](https://github.com/kaaburgh/dosbox-staging/pulls).

## Publication rules and path changes

- DOS Quake `QUAKE.EXE` and the Quake benchmark/game assets were **not** copied. The study records checksums and public upstream download references instead.
- Diagnostic source code, small patches, evidence summaries, and scripts are copied with their substantive contents retained.
- The study README's description of CI was updated to point to `workflows/archive/`; historic workflow files themselves are kept unmodified.
- Former `configs/.github/workflows/*.yml` files are now `benchmarks/quake-staging/workflows/archive/*.yml`, intentionally outside GitHub Actions' active directory. These reference the old branch layout and require review before reuse.
- Some code and docs describe historical DOSBox version-specific experiments. Do not assume all scripts work without adapting inputs, versions, or paths.

See [research/hypotheses.md](research/hypotheses.md) and [guest-block-mapping/README.md](guest-block-mapping/README.md) for study-specific methodology.
