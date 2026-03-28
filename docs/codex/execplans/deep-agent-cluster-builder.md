# Deep Agent Cluster Builder

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md` and must be maintained accordingly.

## Purpose / Big Picture

After this change, the repository will be able to run one non-interactive deep agent that takes a list of tweets as input, processes them sequentially like a todo queue, and builds a structured cluster list through domain tools instead of free-form text output. A developer will be able to launch one command, inspect the resulting cluster JSON, and inspect the full run in LangFuse to see which tweets were read, deferred, or completed and how clusters were created or updated.

The smallest useful outcome is not a full autonomous production system. The smallest useful outcome is a constrained prototype that proves four behaviors in one run: the agent can read the next available tweet, decide whether to cluster it now or defer it, mutate clusters only through structured tools, and mark the tweet as processed in queue state.

## Progress

- [x] (2026-03-28 18:39Z) Confirmed the target interaction model with the user: one non-interactive deep agent, input is only a tweet list, sequential queue processing, deferred tweets allowed within the same run, and LangFuse is the primary observability surface.
- [x] (2026-03-28 18:44Z) Verified fresh documentation for GPT-5.4 prompt guidance, LangGraph/DeepAgents examples, and LangFuse callback-handler integration to keep the design aligned with the current external contracts.
- [x] (2026-03-28 18:51Z) Wrote this initial ExecPlan for the minimal prototype.
- [ ] Implement the minimal queue store, cluster store, domain tools, runner script, and focused tests.
- [ ] Verify the prototype with pytest and one local dry run that exercises sequential processing and emits LangFuse traces through the callback handler.

## Surprises & Discoveries

- Observation: the official OpenAI prompt guidance page the user referenced is specifically labeled for GPT-5.4, so the prompt design should follow that page directly instead of the older GPT-5.1 model guide.
  Evidence: the page title is "Prompt guidance for GPT-5.4" at `https://developers.openai.com/api/docs/guides/prompt-guidance/`.

- Observation: the simplest LangFuse integration for this prototype is the LangChain callback handler, not manual span management.
  Evidence: the LangFuse LangChain integration examples show `CallbackHandler()` passed in `config={"callbacks": [handler]}` to `invoke(...)`, which already captures LLM and tool traces automatically.

- Observation: the user does not want a delay scheduler or multi-run queue for uncertain tweets. The desired behavior is to defer uncertain tweets and revisit them later in the same run.
  Evidence: design confirmation during chat explicitly changed "wait for a next run" into "keep going sequentially and revisit in the same run".

- Observation: DeepAgents include a default set of built-in tools such as file editing, shell execution, todo writing, and subagent delegation.
  Evidence: the DeepAgents quickstart documentation states that every deep agent includes built-in tools like `write_todos`, `read_file`, `write_file`, `execute`, and `task`.

## Decision Log

- Decision: use one deep agent instead of multiple agents or subagents for the first milestone.
  Rationale: the first risk to retire is not delegation quality; it is whether one constrained agent can respect the queue contract and structured mutations.
  Date/Author: 2026-03-28 / Codex

- Decision: treat the incoming tweet list as a todo queue with explicit item status instead of as an immutable batch.
  Rationale: this mirrors the user’s mental model closely and gives the agent a formal way to make forward progress even when some tweets remain ambiguous.
  Date/Author: 2026-03-28 / Codex

- Decision: allow `deferred` tweets inside the same run and add a second pass over deferred items before finishing.
  Rationale: the user wants the model to be able to postpone uncertain assignments until more evidence emerges from later tweets, but not depend on a future scheduled run.
  Date/Author: 2026-03-28 / Codex

- Decision: use LangFuse as the primary observability layer through the callback handler and avoid extra manual observability machinery in the first cut.
  Rationale: the user explicitly rejected overcomplication here, and the callback handler is enough to inspect model and tool behavior in a prototype.
  Date/Author: 2026-03-28 / Codex

- Decision: keep tweet state and cluster state in local JSON files for the first milestone.
  Rationale: JSON is the fastest way to make the workflow inspectable, testable, and easy to discard or replace once the tool contracts stabilize.
  Date/Author: 2026-03-28 / Codex

