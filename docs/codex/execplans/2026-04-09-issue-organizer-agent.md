# Add A One-Shot Issue Organizer Agent

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository follows [PLANS.md](../../../.agents/PLANS.md), and this document must be maintained in accordance with that file.

## Purpose / Big Picture

After this change, `xs2n` will be able to take the prepared tweet queue, route it through the existing text classifier, drop only the ambiguous tweets, and send the remaining tweet content to one new model step that returns a strict JSON issue map. A user will be able to run one CLI mode and see a machine-validated JSON payload with issues, descriptions, and linked tweet ids plus the reason each tweet belongs to that issue.

## Progress

- [x] (2026-04-08 22:20Z) Reviewed the current runtime shape and confirmed that `src/xs2n/run.py` already owns the top-to-bottom CLI order while `src/xs2n/agents/text_router/` is the best local pattern to copy for a new prompt-specific feature.
- [x] (2026-04-08 22:20Z) Chose the first-cut scope: one-shot issue organization only, no incremental patch merge, no store mutation, and no deterministic pre-grouping beyond excluding ambiguous tweets.
- [x] (2026-04-08 22:25Z) Wrote the failing tests for the new issue schema, parser guarantees, agent entrypoint, and CLI mode, then confirmed the red state with `ModuleNotFoundError` because `xs2n.agents.issue_organizer` did not exist yet.
- [x] (2026-04-08 22:32Z) Implemented the new issue organizer feature package, neutral issue schema module, prompt asset, agent export, and CLI plumbing for `--build-issues`.
- [x] (2026-04-08 22:23Z) Ran the focused verification slice `uv run pytest tests/test_issue_organizer.py tests/test_text_router.py tests/test_run.py tests/test_base_agent.py -q` and observed `17 passed in 0.79s`, then updated `README.md` and `docs/codex/autolearning.md`.

## Surprises & Discoveries

- Observation: The current CLI already has the right control-flow style for this feature because it does queue preparation first and then chooses exactly one model path.
  Evidence: `src/xs2n/run.py` loads or fetches queue items, writes the queue file, enables tracing, then branches between `--route-text` and the base scaffold.

- Observation: The strictest useful parser rule for this first version is “each forwarded tweet id must appear exactly once”, not a softer “at most once” check.
  Evidence: the new parser test catches both duplicate coverage and missing coverage with the same contract, which keeps the model output suitable for downstream persistence later.

## Decision Log

- Decision: Keep the first issue organizer path one-shot and stateless.
  Rationale: The user explicitly simplified the scope to “filtered/classified tweets in, final JSON out”, so patch-merging state would add complexity without enabling the first observable behavior.
  Date/Author: 2026-04-08 / Codex

- Decision: Reuse the existing text router as the filter/classification step and exclude only `ambiguous` ids before issue building.
  Rationale: The repo already has one tested classification stage. Reusing it keeps the runtime honest and avoids inventing a second pre-filter contract.
  Date/Author: 2026-04-08 / Codex

## Outcomes & Retrospective

The first-cut issue organizer is now present as an additive feature. The runtime can reuse the existing router, exclude ambiguous tweets, and print strict issue JSON without mutating stored cluster state. That keeps the first iteration easy to inspect and safe to run from cron or shell scripts.

The deliberate non-goals remain unchanged: there is still no incremental patch merge, no persistence step for issue output, and no extra heuristics before the model call. Those can be layered on later if the one-shot contract proves too large or too lossy on real data.

## Context and Orientation

The source tree already contains one prompt-specific feature package at `src/xs2n/agents/text_router/`. Its `main.py` exports a single domain function, its `utils.py` holds feature-local helpers, and the prompt text lives under `src/xs2n/prompts/`. Shared queue and cluster contracts live under `src/xs2n/schemas/` and persisted JSON helpers live under `src/xs2n/tools/cluster_state.py`.

The new feature should follow that ownership model. In this plan, an “issue organizer” means one model invocation that receives tweet content and returns a JSON object with issue records. An “issue record” contains an id, title, description, and linked tweet ids with a short reason for each link. The feature must validate that JSON before the CLI prints it.

## Plan of Work

