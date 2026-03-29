# Cluster Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal cluster builder that processes a tweet queue sequentially, defers uncertain tweets within the same run, mutates clusters through structured tools, and emits LangFuse traces through the LangChain callback handler.

**Architecture:** The runtime uses one deep agent. It pages through queue state with `limit` and `offset`, reads one tweet at a time, evaluates it directly, and performs all queue and cluster mutations through explicit domain tools backed by local JSON stores.

**Tech Stack:** Python 3.11+, Pydantic, deepagents, LangGraph, LangFuse, existing `xs2n.langchain_codex_oauth` LangChain facade, pytest.

---

## File Structure

- Create: `src/xs2n/cluster_builder/__init__.py`
- Create: `src/xs2n/cluster_builder/schemas.py`
- Create: `src/xs2n/cluster_builder/store.py`
- Create: `src/xs2n/cluster_builder/tools.py`
- Create: `src/xs2n/cluster_builder/agent.py`
- Create: `scripts/run_cluster_builder.py`
- Create: `tests/test_cluster_builder_store.py`
- Create: `tests/test_cluster_builder_tools.py`
- Create: `tests/test_cluster_builder_agent.py`
- Create: `tests/test_run_cluster_builder.py`
- Modify: `pyproject.toml`
- Modify: `docs/codex/autolearning.md` only if implementation discoveries add new reusable guidance

### Task 1: Queue And Cluster Store Contracts

**Files:**
- Create: `src/xs2n/cluster_builder/__init__.py`
- Create: `src/xs2n/cluster_builder/schemas.py`
- Create: `src/xs2n/cluster_builder/store.py`
- Test: `tests/test_cluster_builder_store.py`

- [ ] **Step 1: Write the failing store tests**

Write tests that prove:
- queue items validate with `pending`, `deferred`, `done`
- `get_queue_items_page(...)` honors `status`, `limit`, `offset`, and `overview`
- `defer_tweet` persistence updates `status="deferred"` and `processing_note`
- `complete_tweet` persistence updates `status="done"` and `cluster_id`
- `apply_cluster_mutation` can create a cluster and add tweet ids deterministically

- [ ] **Step 2: Run the store tests to verify they fail**

Run: `uv run pytest tests/test_cluster_builder_store.py -q`

Expected: import or attribute errors because the new package does not exist yet.

- [ ] **Step 3: Write the minimal schemas**

Implement:
- `TweetQueueItem`
- `Cluster`
- `ClusterMutation`

Keep names honest and file scope narrow.

- [ ] **Step 4: Write the minimal store**

Implement:
- `load_tweet_queue(path)`
- `save_tweet_queue(path, items)`
- `load_cluster_list(path)`
- `save_cluster_list(path, clusters)`
- `get_queue_items_page(path, *, status, limit, offset, overview)`
- `defer_queue_tweet(path, *, tweet_id, reason)`
- `complete_queue_tweet(path, *, tweet_id, cluster_id, reason)`
- `apply_cluster_mutation(path, mutation)`

- [ ] **Step 5: Run the store tests until green**

Run: `uv run pytest tests/test_cluster_builder_store.py -q`

Expected: all tests pass.

### Task 2: Domain Tools Over The Store

**Files:**
- Create: `src/xs2n/cluster_builder/tools.py`
- Test: `tests/test_cluster_builder_tools.py`

- [ ] **Step 1: Write the failing tool tests**

Write tests that prove:
- `get_queue_items(...)` returns counts plus paginated items
- `read_tweet(tweet_id)` returns the full queue item
- `defer_tweet(...)` mutates the queue through store functions
- `complete_tweet(...)` mutates the queue through store functions
- `list_clusters()` and `read_cluster(cluster_id)` expose cluster state cleanly
- `apply_cluster_mutation(...)` forwards a validated mutation to the store

- [ ] **Step 2: Run the tool tests to verify they fail**

Run: `uv run pytest tests/test_cluster_builder_tools.py -q`

Expected: missing module or missing function failures.