- Decision: accept the presence of DeepAgents built-in tools in the runtime, but treat any domain-state access outside the explicit queue and cluster tools as incorrect behavior.
  Rationale: the quickstart documentation indicates that built-in tools are automatic, so the first milestone should constrain them through prompt and test expectations instead of adding custom runtime surgery before the prototype exists.
  Date/Author: 2026-03-28 / Codex

## Outcomes & Retrospective

The design is now narrowed to a small, testable prototype instead of a full autonomous clustering system. The biggest improvement from the design discussion is that the queue contract is now explicit: tweets are not merely read as context, they are work items that the agent must advance through status changes. The main remaining work is implementation and verification.

## Context and Orientation

The current repository already has three relevant building blocks. `src/xs2n/langchain_codex_oauth/` contains a ChatOpenAI-compatible facade that routes LangChain requests through Codex OAuth credentials instead of a plain `OPENAI_API_KEY`; this is the likely model transport for the new agent. `docs/codex/autolearning.md` records design notes and branch decisions for this repository and should capture any important reusable lessons from this feature. `pyproject.toml` is still minimal and does not yet declare `deepagents`, `langgraph`, or `langfuse`, so the implementation milestone must add the smallest dependency set needed by the prototype.

This plan uses four terms of art and defines them here. A "deep agent" is the agent runtime created by the `deepagents` package, which combines a model, tools, and internal planning behavior. A "queue" is the JSON file that tracks tweet work items and their status as the run progresses. A "cluster store" is the JSON file that holds the evolving list of clusters with title, description, and tweet membership. A "domain tool" is a tool exposed to the agent that reads or mutates tweet or cluster state in a controlled way; the agent must use these tools instead of editing domain files directly.

One implementation detail matters here: DeepAgents come with general built-in tools for file access, todos, shell execution, and delegation. The first milestone should not try to re-engineer that behavior away unless the package exposes a simple documented switch. Instead, the prompt and tests should make the intended contract explicit: domain state lives in the queue and cluster tools, and using built-in file or shell tools to change domain data counts as a bug.

The prototype should live in a new focused package so that orchestration, store logic, schemas, and tools stay easy to scan. The recommended module layout is:

- `src/xs2n/cluster_builder/schemas.py`
- `src/xs2n/cluster_builder/store.py`
- `src/xs2n/cluster_builder/tools.py`
- `src/xs2n/cluster_builder/agent.py`
- `scripts/run_cluster_builder.py`
- `tests/test_cluster_builder_store.py`
- `tests/test_cluster_builder_tools.py`
- `tests/test_run_cluster_builder.py`

The runtime artifacts should stay equally small:

- `data/cluster_builder/tweet_queue.json`
- `data/cluster_builder/cluster_list.json`

The queue file is the only input state the agent needs. Each queue item should include the tweet identity and the work-tracking fields the tools own. The smallest useful shape is:

    {
      "tweet_id": "post-1",
      "account_handle": "alice",
      "text": "Example tweet text",
      "url": "https://x.com/alice/status/post-1",
      "created_at": "2026-03-28T16:00:00Z",
      "status": "pending",
      "cluster_id": null,
      "processing_note": ""
    }

The cluster file should hold only structured cluster state, not free-form reasoning transcripts. The smallest useful shape is:

    {
      "cluster_id": "cluster_001",
      "title": "AI inference cost compression",
      "description": "Tweets pointing to lower serving costs and related economics.",
      "tweet_ids": ["post-1", "post-7"]
    }

## Plan of Work

Start by adding the new dependency surface to `pyproject.toml`. The prototype needs `deepagents` for the agent runtime, `langgraph` if required transitively by the chosen deep-agent APIs, and `langfuse` for tracing via the LangChain callback handler. Keep the existing repository style: minimal dependencies in the base project, with the smallest extra set that makes the feature run.

Then add `src/xs2n/cluster_builder/schemas.py`. This module should define only the shared contracts used across the queue store, cluster store, tools, and tests. It should include a queue item model, a cluster model, a mutation model for cluster updates, and any small typed result objects that tool calls return. The queue item model must support at least three statuses: `pending`, `deferred`, and `done`.

