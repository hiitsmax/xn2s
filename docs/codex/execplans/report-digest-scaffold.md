# Report Digest Scaffold

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a user can run `uv run xs2n report digest` and turn previously downloaded timeline data into a traceable markdown issue that reads like a compact magazine brief. The run produces a final `digest.md`, intermediate JSON artifacts for each step, and a lightweight `data/report_state.json` file so future runs can revisit heated threads instead of starting from scratch every time.

The user-visible proof is a new report command that reads `data/timeline.json`, writes a new folder under `data/report_runs/<run_id>/`, and prints a short summary that includes how many timeline entries were considered, how many conversation units were kept, how many issue sections were produced, and where the markdown digest was saved.

## Progress

- [x] (2026-03-07 13:20Z) Confirmed the current report CLI surface, timeline storage shape, and existing tests before editing.
- [x] (2026-03-07 13:33Z) Added engagement metrics to `TimelineEntry` extraction and persistence.
- [x] (2026-03-07 13:41Z) Updated timeline merge behavior so repeated imports refresh stored metrics for existing tweet IDs instead of freezing virality at first sighting.
- [x] (2026-03-07 13:52Z) Added `src/xs2n/storage/report_state.py` for heated-thread memory between digest runs.
- [x] (2026-03-07 14:00Z) Implemented the first report digest scaffold in `src/xs2n/agents/digest.py` and wired `xs2n report digest`.
- [x] (2026-03-07 14:06Z) Added digest tests, timeline metric tests, README usage docs, taxonomy starter config, and autolearning notes.
- [x] (2026-03-07 14:08Z) Validated the focused suite with `uv run pytest tests/test_timeline_storage.py tests/test_timeline_fetching.py tests/test_report_cli.py tests/test_report_digest.py`.

## Surprises & Discoveries

- Observation: The original timeline merge logic skipped duplicate tweet IDs entirely.
  Evidence: Virality and heated-thread tracking would never move forward after the first ingest because likes/retweets/replies/views on existing tweets would stay stale.

- Observation: Codex ChatGPT login is useful for the CLI bootstrap flow, but it does not expose a clean Python credential path for LangChain model calls.
  Evidence: `codex login status` reports `Logged in using ChatGPT`, while the CLI help exposes `--with-api-key` only for feeding the CLI itself.

- Observation: The current timeline document already contains enough thread metadata to support a first conversation-unit scaffold without reworking ingestion again.
  Evidence: Existing timeline entries carry `conversation_id`, `in_reply_to_tweet_id`, and `timeline_source`, which made it possible to build a candidate-bundling step immediately.

## Decision Log

- Decision: Keep the report scaffold as explicit step functions with JSON handoffs instead of a shared LangGraph state machine.
  Rationale: The user explicitly rejected shared graph-state complexity for v1 and wanted each step to stay separate and inspectable.
  Date/Author: 2026-03-07 / Codex

- Decision: Use LangChain structured output with a small backend interface and ship one real provider first: OpenAI via `langchain-openai`.
  Rationale: This keeps the scaffold runnable today while preserving room to add a Codex-CLI adapter or another provider later without reshaping the pipeline.
  Date/Author: 2026-03-07 / Codex

- Decision: Treat report state as first-class CLI-managed storage in `src/xs2n/storage/report_state.py`.
  Rationale: The repository already centralizes persisted CLI state under `src/xs2n/storage/`, so heated-thread memory belongs beside sources, timeline, and onboarding state.
  Date/Author: 2026-03-07 / Codex

- Decision: Refresh duplicate timeline entries in place during merge.
  Rationale: Engagement metrics are only useful for virality and momentum if later scrapes can update the stored values for tweets that were already seen before.
  Date/Author: 2026-03-07 / Codex

- Decision: Start with a mixed-brief markdown issue shape: top issues, heated-thread watch, and standout signals.
  Rationale: This matches the design discussion and leaves room to refine editorial voice later without changing the artifact pipeline.
  Date/Author: 2026-03-07 / Codex

## Outcomes & Retrospective

The scaffold now exists end-to-end: ingestion persists the virality inputs the digest needs, the report command generates a traceable markdown issue, and every run writes intermediate artifacts that make the pipeline debuggable. The biggest remaining gaps are editorial sophistication, delivery automation, and richer observability, but the repo now has a concrete base for those next steps instead of only design notes.

## Context and Orientation

`xs2n` is a Typer CLI under `src/xs2n/cli/`. Before this change, the `report` command group only exposed `xs2n report auth`, which delegated authentication to the external Codex CLI. Timeline ingestion lived in `src/xs2n/profile/timeline.py`, normalized tweet records into `TimelineEntry` instances in `src/xs2n/profile/types.py`, and stored them in `data/timeline.json` via helpers in `src/xs2n/storage/timeline.py`.