- [ ] **Step 3: Implement the minimal tool layer**

Wrap store functions directly. Do not add pass-through wrappers that rename behavior without adding meaning. The only extra behavior allowed here is validation or result shaping that makes the tool contract clearer for the agent.

- [ ] **Step 4: Run the tool tests until green**

Run: `uv run pytest tests/test_cluster_builder_tools.py -q`

Expected: all tests pass.

### Task 3: Agent Wiring

**Files:**
- Create: `src/xs2n/cluster_builder/agent.py`
- Test: `tests/test_cluster_builder_agent.py`

- [ ] **Step 1: Write the failing agent-wiring tests**

Write tests that prove:
- `build_cluster_builder_agent(...)` creates a deep-agent runtime
- the runtime is configured without runtime subagents
- the agent prompt references paginated queue access, deferred revisits, and cluster mutation through tools
- the domain tools are exposed to the agent

- [ ] **Step 2: Run the agent tests to verify they fail**

Run: `uv run pytest tests/test_cluster_builder_agent.py -q`

Expected: missing module or build function failures.

- [ ] **Step 3: Implement minimal agent wiring**

Build:
- a shared LangChain-compatible model using `ChatOpenAICodexOAuth`
- one deep agent with the domain tools

The agent prompt must explicitly forbid direct domain-file editing and must tell the runtime to use queue paging with `limit` and `offset`.

- [ ] **Step 4: Run the agent tests until green**

Run: `uv run pytest tests/test_cluster_builder_agent.py -q`

Expected: all tests pass.

### Task 4: Runner And LangFuse Wiring

**Files:**
- Create: `scripts/run_cluster_builder.py`
- Test: `tests/test_run_cluster_builder.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write the failing runner tests**

Write tests that prove:
- CLI arguments parse `--queue-file`, `--cluster-file`, and `--model`
- the runner constructs `Langfuse()` and `CallbackHandler()`
- `agent.invoke(...)` receives `config={"callbacks": [handler]}`
- the script prints a summary with `done`, `deferred`, and cluster counts

- [ ] **Step 2: Run the runner tests to verify they fail**

Run: `uv run pytest tests/test_run_cluster_builder.py -q`

Expected: missing script or missing dependency wiring failures.

- [ ] **Step 3: Add dependencies to `pyproject.toml`**

Add the smallest dependency set needed for:
- deepagents runtime
- LangFuse callback handler
- LangGraph if needed by the chosen deepagents package

- [ ] **Step 4: Implement the runner minimally**

The runner should:
- load or create LangFuse client from environment
- build the multi-agent runtime
- invoke it with one fixed operational prompt
- read final queue and cluster files after the run
- print summary counts

- [ ] **Step 5: Run the runner tests until green**

Run: `uv run pytest tests/test_run_cluster_builder.py -q`

Expected: all tests pass.

### Task 5: Focused Verification

**Files:**
- Test: `tests/test_cluster_builder_store.py`
- Test: `tests/test_cluster_builder_tools.py`
- Test: `tests/test_cluster_builder_agent.py`
- Test: `tests/test_run_cluster_builder.py`

- [ ] **Step 1: Run the focused suite**

Run:
`uv run pytest tests/test_cluster_builder_store.py tests/test_cluster_builder_tools.py tests/test_cluster_builder_agent.py tests/test_run_cluster_builder.py -q`

Expected: all tests pass.

- [ ] **Step 2: Run a tiny local dry run**

Prepare a tiny `data/cluster_builder/tweet_queue.json` fixture and run:

`uv run python scripts/run_cluster_builder.py --queue-file data/cluster_builder/tweet_queue.json --cluster-file data/cluster_builder/cluster_list.json --model gpt-5.4-mini`

Expected:
- the queue file ends with only `done` and maybe `deferred`
- the cluster file exists and is valid JSON
- the terminal prints summary counts

- [ ] **Step 3: Record implementation discoveries**

If implementation reveals reusable preferences or runtime quirks, update `docs/codex/autolearning.md` with concise notes.
