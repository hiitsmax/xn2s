# Replace the cluster-builder runtime with one runner and one scaffold

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

`~/.agents/PLANS.md` governs this document and must be followed as implementation continues.

## Purpose / Big Picture

After this change, the repository no longer pretends to have a finished domain agent architecture. A user can open one file, `src/xs2n/cli/run.py`, and see the real runtime order: either reuse an existing tweet-list JSON file or fetch tweets, write the working queue, then invoke one minimal Agents SDK scaffold that already uses ChatGPT/Codex authentication from the repository.

This matters because the next architecture pass should start from a truthful baseline. The old cluster-builder agent was concrete product behavior the user explicitly wants to remove before redesigning the pipeline.

## Progress

- [x] (2026-04-05 01:05Z) Mapped the active runtime and confirmed the repo still centered the old `cluster_builder_agent.py` plus two overlapping CLIs.
- [x] (2026-04-05 01:17Z) Wrote new failing tests for `src/xs2n/cli/run.py` and `src/xs2n/agents/agents_sdk_scaffold.py`, then confirmed collection failed because those modules did not exist yet.
- [x] (2026-04-05 01:29Z) Implemented the new runner and scaffold, removed the old cluster-builder runtime files, and updated package exports.
- [x] (2026-04-05 01:33Z) Verified the focused green state with `uv run pytest tests/test_run.py tests/test_agents_sdk_scaffold.py -q`.
- [ ] Run the broader verification slice that still covers auth, tracing, tweet fetching, and queue helpers.
- [ ] Re-read the repository surface after verification and note any remaining stale cluster-builder wording outside historical docs.

## Surprises & Discoveries

- Observation: the current `load_tweet_queue` and `save_tweet_queue` helpers were already enough to support the "reuse an existing tweet list file" branch without inventing a new persistence layer.
  Evidence: `src/xs2n/tools/cluster_state.py` already provides JSON list load/save helpers with parent-directory creation and file locking.

- Observation: the smallest honest Agents SDK example here still benefits from one real tool, because it makes the scaffold visibly agentic instead of looking like a plain model wrapper.
  Evidence: `src/xs2n/agents/agents_sdk_scaffold.py` now exposes `read_queue_preview` as the single tool bound to the working queue path.

## Decision Log

- Decision: create `src/xs2n/cli/run.py` as the only active pipeline entrypoint and point the `xs2n` script at it.
  Rationale: the user asked for one streamlined file where the fetch-versus-reuse branch is obvious without chasing multiple CLIs.
  Date/Author: 2026-04-05 / Codex

- Decision: replace `src/xs2n/agents/cluster_builder_agent.py` with `src/xs2n/agents/agents_sdk_scaffold.py`.
  Rationale: the user wants the only real agent removed and replaced with a scaffold that demonstrates Agents SDK plus ChatGPT/Codex auth wiring, not a finished domain runtime.
  Date/Author: 2026-04-05 / Codex

- Decision: keep the queue helpers under `src/xs2n/tools/cluster_state.py` for now instead of renaming or deleting them.
  Rationale: the request was to make minimal cuts and leave a clean starting point for a later architecture rewrite, not to rename every legacy helper in the same turn.
  Date/Author: 2026-04-05 / Codex

## Outcomes & Retrospective

The repository surface is smaller and more truthful. There is one active runtime file, one minimal Agents SDK scaffold, and the auth path is still shared through `src/xs2n/llm/openai_client.py`. The main remaining gap is that the broader verification slice has not yet been recorded in this document; that needs to happen before calling the branch fully wrapped.

## Context and Orientation

In this repository, a "tweet list" is the JSON queue consumed by the runtime, stored through `src/xs2n/tools/cluster_state.py`. The fetch layer lives in `src/xs2n/tools/twitter.py`. The shared OpenAI/Codex auth path lives in `src/xs2n/llm/openai_client.py`, which resolves ChatGPT/Codex login state first and only falls back to `OPENAI_API_KEY` if that login state is missing.

The new active runner is `src/xs2n/cli/run.py`. It parses CLI arguments, decides whether to fetch or reuse an existing tweet-list file, writes the working queue, and invokes `src/xs2n/agents/agents_sdk_scaffold.py`. That scaffold binds one `read_queue_preview` tool to the queue file and runs through the OpenAI Agents SDK with the shared auth/model builder.

