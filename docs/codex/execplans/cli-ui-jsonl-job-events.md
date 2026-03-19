# CLI UI JSONL Job Events

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the desktop UI can launch long-running CLI commands and receive live progress updates without waiting for process exit or scraping ad-hoc human output. The CLI remains the installable, cron-friendly surface, while the UI reads one structured JSON object per stdout line and updates its own job state as phases and artifacts appear on disk.

The first target is the `report latest` flow because it is the primary run action in the desktop app. The same event contract should also work for the issue-only pipeline so the repository moves toward one honest engine contract instead of a UI that treats shell transcripts as state.

## Progress

- [x] (2026-03-19 10:05Z) Reviewed the current CLI/UI boundary, confirmed that the FLTK app still launches commands with `subprocess.run(...)`, and identified `src/xs2n/report_runtime.py` plus `src/xs2n/agents/digest/pipeline.py` as the right places to emit shared progress events.
- [x] (2026-03-19 10:12Z) Confirmed fresh reference material for `subprocess.Popen` incremental reads and retained the decision to keep machine-readable JSONL on stdout and human-readable logs on stderr when the CLI is in event-stream mode.
- [x] (2026-03-19 10:22Z) Wrote failing tests for the shared run-event schema, `report latest` JSONL output, and FLTK command-progress handling.
- [x] (2026-03-19 10:36Z) Implemented the shared run-event schema and wired event emission through `src/xs2n/report_runtime.py` and `src/xs2n/agents/digest/pipeline.py`.
- [x] (2026-03-19 10:47Z) Replaced the FLTK command runner in `src/xs2n/ui/app.py` with a `subprocess.Popen`-based reader that consumes JSONL events live, updates UI status, and still collects a final transcript.
- [x] (2026-03-19 10:50Z) Updated UI command builders and docs so the desktop app opts into JSONL streaming only for commands that support it.
- [x] (2026-03-19 10:58Z) Ran focused regression tests plus the full `uv run pytest -q` suite, then captured the architectural preference in `docs/codex/coding-preferences.md` and the implementation note in `docs/codex/autolearning.md`.

## Surprises & Discoveries

- Observation: `src/xs2n/report_runtime.py` already contains shared orchestration for `report latest`, but the FLTK app still shells out to the CLI and only refreshes by rescanning run folders after process exit.
  Evidence: `src/xs2n/ui/app.py` currently calls `subprocess.run(...)` inside `_start_command`, while `src/xs2n/report_runtime.py` already owns the reusable latest-report flow.

- Observation: the repository currently carries two separate `RunCommand` and latest-arguments contracts, one in the UI package and one in the runtime package.
  Evidence: `src/xs2n/report_runtime.py` defines `RunCommand` and `LatestRunArguments`, and `src/xs2n/ui/run_arguments.py` defines near-duplicate versions for the FLTK layer.

- Observation: direct unit tests that call Typer command functions without the CLI parser can receive `typer.Option(...)` metadata objects as default values instead of plain booleans.
  Evidence: the first implementation of `--jsonl-events` emitted JSONL during tests that never passed the flag explicitly, because the raw `OptionInfo` default was truthy until normalized.

## Decision Log

- Decision: implement structured event streaming as an opt-in CLI mode (`--jsonl-events`) instead of changing default stdout for all CLI use.
  Rationale: shell users and cron jobs should keep their current human-readable output, while the UI can explicitly request machine-readable JSONL and treat stdout as an event stream.
  Date/Author: 2026-03-19 / Codex

- Decision: keep the event schema in a neutral schema module rather than burying it inside the UI or the CLI command file.
  Rationale: the contract belongs to the shared runtime boundary between adapters, and future adapters such as FastAPI or Electron should be able to reuse it without importing FLTK code.
  Date/Author: 2026-03-19 / Codex

