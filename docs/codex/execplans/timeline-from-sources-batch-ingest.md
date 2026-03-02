# Timeline Batch Ingestion From Sources

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, timeline ingestion can run for one account (`--account`) or for all onboarded sources (`--from-sources`) in one command. This allows scraping-pipeline runs to operate directly from the persisted source catalog.

## Progress

- [x] (2026-03-02 23:20Z) Added `--from-sources` and `--sources-file` options to `xs2n timeline`.
- [x] (2026-03-02 23:21Z) Added option validation for mutually-exclusive account selection.
- [x] (2026-03-02 23:22Z) Added automatic legacy migration from `sources.yaml` to `sources.json` when needed.
- [x] (2026-03-02 23:24Z) Added graceful `429` handling for batch runs (partial summary + clean exit).
- [x] (2026-03-02 23:23Z) Added tests for batch mode and migration behavior.
- [x] (2026-03-02 23:30Z) Ran full test suite and live command smoke checks.

## Surprises & Discoveries

- Observation: Existing local data still included `data/sources.yaml` from before JSON standardization.
  Evidence: Workspace listing showed both YAML and JSON timeline/source artifacts.

## Decision Log

- Decision: Keep single-account and batch modes inside one `timeline` command.
  Rationale: Avoid command sprawl and keep scraping entrypoint simple.
  Date/Author: 2026-03-02 / Codex

- Decision: Auto-migrate legacy sources YAML only when JSON source file is missing.
  Rationale: Safe default that avoids overwriting existing JSON state.
  Date/Author: 2026-03-02 / Codex

## Outcomes & Retrospective

This closes a key pipeline gap: source onboarding and timeline scraping are now directly linked through `sources.json`. The backward-compatibility tradeoff is intentionally minimal and one-way (YAML -> JSON only on missing JSON).
