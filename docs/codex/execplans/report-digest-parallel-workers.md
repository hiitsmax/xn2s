# Report Digest Parallel Workers

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the digest should stop paying the full latency cost of serial thread-by-thread model calls in the first three semantic stages. A user should be able to run `xs2n report digest --parallel-workers <n>` or `xs2n report latest --parallel-workers <n>` and see the same artifact set as before, but produced with bounded per-stage concurrency and with the chosen worker count recorded in `run.json`.

The visible proof is:

- the CLI accepts `--parallel-workers` on both report commands,
- the digest pipeline fans out the `categorize_threads`, `filter_threads`, and `process_threads` stages without changing their stage order,
- `run.json` records the configured worker count,
- the focused and full pytest suites stay green.

## Progress

- [x] (2026-03-15 22:32Z) Audited the current digest pipeline, CLI plumbing, and tests to confirm that the first three semantic stages are item-independent and can be parallelized without changing stage barriers.
- [x] (2026-03-15 22:34Z) Pulled fresh Context7 guidance for Python `concurrent.futures.ThreadPoolExecutor`, especially bounded worker pools, exception propagation, and ordered result handling.
- [x] (2026-03-15 22:43Z) Added bounded parallel execution to the `categorize_threads`, `filter_threads`, and `process_threads` step modules through a shared helper in `src/xs2n/agents/digest/helpers.py`.
- [x] (2026-03-15 22:45Z) Threaded `parallel_workers` through `run_digest_report(...)`, the `xs2n report digest` CLI, and the `xs2n report latest` CLI, with a default of `4` and run-level artifact logging in `run.json`.
- [x] (2026-03-15 22:48Z) Extended digest and CLI tests to cover the new parameter, worker-count recording, and ordering preservation under delayed fake-LLM calls.
- [ ] Run the full pytest suite and record the final result in this document.
- [ ] Commit the feature with a conventional commit message.

## Surprises & Discoveries

- Observation: `src/xs2n/agents/digest/llm.py` was already partly prepared for parallel execution.
  Evidence: the current `DigestLLM` implementation already uses thread-local OpenAI clients and a lock around the shared trace counter.

- Observation: the easiest place to preserve deterministic artifact ordering is the step helper, not the pipeline.
  Evidence: the stage artifacts need input-order stability, while `llm_calls/*.json` only need unique trace ids.

- Observation: the existing fake LLM used in tests needed locking before the new concurrency assertions were trustworthy.
  Evidence: it kept a shared `_call_index` and wrote trace filenames from it.

## Decision Log

- Decision: parallelize only within the first three semantic stages and keep the stage boundaries intact.
  Rationale: categorization, filtering, and per-thread processing are independent per thread, while issue grouping still needs the fully processed set.
  Date/Author: 2026-03-15 / Codex

- Decision: use one worker-count parameter for the three parallel stages instead of separate per-stage knobs.
  Rationale: one knob keeps the CLI simpler and matches the user request for a configurable worker quantity.
  Date/Author: 2026-03-15 / Codex

- Decision: keep the current linear pipeline file and add concurrency inside the step helpers.
  Rationale: this preserves the repo's preference for obvious top-to-bottom orchestration while still speeding up the item-local work.
  Date/Author: 2026-03-15 / Codex

## Outcomes & Retrospective

The intended runtime shape is implemented: the first three digest stages now support bounded concurrency and the chosen worker count is visible in run artifacts. The remaining work is operational closure: finish the full test run and record the final commit.

## Context and Orientation

The report CLI entrypoints live in `src/xs2n/cli/report.py`. `digest(...)` directly calls `run_digest_report(...)`. `latest(...)` first runs timeline ingestion and then calls the same digest pipeline. Adding a new report-wide option means touching both command functions.

The digest orchestrator lives in `src/xs2n/agents/digest/pipeline.py`. It still reads like the real runtime order: load taxonomy, load threads, categorize, filter, process, group issues, render markdown. In this repository, “parallelizing the digest” does not mean turning the pipeline into a planner or a multi-agent graph. It means letting the thread-local stages process multiple threads at once while still waiting for each stage to finish before the next one starts.

The step modules live in `src/xs2n/agents/digest/steps/`. `categorize_threads.py`, `filter_threads.py`, and `process_threads.py` each loop over a list of thread-shaped objects and call the shared `DigestLLM`. Those three files are the correct place to add bounded fanout because the semantic role still belongs to each step.

Shared helper code lives in `src/xs2n/agents/digest/helpers.py`. That file already owns other cross-step utilities such as taxonomy loading, JSON writing, virality scoring, and source-link rendering, so it is also where the new bounded thread-pool mapper belongs.

The test coverage that proves this feature lives in `tests/test_report_cli.py` and `tests/test_report_digest.py`. The digest test file already uses a fake LLM that writes `llm_calls/*.json`, which makes it the right place to assert stable artifact behavior under concurrency.

## Plan of Work

