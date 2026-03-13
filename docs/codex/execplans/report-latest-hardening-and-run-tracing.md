# Report Latest Hardening And Digest Run Tracing

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, `xs2n report latest` should be safe to use as the real one-command cron entrypoint instead of only looking correct in unit tests. A user should also be able to open one run directory and understand what happened in each digest phase, which model calls ran, how long they took, and where a failure happened if the run stopped midway.

The visible proof is:

- `uv run xs2n report latest ...` no longer crashes with a `TypeError` from Typer option defaults.
- each digest run directory contains the existing stage snapshots plus a frozen `taxonomy.json`, a per-phase execution trace, and per-call LLM trace files.
- failed or partial runs leave enough artifacts behind to explain the stopping point.

## Progress

- [x] (2026-03-13 00:25Z) Reproduced the `report latest --home-latest` failure locally and confirmed the traceback ends in `TypeError: '>' not supported between instances of 'OptionInfo' and 'int'`.
- [x] (2026-03-13 00:28Z) Inspected the current CLI and digest pipeline code paths and identified the two concrete gaps: CLI-to-CLI invocation in `report.latest(...)` and missing run-level execution traces in the digest pipeline.
- [x] (2026-03-13 00:31Z) Pulled fresh Context7 references for Typer command boundaries and OpenAI Python response/request identifiers.
- [x] (2026-03-13 00:38Z) Implemented `run_timeline_ingestion(...)`, routed `report.latest(...)` through it, and added regression tests for helper defaults plus report orchestration.
- [x] (2026-03-13 00:43Z) Added `taxonomy.json`, `phases.json`, `llm_calls/*.json`, and incremental `run.json` status updates to digest runs, including partial-failure recording.
- [x] (2026-03-13 00:47Z) Fixed the shared JSON serializer to support `datetime` values after the new `run.json` payload exposed that gap.
- [x] (2026-03-13 00:50Z) Ran focused validation: `uv run pytest tests/test_report_cli.py tests/test_timeline_cli.py tests/test_report_digest.py tests/test_report_llm.py` (`45 passed`).
- [x] (2026-03-13 00:51Z) Ran full-suite validation: `uv run pytest` (`94 passed`).
- [x] (2026-03-13 00:55Z) Verified live behavior in two ways: a full `report latest --home-latest` run now gets through ingestion and writes incremental trace artifacts, and a trimmed real-model digest run completed with the new artifact set in `data/report_runs_subset/20260313T003317Z/`.

## Surprises & Discoveries

- Observation: `tests/test_report_cli.py` masked the `report latest` bug because it stubbed `xs2n.cli.report.timeline` directly instead of exercising the plain Python behavior of omitted Typer defaults.
  Evidence: the real run crashed immediately, while the test suite stayed green.

- Observation: the digest pipeline already preserves the transformed thread state at every phase, so the real observability gap is execution metadata rather than missing semantic outputs.
  Evidence: each run already writes `threads.json`, `categorized_threads.json`, `filtered_threads.json`, `processed_threads.json`, `issue_assignments.json`, `issues.json`, and `digest.md`, but `run.json` only stores counts and paths.

- Observation: the new run-summary payload exposed a missing serializer rule for `datetime` objects in `src/xs2n/agents/digest/helpers.py`.
  Evidence: the first focused test pass failed with `TypeError: Object of type datetime is not JSON serializable` while writing `run.json`.

- Observation: `report latest` still feeds the entire accumulated `data/timeline.json` into the digest after ingesting a new lookback window.
  Evidence: the live Home->Following run added only one fresh entry but then loaded `506` threads into the digest because the timeline file already contained prior history.

- Observation: externally terminated runs can leave `run.json` in `running` state.
  Evidence: a manually stopped long-running live run preserved useful partial `phases.json` and `llm_calls/` artifacts, but `run.json` did not transition to `failed` because the process was terminated outside Python exception handling.

## Decision Log

- Decision: fix the `report latest` bug by extracting a plain Python ingestion helper from `src/xs2n/cli/timeline.py` and reusing it from both CLI entrypoints.
  Rationale: this keeps control flow obvious and avoids passing Typer `OptionInfo` objects across runtime boundaries.
  Date/Author: 2026-03-13 / Codex

- Decision: keep the current phase snapshot files exactly as they are and add observability with additive artifacts instead of replacing the existing run folder layout.
  Rationale: the current artifacts are already useful for inspecting transformed data, so the smallest safe improvement is to add execution trace files around them.
  Date/Author: 2026-03-13 / Codex

