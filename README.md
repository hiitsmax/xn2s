# xs2n

`xs2n` is an early-stage CLI project for building a free-first X (Twitter) source onboarding layer for a future timeline summarization pipeline.

## Scope

This repository currently focuses on one thing: **collecting and storing profile sources** that will later feed ranking/scraping/summarization steps.

In scope today:
- Normalize handles from pasted input (`@name`, `name`, `x.com/name`).
- Import followed accounts from X via Twikit (`--from-following`).
- Merge into a persistent deduplicated catalog (`data/sources.yaml`).
- Provide a recovery flow for Cloudflare `403` blocks during following import.

Out of scope for now:
- Timeline scraping and content extraction.
- Ranking or signal scoring.
- Summarization generation and delivery.
- Scheduled/production orchestration.

## Current Status (WIP)

Milestone: **CLI onboarding hardening**.

Working now:
- `xs2n onboard --paste`
- `xs2n onboard --from-following <handle>`
- Interactive mode selection when no onboarding mode is provided
- Local-browser cookie preflight (with profile selection) before Twikit login prompts
- Cloudflare block detection + local-browser cookie refresh + Playwright fallback + retry
- Unit tests for parsing, merge behavior, and recovery flow

Known gaps / WIP:
- No dedicated `auth` command set yet (`auth login/check` still pending)
- Following import still depends on Twikit behavior and can break if X internals change
- No full integration/e2e test for real X account flow in CI
- No summarization pipeline yet (this repo is onboarding-only at the moment)

## Quickstart (`uv`)

```bash
uv sync --extra dev
uv run xs2n --help
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

Output catalog:

```text
data/sources.yaml
```

## Tests

```bash
uv run pytest
```

## Project Notes

- Autolearning and milestone notes: `docs/codex/autolearning.md`
- Execution plans: `docs/codex/execplans/`

## Legacy Install (pip)

```bash
python -m pip install -e .[dev]
xs2n --help
```