First, add one shared helper in `src/xs2n/agents/digest/helpers.py` that accepts a list of items, a worker function, and a maximum worker count. The helper must keep result ordering aligned with the original input order even when faster tasks finish earlier. It must also surface the first exception and shut down the worker pool cleanly.

Second, update `src/xs2n/agents/digest/steps/categorize_threads.py`, `src/xs2n/agents/digest/steps/filter_threads.py`, and `src/xs2n/agents/digest/steps/process_threads.py` so each stage defines a local per-item worker function and routes the item list through the new helper. Keep the prompts, payloads, and result models unchanged.

Third, update `src/xs2n/agents/digest/pipeline.py` to define `DEFAULT_REPORT_PARALLEL_WORKERS`, accept a `parallel_workers` argument in `run_digest_report(...)`, reject invalid values below `1`, pass the value into the three parallel stages, and record it in `run.json`.

Fourth, update `src/xs2n/cli/report.py` to expose `--parallel-workers` on both `xs2n report digest` and `xs2n report latest`, and pass the chosen value through to `run_digest_report(...)`. Update `src/xs2n/agents/__init__.py` and `src/xs2n/agents/digest/__init__.py` so the default constant stays exportable from the CLI layer.

Fifth, update `tests/test_report_cli.py` so the fake pipeline captures the new argument, and update `tests/test_report_digest.py` so the fake LLM is thread-safe and the test run proves both of these behaviors: stage artifacts keep input order even when one thread is artificially delayed, and `run.json` records the configured worker count.

Finally, update `README.md` and `docs/codex/autolearning.md` so users can discover the new flag and future contributors can see why the bounded concurrency was introduced.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, implement and validate with:

    uv run pytest tests/test_report_cli.py tests/test_report_digest.py
    uv run pytest

Expected focused-test transcript after the implementation:

    collected 20 items
    tests/test_report_cli.py ...............
    tests/test_report_digest.py .....
    20 passed

Expected behavioral usage:

    uv run xs2n report digest --timeline-file data/timeline.json --parallel-workers 6
    uv run xs2n report latest --home-latest --lookback-hours 24 --parallel-workers 4

The resulting `data/report_runs/<run_id>/run.json` should include:

    {
      "parallel_workers": 4,
      ...
    }

Actual validation completed so far:

    uv run pytest tests/test_report_cli.py tests/test_report_digest.py
    20 passed, 215 warnings in 0.69s

## Validation and Acceptance

Acceptance is behavioral:

1. `uv run pytest tests/test_report_cli.py tests/test_report_digest.py` passes with assertions for the new CLI flag, run metadata, and deterministic artifact ordering under concurrency.
2. `uv run pytest` passes for the full repository.
3. `xs2n report digest --parallel-workers <n>` and `xs2n report latest --parallel-workers <n>` accept the new option and route it into `run_digest_report(...)`.
4. Each completed digest run writes the configured worker count into `run.json`.

Current status:

1. Passed.
2. Pending.
3. Implemented and covered by unit tests.
4. Implemented and covered by unit tests.

## Idempotence and Recovery

The code changes are additive and safe to rerun. The worker-count flag does not mutate shared state outside the normal run artifacts. If a chosen worker count turns out to be too aggressive for rate limits, rerun the same command with a lower number or with `--parallel-workers 1` to force the old serial behavior. Each digest run still writes to a new timestamped directory, so failed or retried runs do not overwrite prior evidence.

## Artifacts and Notes

Context7 reference used for this milestone:

- `/python/cpython` for `concurrent.futures.ThreadPoolExecutor`, especially bounded worker pools, ordered result collection, and future exception propagation.

Primary files touched by this milestone:

- `src/xs2n/agents/digest/helpers.py`
- `src/xs2n/agents/digest/pipeline.py`
- `src/xs2n/agents/digest/steps/categorize_threads.py`
- `src/xs2n/agents/digest/steps/filter_threads.py`
- `src/xs2n/agents/digest/steps/process_threads.py`
- `src/xs2n/cli/report.py`
- `tests/test_report_cli.py`
- `tests/test_report_digest.py`
- `README.md`
- `docs/codex/autolearning.md`
- `docs/codex/execplans/report-digest-parallel-workers.md`

## Interfaces and Dependencies

At the end of this milestone, `src/xs2n/agents/digest/pipeline.py` must export:

    DEFAULT_REPORT_PARALLEL_WORKERS = 4

and `run_digest_report(...)` must accept:

    parallel_workers: int = DEFAULT_REPORT_PARALLEL_WORKERS

The three step files must each accept a `parallel_workers: int` argument and use the shared helper rather than open-coding their own executors.

The CLI command functions in `src/xs2n/cli/report.py` must each expose:

    --parallel-workers <int>

with `min=1` validation at the Typer layer.

Revision note (2026-03-15): Created this plan while implementing configurable per-stage concurrency for the digest pipeline so the design, progress, and validation remain restartable from one file.
