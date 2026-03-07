# Report Digest Scaffold

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a user can run `uv run xs2n report digest` on the existing `data/timeline.json` file and get a traceable markdown issue that organizes the captured X/Twitter threads into a compact, readable digest. The key visible behavior is that the command now follows a very small pipeline: load threads from the timeline file, categorize them, filter them, extract the signal from the kept threads, assign them to issues, and render a markdown issue. Each step writes a JSON artifact so the run stays inspectable.

## Progress

- [x] (2026-03-07 13:20Z) Confirmed the current report CLI surface, timeline storage shape, and existing tests before editing.
- [x] (2026-03-07 13:33Z) Added engagement metrics to `TimelineEntry` extraction and persistence.
- [x] (2026-03-07 13:41Z) Updated timeline merge behavior so repeated imports refresh stored metrics for existing tweet IDs instead of freezing virality at first sighting.
- [x] (2026-03-07 14:00Z) Implemented the first runnable digest scaffold and wired `xs2n report digest`.
- [x] (2026-03-07 14:28Z) Flattened the first refactor back down to the simpler digest-package shape after the earlier split was too abstract for the feature size.
- [x] (2026-03-07 16:10Z) Reworked the digest package again so `pipeline.py` now calls five explicit step files: `load_threads.py`, `categorize_threads.py`, `filter_threads.py`, `process_threads.py`, and `group_issues.py`.
- [x] (2026-03-07 16:18Z) Removed the stateful selection/assembly path from the active digest command so it now operates directly on thread bundles derived from `timeline.json`.
- [x] (2026-03-07 16:24Z) Updated report tests, CLI docs, and autolearning notes to match the simpler thread-first pipeline.
- [x] (2026-03-07 16:27Z) Validated the focused digest suite with `uv run pytest tests/test_report_digest.py tests/test_report_cli.py` and `uv run xs2n report digest --help`.
- [x] (2026-03-07 16:31Z) Ran the full repository suite with `uv run pytest` after the simplification.
- [x] (2026-03-07 16:42Z) Renamed the thin model wrapper from `OpenAIDigestAgent` to `DigestLLM`, moved it to `llm.py`, and removed the stale `backend` vocabulary from the digest pipeline.
- [x] (2026-03-07 16:55Z) Extracted the digest schemas into the new root-level schema module so the pipeline no longer owns the Pydantic/data classes.
- [x] (2026-03-07 17:02Z) Renamed the root-level digest schema package from `src/xs2n/models/` to `src/xs2n/schemas/` so the package name matches the role more clearly.
- [x] (2026-03-07 17:06Z) Revalidated the package rename with `uv run pytest tests/test_report_digest.py tests/test_report_cli.py`, `uv run xs2n report digest --help`, and `uv run pytest`.
- [x] (2026-03-07 17:12Z) Renamed the thread-level raw-output step from `extract_signals.py` to `process_threads.py` and updated the digest artifact name to `processed_threads.json`.
- [x] (2026-03-07 17:18Z) Moved the five digest step modules into `src/xs2n/agents/digest/steps/` and rewired imports/metadata to match.

## Surprises & Discoveries

- Observation: The user’s objection was not only about file count; it was really about control flow.
  Evidence: The simpler design became much clearer once the digest stopped pretending it needed stateful selection and “assembly” before it had even loaded the thread units the timeline command already provides.

- Observation: The current timeline document is already rich enough to be the only input contract for the digest.
  Evidence: `conversation_id`, `in_reply_to_tweet_id`, reply records, and persisted engagement metrics were enough to build thread bundles directly from `data/timeline.json`.

- Observation: LangChain structured output still fits the simpler design cleanly.
  Evidence: A single generic LLM wrapper using `ChatOpenAI.with_structured_output(..., method="json_schema")` works well when each step file loops over threads and asks for one schema at a time.

## Decision Log

- Decision: Keep the active digest architecture to one orchestrator plus five step files.
  Rationale: This matches the user’s requested mental model exactly: one simple pipeline method, five methods that call five separate step files, and one generic agent used inside the semantic steps.
  Date/Author: 2026-03-07 / Codex