In this repository, “report scaffold” means the first runnable version of the digest pipeline, not a final editorial system. The scaffold should read the existing timeline document, select candidate conversation units, call an LLM for the semantic steps, write intermediate JSON artifacts, render a markdown issue, and remember heated threads for the next run. “Traceable” means every major section in the markdown digest must point back to the source tweet URLs that justified the summary.

## Plan of Work

First, extend the timeline model to preserve the engagement fields the digest needs: likes, retweets, replies, quotes, and views. While doing that, adjust merge behavior so repeated imports update existing tweet records rather than leaving stale numbers behind.

Second, add a new report-state storage helper so the digest pipeline has a dedicated place to persist the previous run time and per-thread heat metadata. This keeps report memory consistent with the repository’s existing storage package layout.

Third, implement the first digest agent scaffold in `src/xs2n/agents/digest.py`. The module should define the taxonomy loader, timeline-record parser, deterministic conversation candidate selection, the small LLM backend interface, the OpenAI/LangChain backend, step-by-step artifact writing, state updates, and markdown rendering. The CLI entrypoint in `src/xs2n/cli/report.py` should expose this through `xs2n report digest`.

Finally, add focused tests and user-facing docs. The tests should cover virality extraction, duplicate-refresh behavior, heated-thread carry-over, end-to-end digest artifact generation with a fake backend, and CLI failure/success behavior. The README should explain the new command and the need for `OPENAI_API_KEY`. The taxonomy starter file should be checked in so users have an editable default.

## Concrete Steps

Run these commands from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Run the focused validation suite:

       uv run pytest tests/test_timeline_storage.py tests/test_timeline_fetching.py tests/test_report_cli.py tests/test_report_digest.py

   Expect all listed tests to pass.

2. Run the full test suite:

       uv run pytest

   Expect the repository test suite to pass after the digest scaffold lands.

3. Exercise the new report command with a valid timeline file and OpenAI API key:

       export OPENAI_API_KEY=your_key_here
       uv run xs2n report digest --timeline-file data/timeline.json --taxonomy-file docs/codex/report_taxonomy.json

   Expect one new folder under `data/report_runs/` containing `digest.md`, `run.json`, and the step artifacts.

## Validation and Acceptance

Acceptance is behavioral:

Run `uv run xs2n report digest` with a valid `data/timeline.json` and `OPENAI_API_KEY`. The command should print a one-line summary ending with the path to `digest.md`. The run directory should include `selected_entries.json`, `candidates.json`, `assembled_units.json`, `categorized_units.json`, `filtered_units.json`, `signals.json`, `issues.json`, `run.json`, and `digest.md`.

Inspect the markdown digest. It should contain the sections `Top Issues`, `Heated Threads Watch`, and `Standout Signals`, and each kept unit should expose source links back to X tweet URLs.

Re-run timeline ingestion on the same tweets after their public engagement counts change. The next saved `data/timeline.json` should refresh those metrics in place, and a subsequent digest run should be able to compare the newer heat score against the prior report state instead of reusing stale numbers.

## Idempotence and Recovery

The digest command is additive and safe to rerun. Each run creates a new timestamped folder under `data/report_runs/` and overwrites only `data/report_state.json`. If a run fails before writing `digest.md`, the partial run folder can be deleted and the command rerun safely.

The taxonomy file is editable. If `docs/codex/report_taxonomy.json` is missing, the scaffold falls back to the built-in starter taxonomy baked into `src/xs2n/agents/digest.py`.

## Artifacts and Notes

The most important runtime artifacts are:

- `data/report_runs/<run_id>/selected_entries.json`: timeline entries selected for this run by freshness window or heated-thread carry-over.
- `data/report_runs/<run_id>/candidates.json`: conversation candidate bundles before LLM assembly.
- `data/report_runs/<run_id>/signals.json`: the kept, signal-bearing conversation units with heat metadata.
- `data/report_runs/<run_id>/digest.md`: the final markdown issue.

## Interfaces and Dependencies

`src/xs2n/profile/types.py` must expose `TimelineEntry` with the added optional engagement fields:

    favorite_count: int | None
    retweet_count: int | None
    reply_count: int | None
    quote_count: int | None
    view_count: int | None

`src/xs2n/storage/report_state.py` must expose:

    DEFAULT_REPORT_STATE_PATH = Path("data/report_state.json")
    load_report_state(path: Path | None = None) -> dict[str, Any]
    save_report_state(doc: dict[str, Any], path: Path | None = None) -> None

`src/xs2n/agents/digest.py` must expose:

    run_digest_report(...)
    class OpenAIDigestBackend
    @dataclass class DigestRunResult

The Python model integration uses `langchain-openai` and expects `OPENAI_API_KEY` to be available in the environment. The scaffold uses LangChain structured output (`with_structured_output`) for semantic steps and deterministic Python code for numeric scoring and run-state management.

Revision note (2026-03-07): Added the completed digest scaffold implementation details, validation commands, and the duplicate-refresh discovery so the plan stays restartable from the checked-in state.
