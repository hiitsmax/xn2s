# Large-Batch TWScrape Fetch

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the authenticated Twitter/X fallback in `src/xs2n/twitter_twscrape.py` will stay usable when the handle list is very large. Instead of processing every handle in strict sequence and failing unpredictably on slow or broken profiles, the fetch path will process handles in small windows, retry each handle with a clear limit, and stop to ask the human operator what to do when a window still has failures. The behavior is observable by running the existing digest script against a large handles file and watching the fetch path continue through successful handles while presenting an explicit `retry / go on / stop` decision for the failed ones.

## Progress

- [x] (2026-03-29 21:45Z) Reconfirmed that the active working tree still contains the digest fetch runtime under `src/xs2n/twitter_twscrape.py` and its related tests.
- [x] (2026-03-29 21:52Z) Wrote failing tests for batched retry, timeout, and interactive decision behavior in `tests/test_twitter_twscrape.py` and confirmed they failed because the batching helper did not exist yet.
- [x] (2026-03-29 21:55Z) Implemented batched twscrape handle fetching with small fixed windows and per-handle retry/timeout limits in `src/xs2n/twitter_twscrape.py`.
- [x] (2026-03-29 21:58Z) Ran focused fetch and digest tests, then updated docs to record the new runtime behavior.

## Surprises & Discoveries

- Observation: The current working tree includes both `cluster_builder` and the digest fetch runtime, so the fetch improvement must land in the existing Twitter files instead of assuming the older path was deleted.
  Evidence: `find src -maxdepth 3 -type f | sort | rg 'twitter|pipeline|cluster_builder'` on 2026-03-29 returned both `src/xs2n/twitter_twscrape.py` and `src/xs2n/cluster_builder/*`.

## Decision Log

- Decision: Keep the batching behavior inside `src/xs2n/twitter_twscrape.py` instead of introducing a separate runtime package or persistent queue.
  Rationale: The user explicitly asked for simple, direct changes with no extra data structures or over-engineered scheduling layer. Chunking, retry, timeout, and interactive decisions are all part of the fetch behavior itself.
  Date/Author: 2026-03-29 / Codex

- Decision: Use fixed-size handle windows plus per-handle timeout and retry limits, but skip a global run budget for now.
  Rationale: This gives more predictable runtime for very large handle lists without adding another policy dimension before the simpler guardrails have proven useful.
  Date/Author: 2026-03-29 / Codex

## Outcomes & Retrospective

The authenticated fallback is now much more usable for very large handle lists without adding a new runtime layer. The fetch path still returns the same `list[Thread]` contract, but it now processes handles in small windows, retries each handle with an explicit cap, and asks the operator what to do with persistent failures instead of silently stalling or failing the whole run. The change stayed contained to the existing Twitter fetch module and related docs/tests, which matches the user’s request for a direct, non-overengineered solution.

## Context and Orientation

The relevant public fetch entrypoint is `src/xs2n/twitter.py`, which first tries Nitter and then falls back to `src/xs2n/twitter_twscrape.py` when Nitter is unavailable. The `get_twscrape_threads(...)` function is the authenticated fallback used by the digest runner in `scripts/run_agentic_pipeline.py`. Today that fallback loops through handles one by one, which makes very large batches slow and brittle. The current tests in `tests/test_twitter_twscrape.py` cover state-dir behavior, cookie mapping, rate-limit retries, and account bootstrap, but they do not yet lock down behavior for large-batch orchestration.

In this document, a "window" means one small list of handles fetched in parallel before moving to the next list. A "retry budget" means how many extra attempts a handle gets after its first failed attempt. A "handle timeout" means the maximum amount of time spent waiting for one handle's fetch coroutine before that handle is treated as failed for the current decision point.

## Plan of Work

Start with tests in `tests/test_twitter_twscrape.py`. Add focused tests around a new batching helper in `src/xs2n/twitter_twscrape.py` that will own the real new behavior: processing handles in fixed-size windows, retrying a failing handle up to a small limit, and asking the user what to do with still-failed handles after a window completes. Keep the tests at the helper level so they exercise the new orchestration without mocking the entire twscrape package internals.

Once those tests fail for the right reason, update `src/xs2n/twitter_twscrape.py`. Keep `get_twscrape_threads(...)` as the public entrypoint, but route the async implementation through one batching helper that accepts the per-handle fetch coroutine, the window size, the timeout, and the interactive input/output functions. Keep the helper honest: it should do real work, not just forward arguments. It should return only the collected `Thread` objects and use the existing `RuntimeError` path when the operator chooses to stop.

After the batching logic is in place, wire the existing twscrape fetch path into that helper so the real runtime inherits the new behavior. Finally, update `docs/codex/autolearning.md` with the new preference that the authenticated fetch fallback for large runs should use small windows plus explicit operator decisions instead of one giant sequential pass.

## Concrete Steps

Run these commands from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Run the focused tests before changes:

       uv run pytest tests/test_twitter_twscrape.py -q

2. After adding the new tests, rerun:

       uv run pytest tests/test_twitter_twscrape.py -q

   Expect failures that mention the missing batching/interactivity behavior.

3. After implementation, run:

       uv run pytest tests/test_twitter_twscrape.py tests/test_twitter.py tests/test_run_agentic_pipeline.py -q

4. As a final script-level check, run:

       uv run python scripts/run_agentic_pipeline.py --help

## Validation and Acceptance

Acceptance is behavioral. The focused fetch tests must prove that a failed handle can be retried within a window, that the operator can choose to continue past persistent failures or stop the run, and that a hanging handle is converted into a controlled failure by the timeout guard. The digest runner tests must still pass, proving the public fetch contract did not regress. A human should also be able to run the digest script in the terminal and see explicit progress for handle windows plus a `retry / go on / stop` prompt when a window still has failed handles.

## Idempotence and Recovery

The change is safe to re-run because it only changes Python code and tests. If implementation stops halfway through, rerun the focused test command and continue until the helper and public fetch entrypoint both satisfy the new orchestration tests. If an interactive batch run reaches a stop decision, rerunning the script starts a clean new fetch cycle with the same defaults.

## Artifacts and Notes

Fresh docs checked during design:

- Context7 Python docs confirmed `asyncio.timeout(...)` is the standard way to cap the time spent inside one coroutine and convert expiry into a `TimeoutError`.
- Context7 HTTPX docs confirmed client timeouts and pool limits are available if the fallback later needs lower-level tuning, but this first pass stays with the simpler high-level twscrape API.

## Interfaces and Dependencies

At the end of this change, `src/xs2n/twitter_twscrape.py` should still export:

    def get_twscrape_threads(*, handles: list[str], since_date) -> list[Thread]

The module should also define one batching helper that owns the new behavior and is directly tested. The helper should accept a handle-fetch coroutine function, the handle list, and the interactive input/output functions. The code should continue to use `twscrape.API`, `twscrape.login.get_guest_token`, and the existing `Thread`/`Post` domain models from `src/xs2n/agents/schemas.py`.

Revision note (2026-03-29): Created this ExecPlan for the large-batch authenticated tweet fetch improvement focused on small windows, per-handle retry/timeout, and terminal decisions for persistent failures.

Revision note (2026-03-29, later): Updated the plan after implementation to reflect the completed batching helper, passing verification, and the final direct-in-module design.