- Decision: log LLM call traces as separate JSON files under a dedicated run subdirectory instead of inlining every call payload into `run.json`.
  Rationale: per-call trace files keep `run.json` readable while still making each phase debuggable.
  Date/Author: 2026-03-13 / Codex

## Outcomes & Retrospective

The primary objective is met. `xs2n report latest` no longer crashes on the Typer option-boundary bug, and digest run directories are now materially more understandable because they record status, timing, per-phase counts, frozen taxonomy, and per-call model traces.

The live validation also surfaced one remaining product gap: “latest” currently describes the ingestion window, not the digest scope. In practice, a long-lived `data/timeline.json` can make `report latest` much slower than expected because the digest still reads the whole accumulated file. That did not block this hardening milestone, but it is the next operational issue to solve if the command is meant to stay cron-friendly on an active timeline.

## Context and Orientation

The `report` command group lives in `src/xs2n/cli/report.py`. The failing code path is the `latest(...)` command, which currently resolves a `since` timestamp and then calls the Typer-decorated `timeline(...)` function from `src/xs2n/cli/timeline.py` before calling `run_digest_report(...)`.

In this repository, “timeline ingestion” means fetching X posts and merging them into `data/timeline.json`. The implementation lives in `src/xs2n/cli/timeline.py`, which wraps lower-level fetch helpers from `src/xs2n/profile/timeline.py` and storage helpers from `src/xs2n/storage/`.

The digest pipeline lives in `src/xs2n/agents/digest/pipeline.py`. It loads threads from `data/timeline.json`, runs four LLM-backed semantic phases plus one markdown render phase, and writes a timestamped folder under `data/report_runs/<run_id>/`.

The current digest run folder is strong on semantic snapshots and weak on execution metadata. There is no frozen taxonomy copy, no timing per phase, no per-call LLM trace, and no explicit failure artifact when a run stops before `run.json` is written successfully.

## Plan of Work

First, update `src/xs2n/cli/timeline.py` so the real ingestion logic sits in a plain helper with normal Python defaults. Keep the `timeline(...)` command as the CLI boundary that parses Typer options and forwards them into the helper. Then update `src/xs2n/cli/report.py` so `latest(...)` uses the plain helper instead of calling the CLI wrapper.

Second, extend the digest pipeline in `src/xs2n/agents/digest/` without changing its top-to-bottom structure. The pipeline should still read like the real runtime order, but it should also:

- write `taxonomy.json` into each run directory as a frozen copy of the loaded taxonomy,
- write `run.json` immediately with a running status and update it again on success or failure,
- record one `phases.json` artifact with timing, counts, statuses, and artifact paths for each phase,
- write one JSON file per LLM call with prompt, payload, schema, structured result, response id, request id, duration, and error details when applicable.

Third, update the digest schemas or helper modules only as needed to support these additive artifacts. Avoid moving semantic behavior into the LLM transport; the steps should continue to own their prompts and meanings, while the LLM wrapper only records transport metadata around the request.

Fourth, update tests in `tests/test_report_cli.py` and `tests/test_report_digest.py` so they assert the repaired CLI boundary and the new run-artifact trace. Update `README.md` and `docs/codex/autolearning.md` to describe the new behavior and artifact set.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, implement and validate with:

    uv run pytest tests/test_report_cli.py tests/test_report_digest.py
    uv run pytest
    uv run xs2n report latest --home-latest --lookback-hours 24 --model gpt-5.4

The expected success transcript for the live command is:

    Ingesting Home->Following latest timeline before digest generation (since <iso-datetime>).
    Home latest timeline: scanned <n> items ...
    Latest digest run <run_id>: loaded <n> threads, kept <n> threads, produced <n> issues. Saved markdown to data/report_runs/<run_id>/digest.md.

The expected run directory should now also include:

    taxonomy.json
    phases.json
    llm_calls/<phase>_<thread-or-issue>.json

If the live run fails because X or model auth rejects the request, `run.json` and `phases.json` should still explain the last completed phase and the error message.

Actual validation this milestone produced:

    uv run pytest
    94 passed, 215 warnings in 6.38s

    uv run xs2n report latest --home-latest --lookback-hours 24 --model gpt-5.4
    Ingesting Home->Following latest timeline before digest generation (since 2026-03-12T00:30:39.880455+00:00).
    Scanned 500 Home->Following timeline items. Matched 500 items since 2026-03-12T00:30:39.880455+00:00 (skipped 0 older items). Added 1, skipped 499 duplicates. Saved to data/timeline.json.

