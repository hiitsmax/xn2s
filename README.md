# xs2n

`xs2n` is now a minimal Python base for two things only:

- Codex authentication bootstrap
- one cluster builder CLI over a tweet queue
- one automatic digest CLI over tracked X handles

The repository currently keeps both automation surfaces because they solve different jobs on top of the same Codex-authenticated runtime.

## Install

```bash
uv sync --extra dev
```

If you need the Codex CLI for ChatGPT-backed auth:

```bash
npm install -g @openai/codex
```

## Auth

Use the auth helper script to log into Codex, check status, or log out:

```bash
python scripts/codex_auth.py login
python scripts/codex_auth.py login --device-auth
python scripts/codex_auth.py status
python scripts/codex_auth.py logout
```

The script delegates to the official Codex CLI and leaves token storage in Codex's own location.

## Cluster Builder CLI

The cluster builder starts from a queue JSON file of tweets, processes the queue to completion through explicit queue and cluster tools, and writes the resulting cluster JSON file in place.

Run the cluster builder:

```bash
uv run python scripts/run_cluster_builder.py \
  --queue-file data/cluster_builder/tweet_queue.json \
  --cluster-file data/cluster_builder/cluster_list.json \
  --model gpt-5.4-mini
```

The queue file is an array of tweet work items. The smallest useful item looks like this:

```bash
[
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
]
```

The cluster file can start as an empty array:

```bash
[]
```

The runner uses the Codex OAuth facade, so the main auth path is the local Codex login state managed by `scripts/codex_auth.py`.

If `LANGFUSE_*` environment variables are configured, the run is also traced through LangFuse via the standard LangChain callback handler.

## Digest CLI

The automatic digest runner reads tracked handles from `data/handles.json`, fetches recent tweets into the application's `Thread` model, and writes one final `digest.json`.

Run the digest job:

```bash
uv run python scripts/run_agentic_pipeline.py \
  --output-file digest.json
```

Optional flags:

```bash
uv run python scripts/run_agentic_pipeline.py \
  --output-file digest.json \
  --hours 12 \
  --model gpt-5.4-mini
```

The fetch layer prefers `ntscraper` / Nitter first. If Nitter cannot fetch its instance catalog or has no working instances, the runtime falls back to authenticated X / Twitter profile fetches using your local session cookies.

Cookie discovery order:

1. Google Chrome cookies on macOS, scanning all profiles with `Default` first
2. `TWITTER_COOKIES`
3. `TWITTER_COOKIES_FILE`
4. one final Chrome retry before failing

The authenticated fallback stores its `twscrape` session state outside the repository by default:

```bash
~/Library/Application Support/xs2n/twscrape/accounts.db
```

Override that location with:

```bash
export XS2N_TWSCRAPE_STATE_DIR="$HOME/.local/share/xs2n/twscrape"
```

For large handle lists, the authenticated fallback processes handles in small fixed batches, retries each failing handle with a small per-handle budget, and then asks in the terminal whether to retry the failed handles again, continue without them, or stop the run.

## Tests

```bash
uv run pytest \
  tests/test_cluster_builder_store.py \
  tests/test_cluster_builder_tools.py \
  tests/test_cluster_builder_agent.py \
  tests/test_run_cluster_builder.py \
  tests/test_codex_auth.py \
  tests/test_langchain_codex_oauth.py \
  tests/test_llm.py \
  tests/test_pipeline.py \
  tests/test_twitter.py \
  tests/test_run_agentic_pipeline.py \
  tests/test_twitter_cookies.py \
  tests/test_twitter_nitter_net.py \
  tests/test_twitter_twscrape.py -q
```
