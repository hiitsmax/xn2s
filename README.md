# xs2n

`xs2n` is now a minimal Python base for two things only:

- Codex authentication bootstrap
- one agentic digest pipeline over preassembled thread input

Everything else from the previous wider product surface was intentionally removed on this branch.

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

## Pipeline

The pipeline script expects a JSON file with preassembled threads and writes one final `digest.json`.

Example input:

```json
{
  "threads": [
    {
      "thread_id": "thread-1",
      "account_handle": "alice",
      "posts": [
        {
          "post_id": "post-1",
          "author_handle": "alice",
          "created_at": "2026-03-21T10:00:00Z",
          "text": "AI inference costs are dropping fast.",
          "url": "https://x.com/alice/status/post-1"
        }
      ]
    }
  ]
}
```

Run the pipeline:

```bash
python scripts/run_agentic_pipeline.py \
  --input-file sample_threads.json \
  --output-file digest.json
```

Use `OPENAI_API_KEY` if you want standard API auth. Otherwise the pipeline reads Codex auth from the local Codex login state.

## Tests

```bash
uv run pytest tests/test_codex_auth.py tests/test_pipeline.py -q
```
