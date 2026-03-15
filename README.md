# xs2n

`xs2n` is an early-stage CLI project for building a free-first X (Twitter) onboarding, timeline-ingestion, and digest-generation layer for a future summarization pipeline.

## Scope

This repository currently focuses on three foundations for downstream summarization:
- source onboarding
- timeline ingestion
- report digest scaffolding

In scope today:
- Normalize handles from pasted input (`@name`, `name`, `x.com/name`).
- Import followed accounts from X via Twikit (`--from-following`).
- Merge into a persistent deduplicated catalog (`data/sources.json`).
- Provide a recovery flow for Cloudflare `403` blocks during following import.
- Ingest posts, replies (thread-aware), and retweets from a specific account since a cutoff datetime.
- Persist deduplicated timeline entries for downstream processing (`data/timeline.json`), including engagement metrics used for virality.
- Generate a traceable markdown digest issue from timeline data (`xs2n report digest`).

Out of scope for now:
- Final production ranking/tuning.
- Delivery integrations such as email or LaTeX export.
- Scheduled/production orchestration.

## Current Status (WIP)

Milestone: **First digest scaffold on top of hardened ingestion**.

Working now:
- `xs2n onboard --paste`
- `xs2n onboard --from-following <handle>`
- `xs2n timeline --account <handle> --since <iso-datetime>`
- `xs2n timeline --from-sources --since <iso-datetime>`
- `xs2n report auth` (delegates ChatGPT/Codex authentication)
- `xs2n report digest` (traceable markdown issue scaffold with per-step artifacts)
- `xs2n report latest` (one command: ingest latest from onboarded sources, then render digest)
- `xs2n ui` (optional native desktop artifact browser for digest runs)
- Interactive mode selection when no onboarding mode is provided
- Local-browser cookie preflight (with profile selection) before Twikit login prompts
- Cloudflare block detection + local-browser cookie refresh + Playwright fallback + retry
- Unit tests for parsing, merge behavior, timeline fetching/storage, recovery flow, and digest scaffolding

Known gaps / WIP:
- Following and timeline imports still depend on Twikit behavior and can break if X internals change
- No full integration/e2e test for real X account flow in CI
- Digest uses a first OpenAI/LangChain scaffold and still needs richer editorial tuning
- No delivery automation yet (email/LaTeX are future steps)

## Quickstart (`uv`)

```bash
uv sync --extra dev
uv run xs2n --help
```

Optional desktop GUI setup:

```bash
uv sync --extra gui
```

On macOS, `pyfltk` also expects the native FLTK shared libraries from Homebrew:

```bash
brew install fltk
```

If you prefer one command bootstrap (including Playwright Chromium used for browser cookie recovery):

```bash
make setup
```

Convenience commands:

```bash
make setup
make run
make test
make wizard
```

## Usage

Paste handles interactively:

```bash
uv run xs2n onboard --paste
```

Import from following list:

```bash
uv run xs2n onboard --from-following your_screen_name --cookies-file cookies.json --limit 200
```

Interactive onboarding selector:

```bash
uv run xs2n onboard
uv run xs2n onboard --wizard
```

Ingest posts + replies + retweets from an account since a cutoff datetime:

```bash
uv run xs2n timeline --account your_screen_name --since 2026-03-01T00:00:00Z --cookies-file cookies.json --limit 500
```

Ingest posts + replies + retweets for all onboarded sources in `data/sources.json`:

```bash
uv run xs2n timeline --from-sources --since 2026-03-01T00:00:00Z --cookies-file cookies.json --limit 500
```

Ingest latest tweets from your authenticated Home -> Following feed:

```bash
uv run xs2n timeline --home-latest --since 2026-03-01T00:00:00Z --cookies-file cookies.json --limit 500
```

If `data/sources.json` is missing but legacy `data/sources.yaml` exists, `--from-sources` auto-migrates it to JSON before ingestion.

Rate-limit hardening and slower fetch options:

```bash
uv run xs2n timeline --from-sources --since 2026-03-01T00:00:00Z --slow-fetch-seconds 1.0 --page-delay-seconds 0.4 --wait-on-rate-limit
```

By default, timeline ingestion now waits/retries on X `429` and uses conservative pacing (`--slow-fetch-seconds 1.0`, `--page-delay-seconds 0.4`). Use `--no-wait-on-rate-limit` or set delays to `0` for a faster/fail-fast run.

Thread expansion options (bounded):

