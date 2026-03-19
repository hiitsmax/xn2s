# Report Schedule CLI

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a user can define named digest schedules inside `xs2n`, export the corresponding operating-system job definitions, and execute a named schedule through one stable CLI entrypoint: `xs2n report schedule run <name>`. The operating system remains the real scheduler, while `xs2n` stays the source of truth for schedule definitions, overlap protection, run bookkeeping, and portable export output.

The visible proof is:

- `xs2n report schedule create ...` saves a named schedule in `data/report_schedules.json`.
- `xs2n report schedule list`, `show`, and `delete` manage those saved definitions.
- `xs2n report schedule run <name>` executes the saved `report latest` flow with a lock file and updates `last_run`.
- `xs2n report schedule export <name> --target cron|launchd|systemd` prints install-ready output without mutating the system.

## Progress

- [x] (2026-03-18 18:45Z) Reviewed the existing `report latest`, UI run-arguments, storage, and test surfaces to lock the smallest safe integration points.
- [x] (2026-03-18 18:45Z) Ran the current baseline focused suite: `uv run pytest tests/test_report_cli.py tests/test_ui_run_arguments.py tests/test_ui_run_preferences.py` (`26 passed`).
- [x] (2026-03-18 18:52Z) Added failing tests for the shared `report latest` runtime helper and the new `report schedule` CLI/storage/export paths.
- [x] (2026-03-18 22:15Z) Implemented the shared report runtime contract and wired `src/xs2n/cli/report.py` through it while keeping module-level hooks monkeypatchable for direct-call CLI tests.
- [x] (2026-03-18 22:20Z) Implemented schedule schemas, storage, runner, overlap locks, and export renderers for `cron`, `launchd`, and `systemd`.
- [x] (2026-03-18 22:45Z) Updated docs, verified `xs2n report schedule --help`, smoke-tested `create` + `export`, and reran focused plus full verification suites (`208 passed`).

## Surprises & Discoveries

- Observation: the working tree already contains unrelated UI changes and new untracked UI files, including `src/xs2n/ui/run_arguments.py`, which overlaps the shared-arguments work for this feature.
  Evidence: `git status --short` shows existing modifications and untracked UI files before the feature work started.

- Observation: the active report surface in this workspace had already moved to `report issues`, `report render`, and an issue-based `report latest`, even though earlier docs and assumptions still referred to the older digest-only flow.
  Evidence: `tests/test_report_cli.py` and `tests/test_report_digest.py` treated issue artifacts and `digest.html` as the current behavior under test.

## Decision Log

- Decision: stay in the current workspace instead of creating a new git worktree.
  Rationale: the relevant UI argument files already have local uncommitted changes, so a fresh worktree from `HEAD` would hide part of the current project state and increase merge risk.
  Date/Author: 2026-03-18 / Codex

- Decision: keep the v1 scope portable and export-only for OS integrations.
  Rationale: this preserves the “slim” goal while still making cron, launchd, and systemd user timers first-class targets.
  Date/Author: 2026-03-18 / Codex

- Decision: integrate `report schedule` with the newer issue-based `report latest` flow instead of trying to preserve the older digest-only path as the schedule target.
  Rationale: the working tree and test suite now treat the issue-based flow as the real user-facing contract, so scheduling had to follow that truth to avoid building against a dead surface.
  Date/Author: 2026-03-18 / Codex

## Outcomes & Retrospective

The feature is implemented and verified. `xs2n report schedule` now stores named definitions in `data/report_schedules.json`, exports install-ready scheduler material for `cron`, `launchd`, and `systemd`, and runs saved schedules through `xs2n report schedule run <name>` with overlap protection, timestamped logs, and `last_run` bookkeeping.

The main implementation twist was contextual rather than architectural: the branch had already shifted from an older `digest`-centric report flow to a newer issue-based `issues` / `render` / `latest` flow. Instead of fighting that drift, the shared runtime and schedule runner were wired to the newer flow. The result is simpler and more honest: there is now one real “latest report” contract, and the scheduler reuses it.

## Context and Orientation

The current CLI entrypoint is `src/xs2n/cli/cli.py`, which registers the `report` group from `src/xs2n/cli/report.py`. In this workspace, the active report surface is issue-based: `xs2n report issues`, `xs2n report render`, and `xs2n report latest`. The latest flow resolves a `since` window, calls `run_timeline_ingestion(...)` from `src/xs2n/cli/timeline.py`, snapshots `timeline_window.json`, builds issue artifacts, and renders `digest.html`.

