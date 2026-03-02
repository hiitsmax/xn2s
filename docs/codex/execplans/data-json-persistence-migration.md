# Data Folder JSON Persistence Migration

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, every CLI command that persists project data under `data/` writes JSON files by default. This keeps downstream processing consistent and avoids mixed YAML/JSON formats in the same pipeline.

## Progress

- [x] (2026-03-02 23:00Z) Audited all `data/` persistence paths used by CLI commands.
- [x] (2026-03-02 23:01Z) Migrated source catalog storage from YAML to JSON (`src/xs2n/storage.py`).
- [x] (2026-03-02 23:02Z) Migrated timeline storage from YAML to JSON (`src/xs2n/timeline_storage.py`).
- [x] (2026-03-02 23:03Z) Migrated onboarding state persistence from YAML to JSON (`src/xs2n/cli/helpers.py`).
- [x] (2026-03-02 23:04Z) Updated tests and docs for `.json` defaults and JSON content expectations.
- [x] (2026-03-02 23:05Z) Ran full test suite and smoke-checked command help output.

## Surprises & Discoveries

- Observation: There were three independent YAML persistence helpers (`sources`, `timeline`, and onboarding state), so changing only one would still leave mixed formats.
  Evidence: Repository search for `yaml.safe_load` and `data/*.yaml` defaults.

## Decision Log

- Decision: Switch all `data/` defaults to `.json` and use stdlib `json` read/write in persistence helpers.
  Rationale: Single serialization format simplifies downstream processing and operational tooling.
  Date/Author: 2026-03-02 / Codex

- Decision: Keep loader behavior permissive by returning empty docs for malformed JSON.
  Rationale: Matches prior fault-tolerant behavior and keeps CLI flows resilient.
  Date/Author: 2026-03-02 / Codex

## Outcomes & Retrospective

The migration is straightforward and low risk because persistence is centralized in three helpers. The main compatibility tradeoff is that previous `.yaml` files are no longer used by default paths, so users should rerun commands or migrate files if they want old data reflected in new JSON files.