```bash
uv run xs2n timeline --account your_screen_name --since 2026-03-01T00:00:00Z --thread-parent-limit 120 --thread-replies-limit 240 --thread-other-replies-limit 120
```

- `--thread-parent-limit`: hydrate replied-to parent chain tweets (recursive upward).
- `--thread-replies-limit`: recursively include conversation replies.
- `--thread-other-replies-limit`: cap replies authored by non-target accounts.
- Set any of these to `0` to disable that expansion path.

Authenticate report-pipeline model access via Codex CLI (ChatGPT account flow):

```bash
uv run xs2n report auth
uv run xs2n report auth --device-auth
uv run xs2n report auth --status
uv run xs2n report auth --logout
```

If `codex` is not installed yet, install it first:

```bash
npm install -g @openai/codex
```

Generate a markdown digest issue from `data/timeline.json` using Codex auth:

```bash
uv run xs2n report auth --status
uv run xs2n report digest --model gpt-5.4
```

If you prefer the standard OpenAI API, `OPENAI_API_KEY` still works:

```bash
export OPENAI_API_KEY=your_key_here
uv run xs2n report digest --model gpt-4.1-mini
```

When the digest uses Codex auth, choose a Codex-supported GPT-5 model such as `gpt-5.4`.

Useful digest options:

```bash
uv run xs2n report digest \
  --timeline-file data/timeline.json \
  --output-dir data/report_runs \
  --taxonomy-file docs/codex/report_taxonomy.json \
  --parallel-workers 4
```

The digest command reads the thread-aware `timeline.json`, groups it into conversation threads, runs five simple steps, and writes one run folder per execution with intermediate JSON artifacts and a final `digest.md`. Each run folder now also freezes the taxonomy used for that run, records per-phase timing/count metadata in `phases.json`, and writes one JSON file per LLM call under `llm_calls/` so partial failures are easier to debug.

The `categorize_threads`, `filter_threads`, and `process_threads` phases now use a bounded worker pool. Tune it with `--parallel-workers` and set `--parallel-workers 1` if you want the old serial behavior for debugging or rate-limit troubleshooting.

`--parallel-workers` controls the bounded worker pool used by the high-volume `categorize_threads`, `filter_threads`, and `process_threads` steps. Use `1` to force serial execution when debugging or when rate limits are tight.

Run ingestion + digest end-to-end in one cron-friendly command:

```bash
uv run xs2n report latest --lookback-hours 24
uv run xs2n report latest --since 2026-03-01T00:00:00Z
uv run xs2n report latest --home-latest --lookback-hours 24
uv run xs2n report digest --parallel-workers 6
```

`xs2n report latest` first runs timeline ingestion (from `data/sources.json` by default, or Home -> Following when `--home-latest` is enabled), then runs `xs2n report digest` on the updated `data/timeline.json`.

Browse run artifacts in a native desktop app:

```bash
uv run xs2n ui
uv run xs2n ui --data-dir data
```

The desktop browser is intentionally simple. It scans every `data/report_runs*` directory, shows the discovered run folders on the left, the available artifacts in the middle, and the selected file content on the right. It is read-only for artifact inspection, but it can stay aligned with the existing CLI by exposing refresh and run actions through the same command surface.

If `pyfltk` fails to import on macOS with a missing `libfltk*.dylib` error, install Homebrew FLTK and retry:

```bash
brew install fltk
uv sync --extra gui
uv run xs2n ui
```

Output files:

```text
data/sources.json
data/timeline.json
data/report_runs/<run_id>/taxonomy.json
data/report_runs/<run_id>/threads.json
data/report_runs/<run_id>/categorized_threads.json
data/report_runs/<run_id>/filtered_threads.json
data/report_runs/<run_id>/processed_threads.json
data/report_runs/<run_id>/issue_assignments.json
data/report_runs/<run_id>/issues.json
data/report_runs/<run_id>/phases.json
data/report_runs/<run_id>/llm_calls/*.json
data/report_runs/<run_id>/run.json
data/report_runs/<run_id>/digest.md
```

## Tests

```bash
uv run pytest
```

## Project Notes

- Autolearning and milestone notes: `docs/codex/autolearning.md`
- Execution plans: `docs/codex/execplans/`
- Desktop artifact browser plan: `docs/codex/execplans/ui-artifact-browser.md`
- Digest taxonomy starter file: `docs/codex/report_taxonomy.json`

## Legacy Install (pip)

```bash
python -m pip install -e .[dev]
xs2n --help
```
