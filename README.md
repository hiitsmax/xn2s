# xs2n

`xs2n` is now a minimal Python base for two things only:

- Codex authentication bootstrap
- one fetch-first agentic digest CLI over tracked X handles

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

## Digest CLI

The digest script starts by reading tracked handles from `data/handles.json`, fetches recent tweets with `ntscraper`/Nitter, shapes them into the application's `Thread` model, and writes one final `digest.json`.

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

Use `OPENAI_API_KEY` if you want standard API auth. Otherwise the digest pipeline reads Codex auth from the local Codex login state.

## Tests

```bash
uv run pytest tests/test_codex_auth.py tests/test_llm.py tests/test_pipeline.py tests/test_twitter.py tests/test_run_agentic_pipeline.py -q
```
