# Refactor The Text Router Into A Feature Package

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository follows [PLANS.md](../../../.agents/PLANS.md), and this document must be maintained in accordance with that file.

## Purpose / Big Picture

After this change, the text router will live as one feature-local package under `src/xs2n/agents/text_router/` instead of being split between `src/xs2n/agents/text_router.py` and `src/xs2n/utils/text_router.py`. A reader will be able to open one folder and see the public entrypoint in `main.py` plus the router-specific transport helpers in `utils.py`. The change is observable by running the existing router tests and the CLI tests: they should still pass while imports now point at the package-local modules.

## Progress

- [x] (2026-04-09 10:05Z) Reviewed the current text router layout and confirmed that router-specific packing and parsing helpers still live in `src/xs2n/utils/text_router.py`.
- [x] (2026-04-09 10:10Z) Chose the package layout `src/xs2n/agents/text_router/{__init__.py,main.py,utils.py}` so the public entrypoint reads as a feature slice and router-only helpers stop pretending to be general utilities.
- [x] (2026-04-09 10:16Z) Rewrote `tests/test_text_router.py` to import `xs2n.agents.text_router.main` and `xs2n.agents.text_router.utils`, then confirmed the red state with `ModuleNotFoundError` because the package did not exist yet.
- [x] (2026-04-09 10:22Z) Moved the router into `src/xs2n/agents/text_router/`, updated `src/xs2n/run.py` to import queue adapters from the package-local `utils.py`, and deleted the old flat modules.
- [x] (2026-04-09 10:24Z) Ran the focused verification slice and confirmed the router and CLI tests still pass after the move.

## Surprises & Discoveries

- Observation: The current public API is already function-shaped (`route_tweet_rows(...)`), so the largest remaining mismatch is file placement rather than runtime behavior.
  Evidence: `src/xs2n/agents/text_router.py` exports a single function and imports all of its real work from `src/xs2n/utils/text_router.py`.

- Observation: The helper cleanup was easiest when keeping one feature-local `utils.py` and simplifying the parser loop, not by splitting into more files.
  Evidence: `src/xs2n/agents/text_router/utils.py` now expands ids during the same validation loop that checks completeness and uniqueness, so the extra `_expand_ids(...)` helper disappeared without making the parser harder to scan.

## Decision Log

- Decision: Keep the public router entrypoint as a function in `main.py` rather than restoring a class or builder.
  Rationale: The previous refactor already aligned the runtime contract with the real job. This change only relocates and clarifies ownership boundaries.
  Date/Author: 2026-04-09 / Codex

- Decision: Use one feature-local `utils.py` instead of splitting immediately into `transport.py` and `queue_adapter.py`.
  Rationale: The router helper surface is still small. Moving it under the feature package solves the ownership problem now, and keeping one small helper module avoids premature file splitting.
  Date/Author: 2026-04-09 / Codex

## Outcomes & Retrospective

The refactor achieved the original purpose. The text router is now a self-contained feature package under `src/xs2n/agents/text_router/`, with `main.py` holding the public entrypoint and `utils.py` holding router-only support code. The CLI still behaves the same, but a reader no longer has to bounce between `agents/` and `utils/` to understand one router feature.

The only deliberate non-goal was further splitting `utils.py` into multiple files. That may become worthwhile later if the router grows another distinct responsibility, but the current helper surface is still small enough that one feature-local helper module is the more readable shape.

## Context and Orientation

The current router path is split across two modules. `src/xs2n/agents/text_router.py` contains the public function `route_tweet_rows(...)`, which constructs a `BaseAgent`, loads the prompt, invokes the model, and parses the result. `src/xs2n/utils/text_router.py` contains the compact-id transport format, the parser for the router output, and the queue-item adapters that prepare CLI data for the router. The CLI entrypoint `src/xs2n/run.py` imports `route_tweet_rows(...)` from `xs2n.agents` and imports queue adapters from `xs2n.utils.text_router`.

In this repository, a “feature package” means a directory that holds one feature’s public entrypoint plus its private support code. The goal here is to make the text router readable by opening one folder instead of hopping between `agents/` and `utils/`.

## Plan of Work

Start by rewriting the tests so they describe the desired package boundary. `tests/test_text_router.py` should import the public entrypoint from `xs2n.agents.text_router.main` and the helper functions from `xs2n.agents.text_router.utils`. `tests/test_run.py` should continue to patch the public router function through `xs2n.run`, but any direct helper imports should point at the new package path.

Once the tests are red for the missing package modules, create `src/xs2n/agents/text_router/__init__.py` to export `route_tweet_rows`. Move the public function into `src/xs2n/agents/text_router/main.py`. Move router-specific helper logic into `src/xs2n/agents/text_router/utils.py`, keeping only the helpers that materially improve readability. Delete `src/xs2n/agents/text_router.py` and `src/xs2n/utils/text_router.py` after imports are updated.

Update `src/xs2n/agents/__init__.py` and `src/xs2n/run.py` so the package is the single source of truth for text-router imports. Keep behavior unchanged: `--route-text` must still build routing rows, call the router, and print the grouped output.

## Concrete Steps

Work from the repository root `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Run the red test slice after updating imports:

       uv run pytest tests/test_text_router.py tests/test_run.py::test_main_can_route_queue_items_with_text_router -q

   Expect collection or import failures mentioning `xs2n.agents.text_router.main` or `xs2n.agents.text_router.utils` until the new package exists.

2. Implement the package refactor and helper cleanup.

3. Run the focused verification slice:

       uv run pytest tests/test_run.py tests/test_base_agent.py tests/test_text_router.py tests/test_tracing.py -q

   Observed:

       .............                                                            [100%]
       13 passed in 1.13s

## Validation and Acceptance

Acceptance is behavioral and structural. A contributor should be able to open `src/xs2n/agents/text_router/` and find both the router entrypoint and its support code there. The focused test slice must pass, proving that the CLI still routes queue items and that the router parser still validates compact-id completeness and uniqueness.

## Idempotence and Recovery

This refactor is safe to repeat because it only moves Python modules and updates imports. If an intermediate step breaks imports, rerun the focused tests to see which path still points at the deleted modules, then update that import and rerun. No data migrations or destructive state changes are involved.

## Artifacts and Notes

Expected red-state evidence after rewriting imports:

    ModuleNotFoundError: No module named 'xs2n.agents.text_router.main'

Expected green-state evidence after implementation:

    13 passed in under 1s

## Interfaces and Dependencies

At the end of this refactor, these public interfaces must exist:

- `xs2n.agents.text_router.route_tweet_rows(*, model: str, rows: list[RoutingTweetRow]) -> RoutingResult`
- `xs2n.agents.text_router.utils.build_routing_rows_from_queue_items(items: list[TweetQueueItem]) -> list[RoutingTweetRow]`
- `xs2n.agents.text_router.utils.format_routing_result(result: RoutingResult) -> str`
- `xs2n.agents.text_router.utils.build_packed_routing_batch(rows: list[RoutingTweetRow]) -> PackedRoutingBatch`
- `xs2n.agents.text_router.utils.parse_routing_output(output: str, *, packed_batch: PackedRoutingBatch) -> RoutingResult`

Revision note: created this plan before moving the router modules so the package layout, acceptance criteria, and verification commands stay explicit during implementation.

Revision note: updated the plan after implementation to record the red-state import failure, the package move, the helper simplification, and the passing verification output so the document remains restartable.