## Plan of Work

Start from tests so the new surface is explicit. Replace the old runner tests with expectations around `src/xs2n/cli/run.py` and add a dedicated scaffold test for the new agent module. Once the failing state proves the new module names are missing, implement the runner and scaffold with the smallest behavior needed to satisfy the tests: direct branch logic in `run.py`, one queue preview tool in the scaffold, and the existing auth/model builder wired into the SDK runtime.

After the code is green, remove the old cluster-builder runtime files and update the README plus `docs/codex/autolearning.md` so the repository story matches the code. Leave historical execplans untouched unless they are actively misleading current implementation work.

## Concrete Steps

Work from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Run the focused red test command:

   `uv run pytest tests/test_run.py tests/test_agents_sdk_scaffold.py -q`

   Expected before implementation: collection errors because `xs2n.cli.run` and `xs2n.agents.agents_sdk_scaffold` do not exist.

2. Implement:

   - `src/xs2n/cli/run.py`
   - `src/xs2n/agents/agents_sdk_scaffold.py`
   - `src/xs2n/prompts/agents_sdk_scaffold.txt`

3. Remove:

   - `src/xs2n/cli/fetch_to_cluster.py`
   - `src/xs2n/cli/cluster_builder.py`
   - `src/xs2n/agents/cluster_builder_agent.py`
   - `src/xs2n/prompts/cluster_builder.txt`

4. Update:

   - `src/xs2n/agents/__init__.py`
   - `pyproject.toml`
   - `README.md`
   - `docs/codex/autolearning.md`

5. Run the focused green test command:

   `uv run pytest tests/test_run.py tests/test_agents_sdk_scaffold.py -q`

   Expected after implementation: `6 passed`.

6. Run the broader verification slice before closing the task:

   `uv run pytest tests/test_openai_client.py tests/test_codex_auth.py tests/test_twitter.py tests/test_twitter_nitter_rss.py tests/test_cluster_builder_thread_queue.py tests/test_cluster_builder_store.py tests/test_cluster_builder_tools.py tests/test_tracing.py tests/test_agents_sdk_scaffold.py tests/test_run.py -q`

## Validation and Acceptance

Acceptance is behavioral and structural. A reader should be able to open `src/xs2n/cli/run.py` and understand the runtime order from top to bottom. Running `uv run xs2n --tweet-list-file <path>` should skip fetch, write the working queue, and invoke the scaffold. Running `uv run xs2n --help` should describe the new `--tweet-list-file` option. The scaffold tests must prove that the runtime still uses the shared OpenAI/Codex auth builder and the OpenAI Agents SDK runner.

## Idempotence and Recovery

The runner is safe to repeat because it rewrites the working queue file from either fresh fetch results or the provided tweet-list file. If the scaffold step fails, rerun the same command after fixing the prompt or runtime code; the queue file can be reused. Removing the old cluster-builder runtime is safe here because the user explicitly requested that architecture be taken out before the redesign.

## Artifacts and Notes

Focused green verification recorded during implementation:

  $ uv run pytest tests/test_run.py tests/test_agents_sdk_scaffold.py -q
  ......                                                                   [100%]
  6 passed in 0.76s

Key end-state files:

- `src/xs2n/cli/run.py`
- `src/xs2n/agents/agents_sdk_scaffold.py`
- `src/xs2n/prompts/agents_sdk_scaffold.txt`
- `README.md`
- `docs/codex/autolearning.md`

## Interfaces and Dependencies

The new scaffold keeps using the existing `build_openai_responses_model()` function from `src/xs2n/llm/openai_client.py`. That function is the repository's shared contract for "use ChatGPT/Codex auth if available, otherwise fall back to `OPENAI_API_KEY`." The scaffold module must expose:

- `AgentsSdkScaffold`
- `build_agents_sdk_scaffold(model, reasoning_effort, queue_path)`
- `DEFAULT_MODEL`
- `DEFAULT_REASONING_EFFORT`

The runner module must expose:

- `DEFAULT_HANDLES_PATH`
- `DEFAULT_QUEUE_PATH`
- `DEFAULT_SCAFFOLD_PROMPT`
- `build_parser()`
- `main(argv=None)`

Revision note: initial plan written after implementation to capture the final rationale, observed behavior, and the exact verification slice needed to finish the branch cleanly.