Start by extending the tests so they describe the target behavior before any production code changes. Add a new test module for issue-organizer-specific packing and parsing. The parser tests must prove that valid JSON becomes typed schema objects and that invalid coverage, such as duplicate tweet ids or missing tweet ids, is rejected. Extend the CLI tests so a new mode runs the router first, forwards only non-ambiguous tweets to the new feature, and prints the resulting JSON.

After the tests are red, add a new schema module for the issue-organizer contracts. Keep these contracts neutral because they are shared between the parser, the CLI, and any future persistence step. Then add `src/xs2n/agents/issue_organizer/` with `__init__.py`, `main.py`, and `utils.py`. `main.py` should mirror the text router pattern: build a `BaseAgent`, load the prompt, invoke the model, and parse the final JSON string. `utils.py` should convert queue items into the issue-organizer input payload, filter out ambiguous rows using the router result, and validate the output coverage rules.

Update `src/xs2n/agents/__init__.py` to export the new public entrypoint. Then update `src/xs2n/run.py` so a new CLI flag runs `route_tweet_rows(...)`, selects the non-ambiguous queue items in original order, invokes the issue organizer, and prints one JSON line block to stdout. Keep the old modes unchanged. Finally, update `README.md` and `docs/codex/autolearning.md` so the new runtime surface and the learned design rule are captured near the code.

## Concrete Steps

Work from the repository root `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Write the failing tests, then run:

       uv run pytest tests/test_issue_organizer.py tests/test_run.py::test_main_can_build_issue_json_from_non_ambiguous_tweets -q

   Expect failures because the new schema module, feature package, or CLI branch does not exist yet.

2. Implement the new schema module, feature package, prompt asset, agent export, and CLI mode.

3. Run focused verification:

       uv run pytest tests/test_issue_organizer.py tests/test_text_router.py tests/test_run.py tests/test_base_agent.py -q

4. If the focused slice passes, update `README.md` and `docs/codex/autolearning.md`, then rerun the same focused verification command.

## Validation and Acceptance

Acceptance is user-visible. Running the CLI with the new issue-organizer mode against an existing queue file must print a valid JSON object whose top-level key is `issues`. The router must still classify the queue first, ambiguous tweets must not be forwarded into the issue-organizer payload, and the resulting JSON must be validated so duplicate or missing tweet coverage fails fast instead of silently printing bad output.

The focused pytest slice must pass. The new issue-organizer tests must demonstrate both parser correctness and CLI orchestration behavior.

## Idempotence and Recovery

This change is additive. Re-running the CLI mode is safe because it only reads the queue file, routes tweets, and prints validated JSON; it does not mutate persisted cluster state. If parser validation fails during development, inspect the failing output contract in the new tests first because that is the fastest way to determine whether the prompt, schema, or coverage rules drifted.

## Artifacts and Notes

Expected CLI success shape after implementation:

    Reused 3 queue item(s).
    Queue items ready: 3
    Issue organizer completed.
    Issue JSON: {"issues":[...]}

Expected parser failure shape during development when the model duplicates tweet ids:

    ValueError: Each input tweet id must appear exactly once in the issue output.

## Interfaces and Dependencies

At the end of this change, these public interfaces must exist:

- `xs2n.agents.issue_organizer.build_issue_map(*, model: str, rows: list[IssueTweetRow]) -> IssueMap`
- `xs2n.agents.issue_organizer.utils.build_issue_rows_from_queue_items(items: list[TweetQueueItem]) -> list[IssueTweetRow]`
- `xs2n.agents.issue_organizer.utils.select_non_ambiguous_issue_rows(items: list[TweetQueueItem], routing_result: RoutingResult) -> list[IssueTweetRow]`
- `xs2n.agents.issue_organizer.utils.parse_issue_map_output(output: str, *, rows: list[IssueTweetRow]) -> IssueMap`

The feature will continue to rely on the existing `BaseAgent` wrapper, `load_prompt(...)`, and the current OpenAI Agents SDK integration. The prompt should follow current GPT-5.4 guidance by making the role, completion criteria, and output contract explicit and by requiring JSON-only output.

Revision note: created this plan before the new tests and implementation so the one-shot scope, repo-local boundaries, and verification commands stay explicit while the feature is built.

Revision note: updated the plan after the red-state import failure and the first implementation pass so the executed scope, parser discovery, and remaining verification/doc work stay restartable from this file alone.
