# xs2n

`xs2n` now exposes one main runner plus one auth helper.

The active runtime is intentionally small:

- `src/xs2n/run.py` is the single pipeline entrypoint.
- `src/xs2n/agents/base_agent.py` is a minimal base agent that uses the repository's ChatGPT/Codex auth wiring.
- `src/xs2n/agents/text_router/` classifies queue items into plain, ambiguous, image-led, and external-led buckets.
- `src/xs2n/agents/issue_organizer/` groups the non-ambiguous queue items into strict JSON issue records.
- `src/xs2n/utils/` keeps tweet fetching (Nitter RSS) and Codex/OpenAI auth helpers; `src/xs2n/tools/` keeps persisted queue and cluster state.

## Layout

The source tree is organized by honest ownership:

- `src/xs2n/agents/` contains the base agent and future domain agents.
- `src/xs2n/utils/` contains tweet fetching, Codex/OpenAI auth, and tracing helpers.
- `src/xs2n/tools/` contains JSON state and agent-bound queue tools.
- `src/xs2n/prompts/` contains prompt assets and `manager.py`.
- `src/xs2n/schemas/` contains shared data contracts.
- `src/xs2n/run.py` and `src/xs2n/auth.py` are package entrypoints.

## Install

```bash
uv sync --extra dev
```

The default environment includes Phoenix tracing support for the OpenAI Agents SDK runtime.

If you need the Codex CLI for ChatGPT-backed auth:

```bash
npm install -g @openai/codex
```

## Auth

Use the auth helper to log into Codex, check status, or log out:

```bash
uv run xs2n-auth login
uv run xs2n-auth login --device-auth
uv run xs2n-auth status
uv run xs2n-auth logout
```

The helper delegates to the official Codex CLI and leaves token storage in Codex's own location. The base agent consumes that existing auth state through `src/xs2n/utils/auth/openai_client.py`.

## Phoenix Tracing

The scaffold runtime boots Phoenix tracing automatically through the official Phoenix/OpenInference OpenAI Agents SDK integration.

Default local behavior:

```bash
PHOENIX_COLLECTOR_ENDPOINT=http://127.0.0.1:6006/v1/traces
PHOENIX_PROJECT_NAME=xs2n
```

If those variables are unset, `xs2n` uses the defaults above so a local Phoenix instance can receive traces immediately.

To disable tracing for one run:

```bash
XS2N_DISABLE_TRACING=1 uv run xs2n \
  --tweet-list-file data/cluster_builder/tweet_queue.json
```

With tracing enabled, run the CLI and open `http://localhost:6006` to inspect the scaffold trace.

## Main CLI

`src/xs2n/run.py` owns the runtime order directly:

1. If `--tweet-list-file` is provided, load that file and skip the fetch step.
2. Otherwise fetch recent tracked-handle posts and build the queue.
3. Write the working queue to `--queue-file`.
4. Run the base Agents SDK scaffold against that prepared queue.

Fetch fresh tweets and run the scaffold:

```bash
uv run xs2n \
  --hours 24 \
  --model gpt-5.4-mini
```

Reuse an existing tweet list and skip fetch:

```bash
uv run xs2n \
  --tweet-list-file data/cluster_builder/tweet_queue.json \
  --queue-file data/cluster_builder/tweet_queue.json \
  --model gpt-5.4-mini
```

Run the strict text router against the prepared queue and print the grouped ids:

```bash
uv run xs2n \
  --tweet-list-file data/cluster_builder/tweet_queue.json \
  --route-text \
  --model gpt-5.4-mini
```

The router prints one compact line in this fixed order:

```text
plain_ids|ambiguous_ids|image_ids|external_ids
```

Run the issue organizer against the prepared queue. This first routes the queue, drops ambiguous tweets, and prints the validated issue JSON:

```bash
uv run xs2n \
  --tweet-list-file data/cluster_builder/tweet_queue.json \
  --build-issues \
  --model gpt-5.4-mini
```

The scaffold is intentionally not the final domain architecture. It proves the minimal Agents SDK loop, the queue handoff, and the ChatGPT/Codex auth path in one place so the next agentic redesign can start from a truthful baseline.

## Tests

```bash
uv run pytest \
  tests/test_openai_client.py \
  tests/test_codex_auth.py \
  tests/test_twitter.py \
  tests/test_twitter_nitter_rss.py \
  tests/test_cluster_builder_thread_queue.py \
  tests/test_cluster_builder_store.py \
  tests/test_cluster_builder_tools.py \
  tests/test_tracing.py \
  tests/test_base_agent.py \
  tests/test_run.py -q
```