- Decision: Drop the stateful “selected entries / assembled units / heated thread memory” path from the active digest command.
  Rationale: The user explicitly asked to start from the threads already captured by the timeline command, so the digest should consume that file directly instead of layering more orchestration first.
  Date/Author: 2026-03-07 / Codex

- Decision: Keep deterministic code only for what is mechanical: thread loading, JSON writing, virality scoring, and markdown rendering.
  Rationale: This preserves the user’s preference for agentic semantic steps while still keeping measurable logic out of the model.
  Date/Author: 2026-03-07 / Codex

- Decision: Use one generic OpenAI/LangChain LLM wrapper instead of one backend class with per-step methods.
  Rationale: The user asked for one thin model interface that each step can call with a prompt and schema, so the code now exposes exactly that shape.
  Date/Author: 2026-03-07 / Codex

- Decision: Rename the thin model client from “agent” to “LLM.”
  Rationale: The wrapper only sends structured prompts to the model and returns typed results; the step files are the agentic units, while the wrapper itself is just the model interface.
  Date/Author: 2026-03-07 / Codex

- Decision: Move the digest schemas into a root-level schemas package.
  Rationale: The user wanted the Pydantic-heavy data definitions separated from the digest package internals, and `schemas` describes these validation/IO shapes more clearly than `models`.
  Date/Author: 2026-03-07 / Codex

- Decision: Name the thread-level semantic operation `process_threads`, not `extract_signals`.
  Rationale: The main operation is processing a thread and returning its raw thread-level output. “Signal” is one field inside that output, not the identity of the whole step.
  Date/Author: 2026-03-07 / Codex

## Outcomes & Retrospective

The digest feature is still a scaffold, but it is now a much cleaner scaffold. A run reads one timeline file, groups source-authored conversations into thread units, sends each thread through clear semantic steps, and writes both the intermediate artifacts and the final markdown issue. The biggest lesson from this iteration is that a young pipeline benefits more from obvious control flow than from abstraction that anticipates future needs too early.

## Context and Orientation

`xs2n` is a Typer CLI under `src/xs2n/cli/`. The timeline ingestion command lives in `src/xs2n/cli/timeline.py` and stores flat tweet records in `data/timeline.json` via `src/xs2n/storage/timeline.py`. Those records include thread context fields such as `conversation_id`, reply linkage, and engagement metrics.

The active digest code lives under `src/xs2n/agents/digest/`, but the digest schemas now live in the root-level `src/xs2n/schemas/digest.py` module. In the current design, `pipeline.py` owns the JSON helpers, the markdown rendering, and the top-level `run_digest_report(...)` orchestrator. `llm.py` owns the single generic OpenAI/LangChain structured-output model wrapper. The five step files are:

- `src/xs2n/agents/digest/steps/load_threads.py`
- `src/xs2n/agents/digest/steps/categorize_threads.py`
- `src/xs2n/agents/digest/steps/filter_threads.py`
- `src/xs2n/agents/digest/steps/process_threads.py`
- `src/xs2n/agents/digest/steps/group_issues.py`

When this document says “thread,” it means one conversation bundle grouped from `timeline.json` by `conversation_id`, keeping only conversations that contain at least one source-authored tweet. Outside replies already present in the timeline file stay attached as context inside that bundle.

## Plan of Work

First, keep the ingestion-side engagement metrics already added to `TimelineEntry` and timeline persistence so virality remains available during digest generation.

Second, make the digest input contract as small as possible. `src/xs2n/agents/digest/steps/load_threads.py` should read `data/timeline.json`, validate the entries into `TimelineRecord`, group them by conversation, discard conversations that do not contain any source-authored tweet, and emit `ThreadInput` objects sorted by recency.

Third, keep the semantic steps explicit and separate. `src/xs2n/agents/digest/steps/categorize_threads.py`, `filter_threads.py`, `process_threads.py`, and `group_issues.py` should each expose a `run(...)` function. Inside those files, loop over threads one by one and call the single generic LLM wrapper in `src/xs2n/agents/digest/llm.py` with a prompt, a JSON payload, and a Pydantic schema.