The full live run was intentionally stopped after confirming that the repaired command wrote partial trace artifacts incrementally, because the digest was processing the entire historical timeline file rather than only the new lookback window.

To inspect a completed real-model run with the new artifact set, this milestone also used:

    jq '{entries: (.entries | sort_by(.created_at) | reverse | .[:12])}' data/timeline.json > data/latest_subset.json
    uv run xs2n report digest --timeline-file data/latest_subset.json --output-dir data/report_runs_subset --model gpt-5.4

Observed transcript:

    Digest run 20260313T003317Z: loaded 12 threads, kept 0 threads, produced 0 issues. Saved markdown to data/report_runs_subset/20260313T003317Z/digest.md.

## Validation and Acceptance

Acceptance is behavioral:

1. `uv run pytest tests/test_report_cli.py tests/test_report_digest.py` passes with new coverage for the plain ingestion helper boundary and the new artifact files.
2. `uv run pytest` stays green.
3. `uv run xs2n report latest --home-latest --lookback-hours 24 --model gpt-5.4` no longer crashes with a Typer `OptionInfo` error.
4. A successful digest run folder contains the previous semantic snapshots plus `taxonomy.json`, `phases.json`, and per-call LLM trace files.
5. A partial failure leaves `run.json` in a failed state with the stopping phase and error details instead of silently disappearing.

Acceptance status at the end of this milestone:

1. Passed. The focused suite and the full suite are green.
2. Passed. `report latest --home-latest` now gets through ingestion instead of crashing on `OptionInfo`.
3. Passed. Completed runs contain the new artifact set, and partial runs write enough trace data to debug progress.
4. Partially passed. Python exceptions are recorded cleanly as failed runs, but process-level external termination still leaves `run.json` in `running` state.

## Idempotence and Recovery

The code changes are additive and safe to rerun. Timeline ingestion is already deduplicated by tweet id, and each digest run uses a new timestamped directory. If the live run fails because X rate limits or auth expires, fix the environmental issue and rerun the same command; the failed run directory should remain useful for debugging and does not need manual cleanup.

## Artifacts and Notes

Context7 references used in this milestone:

- `/fastapi/typer` for the reminder that Typer command signatures are CLI parsing boundaries rather than reusable runtime APIs.
- `/openai/openai-python` for response/request identifier logging (`response.id` and `response._request_id`) and stream final-response access.

Primary files expected to change:

- `src/xs2n/cli/report.py`
- `src/xs2n/cli/timeline.py`
- `src/xs2n/agents/digest/pipeline.py`
- `src/xs2n/agents/digest/llm.py`
- `src/xs2n/schemas/digest.py`
- `tests/test_report_cli.py`
- `tests/test_report_digest.py`
- `README.md`
- `docs/codex/autolearning.md`
- `docs/codex/execplans/report-latest-hardening-and-run-tracing.md`

Key observed artifact directories from this milestone:

- `data/report_runs/20260313T003056Z/` for an incremental live Home->Following run that proved partial traces appear during long execution.
- `data/report_runs_subset/20260313T003317Z/` for a completed real-model digest run with the new artifact layout.

## Interfaces and Dependencies

At the end of this milestone, `src/xs2n/cli/timeline.py` should expose one plain runtime helper that can be safely called from Python without Typer parsing in the loop. The exact name can be `run_timeline(...)` or another honest name, but it must accept concrete Python values, not `typer.Option(...)` objects.

`src/xs2n/agents/digest/llm.py` should continue to expose the thin `DigestLLM.run(...)` entrypoint. If call tracing requires extra metadata, extend this entrypoint with additive parameters such as the phase name and item id; do not move categorization, filtering, or issue semantics into the transport layer.

`src/xs2n/agents/digest/pipeline.py` must still orchestrate the phases in the real runtime order from top to bottom, but it must also persist enough metadata to explain progress, timings, and failures for each run.

Revision note (2026-03-13): Created this plan after reproducing the live `report latest` failure and auditing the current run artifacts so the implementation can proceed with both reliability and observability goals in one place.

Revision note (2026-03-13, later): Updated this plan after implementation and validation to reflect the shipped helper split, the new digest trace artifacts, the serializer fix discovered during tests, and the remaining live-run scope/termination caveats.