- Decision: make the desktop UI opt into event streaming by appending `--jsonl-events` in `src/xs2n/ui/run_arguments.py` instead of changing default CLI stdout for every invocation.
  Rationale: the repository still needs a human-friendly default CLI for shell and scheduler use, while the FLTK app can explicitly request a stricter machine-readable contract.
  Date/Author: 2026-03-19 / Codex

## Outcomes & Retrospective

The change shipped end to end. The CLI now has an explicit `--jsonl-events` mode for `report latest` and `report issues`, the shared runtime emits structured run progress, and the FLTK app consumes those events incrementally through `subprocess.Popen(...)` instead of waiting for command exit. The user-visible win is that the desktop UI can now show run progress and refresh run artifacts while the process is still active.

The work also established a cleaner boundary for later adapters. The event schema lives outside the UI, the runtime owns semantic progress, and the FLTK layer only owns process transport plus presentation. The remaining gap is broader consolidation of duplicate run-command argument contracts between `src/xs2n/report_runtime.py` and `src/xs2n/ui/run_arguments.py`, but that is now an independent cleanup rather than a blocker for live UI state.

## Context and Orientation

The current FLTK desktop browser lives in `src/xs2n/ui/app.py`. Its `_start_command` helper launches the CLI with `subprocess.run(...)` in a background thread, then updates the UI only when the command has fully exited. This means the UI can show a static “running” placeholder, but it does not have a live job-state model while the command is still working.

The primary command surface for the current product milestone is `xs2n report latest`, defined in `src/xs2n/cli/report.py`. That command already delegates the reusable orchestration to `src/xs2n/report_runtime.py`, which handles timeline ingestion, writes `timeline_window.json`, runs the issue pipeline, and renders `digest.html`.

The issue pipeline itself lives in `src/xs2n/agents/digest/pipeline.py`. That module already knows the run directory, run identifier, phases, and artifact paths. Those are exactly the pieces of state the UI should receive as structured events instead of rediscovering them later from free-form stdout.

The FLTK app also has a UI-only command-argument layer in `src/xs2n/ui/run_arguments.py`. That layer currently builds CLI argument lists but has no notion of whether a command should emit machine-readable progress. This plan adds that notion without changing the rest of the preferences UI.

## Plan of Work

Start by adding a new shared schema module under `src/xs2n/schemas/` that defines one progress event record. The record needs a small set of honest fields: the event type, a human-readable message, an optional run identifier, an optional phase name, an optional artifact path, and optional numeric counts. Keep the schema reusable and adapter-neutral.

Next, thread an optional event-emitter callback through `src/xs2n/report_runtime.py` and `src/xs2n/agents/digest/pipeline.py`. Emit events when a run starts, when a phase starts or completes, when an artifact is written, and when the issue run completes or fails. Keep existing human-facing `echo(...)` output intact for normal CLI usage.

Then update `src/xs2n/cli/report.py` so `report latest` and `report issues` can opt into JSONL event mode with a CLI flag. In that mode, emit JSONL event lines to stdout with flushing on every line, and route the existing human-readable status text to stderr so the UI never has to parse mixed output.

Finally, replace the FLTK command runner with `subprocess.Popen(...)` in `src/xs2n/ui/app.py`. Read stdout incrementally, parse JSONL events only for commands that opt into event streaming, update the status bar and selected run as events arrive, and still keep a final transcript for the viewer after completion. Use a final `refresh_runs()` as reconciliation, but no longer make that the only source of state.

## Concrete Steps