Fourth, make `src/xs2n/agents/digest/pipeline.py` intentionally boring. It should not define the digest schemas anymore; those belong in `src/xs2n/schemas/digest.py`. `pipeline.py` should only define helper functions like `virality_score(...)`, markdown rendering, and `run_digest_report(...)`. The report command should write these artifacts per run: `threads.json`, `categorized_threads.json`, `filtered_threads.json`, `processed_threads.json`, `issue_assignments.json`, `issues.json`, `run.json`, and `digest.md`.

Finally, keep the CLI small. `src/xs2n/cli/report.py` should accept `--timeline-file`, `--output-dir`, `--taxonomy-file`, and `--model`, then print a one-line summary of loaded threads, kept threads, produced issues, and the digest path.

## Concrete Steps

Run these commands from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Validate the focused digest suite:

       uv run pytest tests/test_report_digest.py tests/test_report_cli.py

   Expect the report tests to pass.

2. Check the user-facing CLI shape:

       uv run xs2n report digest --help

   Expect the help output to list only `--timeline-file`, `--output-dir`, `--taxonomy-file`, and `--model` for the digest command.

3. Run the full test suite:

       uv run pytest

   Expect the repository suite to pass after the simplification.

## Validation and Acceptance

Acceptance is behavioral.

Run `uv run xs2n report digest --timeline-file data/timeline.json --taxonomy-file docs/codex/report_taxonomy.json` with `OPENAI_API_KEY` exported. The command should print a one-line summary ending with the saved `digest.md` path. The run directory under `data/report_runs/<run_id>/` should contain `threads.json`, `categorized_threads.json`, `filtered_threads.json`, `processed_threads.json`, `issue_assignments.json`, `issues.json`, `run.json`, and `digest.md`.

Open the markdown digest. It should contain at least `Top Issues` and `Standout Threads`, and each kept thread should include source links pointing back to tweet URLs.

Run `uv run pytest`. The report tests should confirm that thread loading groups conversations correctly, virality scoring still prefers larger engagement signals, and the simplified fake-agent end-to-end digest run writes the expected artifacts.

## Idempotence and Recovery

The digest command is additive and safe to rerun. Each run creates a new timestamped folder under `data/report_runs/`. If a run fails partway through, delete the partial run folder and rerun the command.

If `docs/codex/report_taxonomy.json` is missing, the digest code falls back to the built-in starter taxonomy in `src/xs2n/agents/digest/pipeline.py`.

## Artifacts and Notes

The most important runtime artifacts are:

- `data/report_runs/<run_id>/threads.json`: thread bundles derived directly from `timeline.json`
- `data/report_runs/<run_id>/processed_threads.json`: kept threads with processed thread output fields and virality scores
- `data/report_runs/<run_id>/issues.json`: grouped issue sections derived from the signal threads
- `data/report_runs/<run_id>/digest.md`: the final markdown issue

## Interfaces and Dependencies

`src/xs2n/agents/digest/llm.py` must expose:

    class DigestLLM:
        def run(self, *, prompt: str, payload: Any, schema: type[BaseModel]) -> BaseModel: ...

`src/xs2n/agents/digest/pipeline.py` must expose:

    run_digest_report(...)
    def virality_score(record: TimelineRecord) -> float

`src/xs2n/schemas/digest.py` must expose:

    @dataclass class DigestRunResult
    class TimelineRecord(BaseModel)
    class TaxonomyConfig(BaseModel)
    class ThreadInput(BaseModel)

The model integration uses `langchain-openai` and expects `OPENAI_API_KEY` to be available in the environment. The structured-output pattern should use `ChatOpenAI.with_structured_output(..., method="json_schema")`, which is the current supported LangChain integration for returning Pydantic objects from model calls.

Revision note (2026-03-07): Rewrote this ExecPlan to match the simplified thread-first digest architecture after the earlier stateful scaffold and heavier abstractions proved misaligned with the user’s requested shape.
