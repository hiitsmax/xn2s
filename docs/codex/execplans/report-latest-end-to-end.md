# Report Latest End-To-End Command

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a user can run one command to produce a digest from the latest timeline data without manually chaining two commands. The new behavior is `xs2n report latest`, which first ingests timeline entries from onboarded sources (`data/sources.json`) and then renders a digest from `data/timeline.json`. This is designed to be easier to schedule in cron because the orchestration is now inside the CLI instead of external shell glue.

## Progress

- [x] (2026-03-08 21:10Z) Confirmed current gap: ingestion and digest are separate commands with no single end-to-end report command.
- [x] (2026-03-08 21:14Z) Pulled fresh Typer usage references from Context7 for current command-group patterns.
- [x] (2026-03-08 21:20Z) Implemented `xs2n report latest` in `src/xs2n/cli/report.py` with explicit orchestration: resolve since window, run timeline batch ingestion, then run digest generation.
- [x] (2026-03-08 21:24Z) Added deterministic tests in `tests/test_report_cli.py` for since-resolution, orchestration wiring, and digest runtime error propagation.
- [x] (2026-03-08 21:30Z) Ran focused validation: `uv run pytest tests/test_report_cli.py` (14 passed) and `uv run xs2n report latest --help`.
- [x] (2026-03-08 21:31Z) Ran full suite validation: `uv run pytest` (84 passed).
- [x] (2026-03-08 21:33Z) Committed implementation as `feat(cli): add report latest end-to-end command` (`b2db1e9`).

## Surprises & Discoveries

- Observation: Existing CLI tests mostly call command functions directly instead of Typer `CliRunner`.
  Evidence: `tests/test_report_cli.py` uses direct calls to `auth(...)` and `digest(...)`, so adding `latest(...)` tests in the same style keeps consistency and low test overhead.

- Observation: The existing `timeline(...)` command already has strong parameter defaults for rate-limit waiting and pacing.
  Evidence: `src/xs2n/cli/timeline.py` sets defaults such as `wait_on_rate_limit=True`, `slow_fetch_seconds=1.0`, and `page_delay_seconds=0.4`, so `report latest` can reuse those defaults by calling `timeline(...)` without introducing a second copy of those knobs.

## Decision Log

- Decision: Implement the end-to-end command under the existing `report` command group as `xs2n report latest`.
  Rationale: Users already look in `report` for digest-related workflows (`report auth`, `report digest`), and this keeps the navigation model obvious.
  Date/Author: 2026-03-08 / Codex

- Decision: Keep orchestration in one explicit function that directly calls `timeline(...)` then `run_digest_report(...)`.
  Rationale: This preserves top-to-bottom readability and avoids introducing pass-through wrappers that add no behavior.
  Date/Author: 2026-03-08 / Codex

- Decision: Support both `--since` and `--lookback-hours` with a small resolver helper.
  Rationale: `--since` supports deterministic reruns; `--lookback-hours` is easier for cron schedules.
  Date/Author: 2026-03-08 / Codex

## Outcomes & Retrospective

This milestone adds the missing single-command flow for “latest-to-digest” generation. The CLI now has an additive path that reuses hardened timeline ingestion and the existing digest pipeline, and all tests are green (`84 passed`). Remaining risk is operational, not structural: this still depends on X/Twikit behavior and valid auth cookies, so scheduled jobs should continue to monitor failures and retries.

## Context and Orientation

The user-facing CLI entrypoint is `src/xs2n/cli/cli.py`, which registers `report` via `app.add_typer(report_app, name="report")`. Report commands live in `src/xs2n/cli/report.py`.

In this repository, “timeline ingestion” means fetching posts/replies/retweets from X accounts and merging them into `data/timeline.json`; this behavior is implemented in `src/xs2n/cli/timeline.py` and storage helpers under `src/xs2n/storage/`.

“Digest generation” means running the thread-based digest pipeline from `src/xs2n/agents/digest/pipeline.py`, which writes a timestamped run folder under `data/report_runs/<run_id>/`.

Before this milestone, users needed two commands in sequence:

- `xs2n timeline --from-sources --since <iso>`
- `xs2n report digest`

This plan introduces one command that performs both steps consistently.

## Plan of Work

Update `src/xs2n/cli/report.py` by adding a new command function, `latest(...)`, under `@report_app.command("latest")`. Keep the function readable as direct orchestration:

1. Resolve the cutoff datetime using a helper `_resolve_latest_since(...)`.
2. Call `timeline(...)` with `from_sources=True` and the resolved `since` value.
3. Call `run_digest_report(...)` using the same digest options as `report digest`.
4. Print one final summary line with run id, counts, and digest path.

Add tests in `tests/test_report_cli.py`:

- resolver behavior with explicit `--since`;
- resolver behavior with `--lookback-hours`;
- orchestration wiring (timeline called once before digest call);
- digest runtime error surfacing as `typer.Exit(code=1)`.

Update `README.md` to document `xs2n report latest` and show both usage modes (`--lookback-hours` and `--since`).

Update `docs/codex/autolearning.md` with a new milestone note that captures what was added and why.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, implement and validate with:

    uv run pytest tests/test_report_cli.py
    uv run pytest
    uv run xs2n report latest --help

Expected help output should include the new subcommand and options for `--since` and `--lookback-hours`.

Expected runtime behavior (with valid cookies/auth and non-empty sources) is:

    Ingesting source timelines before digest generation (since <iso-datetime>).
    Processed <n> of <n> accounts ...
    Latest digest run <run_id>: loaded <n> threads, kept <n> threads, produced <n> issues. Saved markdown to data/report_runs/<run_id>/digest.md.

## Validation and Acceptance

Acceptance is behavioral:

1. `uv run xs2n report latest --help` shows the new command and parameters.
2. `tests/test_report_cli.py` passes with explicit coverage for resolver and orchestration behavior.
3. `uv run xs2n report latest --lookback-hours 24` performs both ingestion and digest generation in one command when environment prerequisites are present.
4. Existing commands (`xs2n report digest`, `xs2n timeline`) still behave unchanged.

## Idempotence and Recovery

The command is safe to rerun. Timeline merge storage is deduplicated by tweet id, and each digest run writes a new timestamped output directory. If a run fails during ingestion or digest generation, fix the underlying auth/network issue and rerun the same command. No destructive migration is involved in this milestone.

## Artifacts and Notes

Key changed files for this milestone:

- `src/xs2n/cli/report.py`
- `tests/test_report_cli.py`
- `README.md`
- `docs/codex/autolearning.md`
- `docs/codex/execplans/report-latest-end-to-end.md`

Context7 reference used:

- Typer command-group guidance from `/fastapi/typer` to confirm current subcommand patterns.

## Interfaces and Dependencies

`src/xs2n/cli/report.py` must expose:

    def _resolve_latest_since(*, since: str | None, lookback_hours: int, now: datetime | None = None) -> datetime:
        ...

    @report_app.command("latest")
    def latest(...):
        ...

The `latest(...)` command reuses existing interfaces without introducing new transport layers:

- `xs2n.cli.timeline.timeline(...)` for ingestion.
- `xs2n.agents.run_digest_report(...)` for digest generation.

Revision note (2026-03-08): Created this plan while implementing the new `report latest` milestone, then updated progress and acceptance sections so the document matches the actual shipped behavior and remaining validation tasks.