After the shared schemas exist, add `src/xs2n/cluster_builder/store.py`. This module should own all file IO for reading and writing the queue and cluster JSON files. It should expose obvious functions such as `load_tweet_queue`, `save_tweet_queue`, `load_cluster_list`, and `apply_cluster_mutation`. Keep control flow readable and direct. Do not hide meaningful behavior behind unnecessary wrappers. The store is also where the second-pass logic can discover whether deferred tweets still remain.

Then add `src/xs2n/cluster_builder/tools.py`. This file should expose the tool functions the agent can use. For the first milestone, the tool list should stay small and concrete: `count_remaining_tweets`, `get_next_tweet`, `read_tweet`, `defer_tweet`, `complete_tweet`, `list_clusters`, `read_cluster`, and `apply_cluster_mutation`. `count_remaining_tweets` should report counts by status rather than a single raw integer so the agent can tell whether it is still in the first pass or already revisiting deferred work. `get_next_tweet` should return the next `pending` item if any exist; if not, it should return the next `deferred` item. This gives the agent an obvious default path through the queue while still allowing a second pass without a separate scheduler.

Next add `src/xs2n/cluster_builder/agent.py`. This module should construct the model and the deep agent. Reuse the existing Codex OAuth LangChain facade from `src/xs2n/langchain_codex_oauth/chat_openai.py` unless the deep-agent runtime requires a different but still LangChain-compatible object. The prompt should be explicit and operational, following the GPT-5.4 prompt guidance in spirit: define the job, define the allowed tools, define the work order, define the conditions for deferring, and define what "done" means. The agent must be told to read and mutate only through domain tools, to process the queue incrementally, and to revisit deferred tweets before exiting.

The prompt should include these behavioral rules in plain language:

- Always start by checking how many tweets remain.
- Work one tweet at a time.
- Read the tweet before deciding anything.
- If the cluster assignment is clear, create or update a cluster through the cluster mutation tool and then mark the tweet complete.
- If the assignment is not clear yet, defer the tweet with a short reason and continue.
- After there are no pending tweets left, revisit deferred tweets.
- Do not invent tweet ids, cluster ids, or tool results.
- Do not write domain files directly.
- Ignore the built-in deep-agent file, shell, and delegation tools for domain work unless a later milestone explicitly allows them.
- Prefer stable, semantically honest cluster titles and descriptions over clever wording.

After the agent module exists, add `scripts/run_cluster_builder.py`. This script should be the one visible entrypoint for the prototype. It should accept at least a queue path, a cluster output path, and a model name. It should initialize LangFuse through environment variables and create a `CallbackHandler()` that is passed to the agent invocation. The script should print a short summary on success, such as how many tweets ended `done`, how many remain `deferred`, and how many clusters exist in the final file.

The final implementation step is tests. Add focused tests for store behavior, tool behavior, and the runner wiring. The store tests should prove that deferred and done transitions persist correctly. The tool tests should prove that cluster mutations and queue transitions happen only through the designed interfaces. The runner test should fake the deep-agent invocation and verify that LangFuse callbacks are passed in the LangChain config, because that is the chosen observability contract for the prototype. If the deep-agent runtime exposes invoked tool names in testable output, add one assertion that the happy-path prototype uses the domain tools for queue and cluster work.

## Concrete Steps

Run all commands from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

First, add the dependency surface and run the focused tests:

    uv sync --extra dev
    uv run pytest tests/test_cluster_builder_store.py tests/test_cluster_builder_tools.py tests/test_run_cluster_builder.py -q

Before implementation, the new tests should fail because the files and functions do not exist yet. After implementation, they should pass.

Once the prototype exists, exercise the runner against a tiny queue file:

    uv run python scripts/run_cluster_builder.py \
      --queue-file data/cluster_builder/tweet_queue.json \
      --cluster-file data/cluster_builder/cluster_list.json \
      --model gpt-5.4-mini

Expected behavior for a successful local dry run:

    Cluster builder completed.
    Tweets done: 4
    Tweets deferred: 1
    Clusters written: 2

The exact numbers will vary with the queue file, but the success transcript should include all three counts.

## Validation and Acceptance

Acceptance is behavioral. A developer should be able to create a tiny queue JSON file, run one command, and observe these outcomes:

