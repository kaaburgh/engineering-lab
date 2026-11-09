# Historical GitHub Actions (inactive)

These YAML files were copied unmodified from the private `kaaburgh/configs` research branches, with the source commits documented in [../../MIGRATION.md](../../MIGRATION.md).

They are **reference artifacts**, not runnable GitHub Actions in this repository: only YAML under the repository root's `.github/workflows/` directory is discovered as workflow definitions by GitHub Actions.

Do not blindly copy these back to the active workflow directory. Their `on:` filters, source checkout paths, fork revisions, dependencies, and expected benchmark archives were written for specific historical experiments. Port and review them separately when needed.

No Quake executable, benchmark ZIP, packaged SDK, local run output, or authorization secret was migrated.
