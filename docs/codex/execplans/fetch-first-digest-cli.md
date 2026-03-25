# Fetch-First Digest CLI

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the repository will expose one digest CLI that starts by fetching tweets from the tracked handles list and only then runs the digest workflow. A user will no longer prepare a manual thread JSON file. They will run one command, the command will collect recent tweets, shape them into the application's thread model, send those threads through the digest pipeline, and write `digest.json`.

## Progress

- [x] (2026-03-25 23:12Z) Confirmed the desired cut with the user: no manual `--input-file` fallback, one CLI, fetch-first flow, and domain models named `Thread` and `Post`.
- [x] (2026-03-25 23:14Z) Wrote failing tests for the new domain-model and CLI contract and watched them fail on the old `PostInput`/`ThreadInput` names and `--input-file` runtime.
- [x] (2026-03-25 23:15Z) Refactored the thread schema, tweet fetching module, pipeline entrypoint, and runner script to the fetch-first flow.
- [x] (2026-03-25 23:16Z) Updated `README.md` and `docs/codex/autolearning.md` to match the new runtime contract.
- [x] (2026-03-25 23:18Z) Ran the focused test suite and `uv run python scripts/run_agentic_pipeline.py --help`; all relevant checks passed.

## Surprises & Discoveries

- Observation: The current branch still contains a `src/xs2n/agents/` package even though earlier notes described a flatter package shape.
  Evidence: `find src -maxdepth 3 -type f | sort` lists `src/xs2n/agents/llm.py`, `src/xs2n/agents/pipeline.py`, and `src/xs2n/agents/schemas.py`.

- Observation: `ntscraper` does not want a raw Python `datetime` for `since`; it validates a `YYYY-MM-DD` string internally.
  Evidence: Reading the installed source for `Nitter.get_tweets()` and `_search()` showed the library appends `since=<date>` only after `_check_date_validity()` accepts the value.

- Observation: Instantiating `Nitter(...)` at module import made the CLI `--help` path perform network-ish setup before the user asked to fetch anything.
  Evidence: The first `uv run python scripts/run_agentic_pipeline.py --help` showed instance-testing output before argparse rendered the help text.

## Decision Log

- Decision: Keep the fetch orchestration in the public CLI and keep the digest pipeline focused on already-modeled `Thread` objects.
  Rationale: This is the smallest cut that still makes the runtime feel like one streamlined command while avoiding a junk-drawer `pipeline.py`.
  Date/Author: 2026-03-25 / Codex

- Decision: Rename `PostInput` and `ThreadInput` to `Post` and `Thread`, and remove the separate `PipelineInput` wrapper.
  Rationale: The thread shape is the application domain model, not an adapter format for one pipeline boundary.
  Date/Author: 2026-03-25 / Codex

## Outcomes & Retrospective

The core refactor landed in one small pass without creating a new architecture layer. The fetch contract now starts with tracked handles, turns scraper payloads into domain `Thread` objects immediately, and hands those objects to the digest pipeline. The public CLI now exposes the single-command runtime the user asked for, and the help path stays clean because scraper initialization is lazy.

## Context and Orientation

The relevant runtime lives in four places. `src/xs2n/twitter.py` currently reads `data/handles.json` and uses `ntscraper` with `Nitter` to fetch tweets, but it returns raw scraper payloads. `src/xs2n/agents/schemas.py` defines the current thread and digest models, but the thread model is still named like an input transfer object. `src/xs2n/agents/pipeline.py` currently reads a JSON file from disk, validates it into `PipelineInput`, and then runs the digest LLM steps. `scripts/run_agentic_pipeline.py` is the public CLI and still requires `--input-file`, which is the behavior this change removes.

## Plan of Work

Start with tests. Add one test that proves the tweet-fetching module returns `Thread` domain objects from scraper output, one test that proves the digest pipeline now accepts `threads` directly, and one CLI test that proves `scripts/run_agentic_pipeline.py` fetches first and then calls the pipeline with those modeled threads.

Once those tests fail for the right reason, rename the thread models in `src/xs2n/agents/schemas.py`, move the fetch module to return those models directly, and change `run_digest_pipeline` in `src/xs2n/agents/pipeline.py` to accept `threads` instead of `input_file`. Then simplify `scripts/run_agentic_pipeline.py` so it reads handles from `data/handles.json`, computes a time window, fetches tweets, calls the pipeline, and prints the final digest count. Finally, remove or retire the now-redundant fetch utility script, and update `README.md` plus `docs/codex/autolearning.md` so the documented contract matches the code.

## Concrete Steps

Run these commands from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Run focused tests before changes:

       uv run pytest tests/test_pipeline.py tests/test_llm.py tests/test_codex_auth.py -q

2. After writing new failing tests, run the same focused subset and expect failures that mention the old `input_file` contract or missing `Thread` names.

3. After implementation, run:

       uv run pytest tests/test_pipeline.py tests/test_twitter.py tests/test_codex_auth.py tests/test_llm.py -q

4. Then run the CLI help:

       uv run python scripts/run_agentic_pipeline.py --help

## Validation and Acceptance

Acceptance is behavioral. Running `python scripts/run_agentic_pipeline.py --output-file digest.json` should describe one single digest job surface. The code path must fetch tweets from `data/handles.json` first, turn them into `Thread` objects, pass those objects through the digest pipeline, and write only the final `digest.json` artifact. The focused tests must pass and prove that the domain model now starts at the fetch layer instead of at a later JSON adapter layer.

## Idempotence and Recovery

The CLI remains safe to rerun because it overwrites only the explicit output path. The refactor is additive within the same small module set, so if a step fails mid-way the safe recovery is to rerun the focused test subset and continue until the runtime contract is restored.

## Artifacts and Notes

Fresh docs checked for this change:

- Nitter docs via Context7 confirmed that Nitter is the read-only proxy layer used to retrieve Twitter/X content.
- Pydantic v2 docs via Context7 confirmed the current `model_validate`, `model_validate_json`, and `model_dump` APIs used by the refactor.

## Interfaces and Dependencies

At the end of this change, these interfaces should exist:

    class Post(BaseModel): ...

    class Thread(BaseModel):
        thread_id: str
        account_handle: str
        posts: list[Post]

    def get_twitter_threads(handles_path: Path, since_date: datetime) -> list[Thread]

    def run_digest_pipeline(*, threads: list[Thread], output_file: Path, model: str, api_key: str | None = None) -> DigestOutput

`ntscraper` remains the fetch dependency, and the digest steps continue using the OpenAI Agents SDK through `src/xs2n/agents/llm.py`.

Revision note (2026-03-25): Created this ExecPlan for the fetch-first refactor that removes the manual thread-input file flow.