The reusable latest-run arguments and orchestration now live in `src/xs2n/report_runtime.py`, so `report latest` and `report schedule run` share one runtime contract.

The new schedule source of truth should be a JSON document under `data/report_schedules.json`, following the same style as `src/xs2n/storage/report_state.py`. Reusable schedule data contracts should live under `src/xs2n/schemas/`, not inside the CLI layer.

## Plan of Work

First, write failing tests for a shared runtime helper that runs the current `report latest` flow from a plain Python arguments object, and for the new `report schedule` CLI commands. Keep the tests in the existing direct-call style already used in `tests/test_report_cli.py`.

Second, extract the reusable `report latest` runtime into a neutral module and update `src/xs2n/cli/report.py` to become a thin Typer boundary that passes its module-level call targets into the shared helper. This preserves monkeypatch-friendly direct-call CLI tests while still giving the schedule runner one honest runtime path.

Third, add the `report_schedule` subsystem with four focused responsibilities: schedule catalog access, schedule execution with lock and run bookkeeping, target export rendering, and CLI wiring. The runner must create `data/report_schedule_locks/<name>.lock` atomically, skip cleanly when the lock already exists, and write `last_run` back to the schedule catalog on both success and failure.

Fourth, update the user-facing docs in `README.md` and `docs/codex/autolearning.md`, then rerun the focused suite and the final verification commands.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, implement and verify with:

    uv run pytest tests/test_report_digest.py tests/test_report_runtime.py tests/test_report_schedule.py tests/test_report_schedule_storage.py tests/test_report_cli.py tests/test_ui_run_arguments.py tests/test_ui_run_preferences.py
    uv run pytest

After implementation, also inspect the CLI surface with:

    uv run xs2n report schedule --help
    uv run xs2n report schedule create demo --every-hours 6 --lookback-hours 24
    uv run xs2n report schedule export demo --target cron

Expected behavior:

- the focused suite passes with new schedule coverage,
- `report schedule --help` shows the new subcommands,
- `create` writes `data/report_schedules.json`,
- `export` prints a concrete cron, launchd, or systemd artifact without installing it.

## Validation and Acceptance

Acceptance is behavioral:

1. `xs2n report latest` still works through the new shared runtime helper and continues to produce issue artifacts plus `digest.html`.
2. `xs2n report schedule create/list/show/delete` manage `data/report_schedules.json`.
3. `xs2n report schedule run <name>` records `last_run` for success, failure, and lock-skip outcomes.
4. `xs2n report schedule export <name> --target cron|launchd|systemd` prints install-ready output.
5. A schedule created with `--cron` exports to `cron` and fails explicitly for `launchd` and `systemd`.

## Idempotence and Recovery

Re-running `create` with the same name should fail unless `--replace` is passed. Re-running `run` is safe because it uses a lock file and additive log/output paths. Re-running `export` is always safe because it only prints generated content.

If development is interrupted, resume from this document, update `Progress`, and continue with the next unchecked item. If a test reveals a design gap, record it in `Surprises & Discoveries` and `Decision Log` before changing direction.

## Artifacts and Notes

Primary files expected to change:

- `src/xs2n/cli/report.py`
- `src/xs2n/cli/report_schedule.py`
- `src/xs2n/cli/timeline.py`
- `src/xs2n/storage/report_schedules.py`
- `src/xs2n/schemas/report_schedule.py`
- `src/xs2n/report_runtime.py`
- `src/xs2n/report_schedule/`
- `src/xs2n/ui/run_arguments.py`
- `README.md`
- `docs/codex/autolearning.md`
- `tests/test_report_cli.py`
- `tests/test_report_schedule.py`
- `tests/test_report_schedule_storage.py`

## Interfaces and Dependencies

At the end of this milestone, the reusable report runtime must expose a plain-Python contract for the current end-to-end flow, and the CLI layer must only translate Typer options into that contract.

The new schedule schema must at least represent:

- `name`
- `cadence_kind`
- `time_local`
- `weekdays`
- `interval_hours`
- `cron_expression`
- `latest_arguments`
- `working_directory`
- `launcher_argv`
- `log_dir`
- `last_run`

The runner must persist `last_run.status`, `started_at`, `finished_at`, `exit_code`, `run_id`, `digest_path`, and `error_message`.