Work from the repository root `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Write failing tests that describe the new behavior.
   - `uv run pytest tests/test_report_runtime.py tests/test_report_digest.py tests/test_report_cli.py tests/test_ui_app.py tests/test_ui_run_arguments.py tests/test_ui_run_preferences.py -q`
   - Expect new assertions for event records, `--jsonl-events`, and FLTK progress handling to fail before the implementation exists.

2. Implement the event schema and emitters in:
   - `src/xs2n/schemas/run_events.py`
   - `src/xs2n/report_runtime.py`
   - `src/xs2n/agents/digest/pipeline.py`

3. Wire CLI event-mode output in:
   - `src/xs2n/cli/report.py`

4. Update the FLTK runner and UI command builders in:
   - `src/xs2n/ui/app.py`
   - `src/xs2n/ui/run_arguments.py`
   - `src/xs2n/ui/auth_commands.py` only if the shared `RunCommand` contract changes

5. Update docs and notes in:
   - `docs/codex/coding-preferences.md`
   - `docs/codex/autolearning.md`
   - this ExecPlan file

## Validation and Acceptance

Acceptance is behavioral, not structural.

From the repo root, run:

    uv run pytest tests/test_report_runtime.py tests/test_report_digest.py tests/test_report_cli.py tests/test_ui_app.py tests/test_ui_run_arguments.py tests/test_ui_run_preferences.py -q

The new tests must prove three things. First, the runtime and digest pipeline emit structured events with stable fields and run identifiers. Second, `xs2n report latest --jsonl-events` writes JSONL events to stdout while keeping human-readable guidance off stdout. Third, the FLTK app can consume queued progress events, update status text, and refresh/select the active run before process exit.

If a manual check is needed after tests pass, run:

    uv run xs2n report latest --lookback-hours 24 --jsonl-events

You should see one JSON object per line on stdout. Each line should be parseable JSON, and at least one line should contain the issue run identifier plus one or more artifact paths.

Recorded verification after implementation:

    uv run pytest tests/test_report_runtime.py tests/test_report_digest.py tests/test_report_cli.py tests/test_ui_app.py tests/test_ui_run_arguments.py tests/test_ui_run_preferences.py -q
    uv run pytest -q
    uv run xs2n report latest --help

## Idempotence and Recovery

This plan is additive. Re-running the focused tests is safe. Re-running `report latest` is already designed to create a new run directory. If the FLTK runner partially updates UI state before a command fails, the final command result and the post-run `refresh_runs()` remain the recovery path that reconciles the UI with on-disk truth.

If the JSONL stream breaks because a command prints non-JSON to stdout while event mode is enabled, treat that as a bug in the command contract, fix the emitter, and keep the UI parser strict rather than teaching the UI to guess.

## Artifacts and Notes

The most important artifact for this milestone is the shared event contract itself. The output must remain small and line-oriented so it can be tailed, piped, or consumed by the FLTK app without needing a custom protocol server.

Expected JSONL shape, shown here as an example rather than a final transcript:

    {"event":"phase_started","message":"Starting timeline ingestion.","phase":"timeline_ingestion"}
    {"event":"run_started","message":"Issue run 20260319T101500Z started.","run_id":"20260319T101500Z"}
    {"event":"artifact_written","message":"Wrote filtered threads artifact.","run_id":"20260319T101500Z","phase":"filter_threads","artifact_path":"data/report_runs/20260319T101500Z/filtered_threads.json"}

## Interfaces and Dependencies

Define a reusable Pydantic model in `src/xs2n/schemas/run_events.py` that the CLI can serialize with `model_dump_json()` and the UI can parse with `model_validate_json()`. Keep the interface intentionally small:

    class RunEvent(BaseModel):
        event: Literal["run_started", "phase_started", "phase_completed", "artifact_written", "run_completed", "run_failed"]
        message: str
        run_id: str | None = None
        phase: str | None = None
        artifact_path: str | None = None
        counts: dict[str, int] = Field(default_factory=dict)

`src/xs2n/report_runtime.py` and `src/xs2n/agents/digest/pipeline.py` should both accept an optional callback with this shape:

    Callable[[RunEvent], None]

`src/xs2n/ui/app.py` should treat that schema as the only machine-readable progress contract for streaming commands. It should not parse human log lines for state.

Revision note: created this ExecPlan on 2026-03-19 to guide the migration from blocking CLI launches to JSONL event streaming in the FLTK UI after the architectural review and user approval.

Revision note: updated on 2026-03-19 after implementation to record the shipped event schema, the Typer `OptionInfo` discovery, and the final verification evidence.