First, the queue file changes from all `pending` items to a mix of `done` and possibly `deferred`, with each processed item carrying a `cluster_id` or a short processing note. Second, the cluster file contains the accumulated cluster list with titles, descriptions, and tweet membership. Third, the run appears in LangFuse through the callback handler without any extra manual tracing code in the runner.

The focused tests must also prove the local contract. `tests/test_cluster_builder_store.py` should prove the queue and cluster persistence logic. `tests/test_cluster_builder_tools.py` should prove the public tool semantics. `tests/test_run_cluster_builder.py` should prove that the runner creates the agent invocation with the expected callback configuration and summary behavior. If the runtime exposes tool-call traces in a deterministic way during tests, use that to prove the domain state changes came through the intended tools rather than accidental file editing.

## Idempotence and Recovery

The prototype should be safe to rerun on the same input files. Queue and cluster writes should overwrite the JSON files with the latest truthful state instead of appending ambiguous partial records. If a run stops halfway through, a developer should be able to inspect the JSON files, reset selected queue items from `done` or `deferred` back to `pending` manually, and rerun the command without hidden state elsewhere. LangFuse tracing is additive and should not block reruns.

If a dependency or prompt change causes agent behavior to regress, the safe fallback is to keep the queue and cluster tool contracts unchanged and swap only the agent prompt or runtime wiring. That is why the store and tools are separate modules instead of being embedded inside the runner.

## Artifacts and Notes

Important prompt shape for the prototype runner:

    You are a cluster builder deep agent.
    Your input work is a queue of tweets.
    Process tweets sequentially using tools.
    You may defer uncertain tweets and revisit them after all pending tweets are handled.
    You must create or update clusters only through structured cluster tools.
    You must mark each processed tweet through the queue tools.
    Do not invent ids or modify domain files directly.

Important LangFuse wiring shape for the runner:

    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    Langfuse()
    langfuse_handler = CallbackHandler()
    result = agent.invoke(
        {"messages": [{"role": "user", "content": run_prompt}]},
        config={"callbacks": [langfuse_handler]},
    )

## Interfaces and Dependencies

The implementation should keep the public interfaces concrete and honest.

In `src/xs2n/cluster_builder/schemas.py`, define:

    class TweetQueueItem(BaseModel):
        tweet_id: str
        account_handle: str
        text: str
        url: str
        created_at: str
        status: Literal["pending", "deferred", "done"]
        cluster_id: str | None = None
        processing_note: str = ""

    class QueueCounts(BaseModel):
        pending: int
        deferred: int
        done: int

    class Cluster(BaseModel):
        cluster_id: str
        title: str
        description: str
        tweet_ids: list[str]

    class ClusterMutation(BaseModel):
        action: Literal["create_cluster", "rename_cluster", "set_description", "add_tweets", "remove_tweets"]
        cluster_id: str | None = None
        title: str | None = None
        description: str | None = None
        tweet_ids: list[str] = Field(default_factory=list)

In `src/xs2n/cluster_builder/store.py`, define obvious store functions for queue and cluster persistence, including one function that applies a `ClusterMutation` deterministically.

In `src/xs2n/cluster_builder/tools.py`, define:

    def count_remaining_tweets(...) -> QueueCounts
    def get_next_tweet(...) -> dict | None
    def read_tweet(tweet_id: str, ...) -> dict
    def defer_tweet(tweet_id: str, reason: str, ...) -> dict
    def complete_tweet(tweet_id: str, cluster_id: str | None, reason: str, ...) -> dict
    def list_clusters(...) -> list[dict]
    def read_cluster(cluster_id: str, ...) -> dict
    def apply_cluster_mutation(mutation: ClusterMutation, ...) -> dict

In `src/xs2n/cluster_builder/agent.py`, expose one construction function:

    def build_cluster_builder_agent(*, model: str):
        ...

This function should create the Codex-authenticated LangChain model, build the deep agent with the domain tools, and return the runnable agent object.

Revision note (2026-03-28): Initial ExecPlan created after design approval. It captures the minimal one-agent, queue-first prototype and records the decision to use LangFuse through the callback handler instead of custom tracing code.
