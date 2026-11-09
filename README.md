# Engineering Lab

Public, reproducible engineering research: performance experiments, reverse engineering, hypotheses, measurements, and technical findings.

This is an **experiment and evidence repository**, not a downstream source-code fork or a collection of machine configurations.

## Research areas

- [DOSBox Staging × DOS Quake 1.06](benchmarks/quake-staging/) — guest-to-native JIT block mapping, performance hypotheses, correctness probes, benchmarks, and supporting scripts.
- [Reverse engineering](reverse-engineering/) — future investigations, organized by target.
- [Hardware](hardware/) — future firmware and hardware experiments, organized by target.

## Repository conventions

Each investigation lives in its own directory and should distinguish:
- **Hypothesis:** a falsifiable prediction, not an observed regression or established optimization.
- **Evidence:** direct observations, environment details, exact tool/source revisions, input hashes, and recorded limits.
- **Experiment:** reproducible commands or scripts, acceptance criteria, and falsifiers.
- **Finding:** conclusions proportionate to the evidence, including negative results.

Store concise derived evidence, parsers, scripts, configuration examples, and benchmark manifests. Keep large raw traces and build products in external artifacts with hashes and provenance where practical.

Performance measurements from a constrained or shared environment are exploratory unless stability and measurement conditions are demonstrated. Correctness must be checked independently from speed.

## Separation of concerns

- **Here:** study design, external harnesses, analyses, experiment reports, and reproducibility metadata.
- **In upstream/forks:** implementation patches and regression tests intended to ship with a project (e.g. [kaaburgh/dosbox-staging](https://github.com/kaaburgh/dosbox-staging)).
- **Never here:** copyrighted game releases, proprietary firmware dumps, secrets, or personal machine configs.

Historical workflows copied from `configs` are archived as data under the study's `workflows/archive/` directory. They are **not activated** as GitHub Actions; inspect and port them before reuse.

## Attribution and provenance

Research-specific source revisions and migration notes are recorded in each study's `MIGRATION.md`. Publication does not imply ownership of third-party source material or grant a new license to third-party code.
