# xs2n

`xs2n` is an early-stage CLI project for building a free-first X (Twitter) onboarding, timeline-ingestion, and issue-digest generation layer for a future summarization pipeline.

## Scope

This repository currently focuses on three foundations for downstream summarization:
- source onboarding
- timeline ingestion
- issue-digest scaffolding

In scope today:
- Normalize handles from pasted input (`@name`, `name`, `x.com/name`).
- Import followed accounts from X via Twikit (`--from-following`).
- Merge into a persistent deduplicated catalog (`data/sources.json`).
- Provide a recovery flow for Cloudflare `403` blocks during following import.
- Ingest posts, replies (thread-aware), and retweets from a specific account since a cutoff datetime.
- Persist deduplicated timeline entries for downstream processing (`data/timeline.json`), including engagement metrics used for virality.
- Build issue artifacts from timeline data (`xs2n report issues`).
- Render a simple HTML digest from a saved run (`xs2n report html`, with `xs2n report render` kept as a compatibility alias).
- Define portable schedule definitions for the latest issue flow (`xs2n report schedule ...`).

Out of scope for now:
- Final production ranking/tuning.
- Delivery integrations such as email or LaTeX export.
- Scheduled/production orchestration.

## Current Status (WIP)

Milestone: **CLI-first issue digest on top of hardened ingestion**.

Working now:
- `xs2n onboard --paste`
- `xs2n onboard --from-following <handle>`
- `xs2n onboard --refresh-following`
- `xs2n timeline --account <handle> --since <iso-datetime>`
- `xs2n timeline --from-sources --since <iso-datetime>`
- `xs2n report auth` (delegates ChatGPT/Codex authentication)
- `xs2n auth doctor` (machine-readable auth health for Codex + X/Twitter)
- `xs2n auth x login` / `xs2n auth x reset` (explicit X/Twitter session management)
- `xs2n report issues` (loose filter + sequential issue-building with per-step artifacts)
- `xs2n report html` (deterministic HTML render from saved issue artifacts, with `report render` kept as an alias)
- `xs2n report latest` (one command: ingest latest from onboarded sources, build issues, then render HTML)
- `xs2n report schedule` (portable schedule definitions, overlap-safe runner, and export-only OS job output)
- `xs2n ui` (optional native desktop artifact browser for digest runs)
- Desktop auth center with separate `Codex` and `X / Twitter` sections plus pre-run auth guard
- Interactive mode selection when no onboarding mode is provided
- Local-browser cookie preflight (with profile selection) before Twikit login prompts
- Cloudflare block detection + local-browser cookie refresh + Playwright fallback + retry
- Unit tests for parsing, merge behavior, timeline fetching/storage, recovery flow, and digest scaffolding

Known gaps / WIP:
- Following and timeline imports still depend on Twikit behavior and can break if X internals change
- No full integration/e2e test for real X account flow in CI
- The new issue builder still needs editorial tuning and stronger real-world prompting
- No delivery automation yet (email/LaTeX are future steps)
- No native scheduler installation yet; `report schedule` only exports install-ready `cron` / `launchd` / `systemd` output in v1

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

Refresh the stored sources catalog from the currently authenticated account's following list:

```bash
uv run xs2n onboard --refresh-following --cookies-file cookies.json --sources-file data/sources.json
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

Check the combined auth/readiness snapshot consumed by the desktop UI:

```bash
uv run xs2n auth doctor --json
uv run xs2n auth doctor --json --cookies-file tmp/cookies.json
```

Refresh or clear the X/Twitter session cookies used by timeline/report runs:

```bash
uv run xs2n auth x login --cookies-file cookies.json
uv run xs2n auth x reset --cookies-file cookies.json
```

If `codex` is not installed yet, install it first:

```bash
npm install -g @openai/codex
```

Build issue artifacts from `data/timeline.json` using Codex auth:

```bash
uv run xs2n report auth --status
uv run xs2n report issues --model gpt-5.4-mini
```

If you prefer the standard OpenAI API, `OPENAI_API_KEY` still works:

```bash
export OPENAI_API_KEY=your_key_here
uv run xs2n report issues --model gpt-5.4-mini
```

When the issue pipeline uses Codex auth, choose a Codex-supported GPT-5 model such as `gpt-5.4-mini`.

Useful issue-build options:

```bash
uv run xs2n report issues \
  --timeline-file data/timeline.json \
  --output-dir data/report_runs \
  --model gpt-5.4-mini
```

`xs2n report issues` reads the thread-aware `timeline.json`, groups it into source-authored conversation threads, runs a very loose stupid-filter, then assigns kept threads into issues sequentially. Each run folder writes the intermediate JSON artifacts plus `phases.json`, `run.json`, and one JSON file per model call under `llm_calls/`.

The current pipeline is intentionally simple:
- `load_threads`
- `filter_threads`
- `group_issues`

To render a saved run into HTML:

```bash
uv run xs2n report html --run-dir data/report_runs/<run_id>
```

`xs2n report render --run-dir ...` still works as a compatibility alias.

Run ingestion + digest end-to-end in one cron-friendly command:

```bash
uv run xs2n report latest --lookback-hours 24
uv run xs2n report latest --since 2026-03-01T00:00:00Z
uv run xs2n report latest --home-latest --lookback-hours 24
```

`xs2n report latest` first runs timeline ingestion (from `data/sources.json` by default, or Home -> Following when `--home-latest` is enabled), then snapshots only the requested time window into the run folder, builds issues from that snapshot, and renders `digest.html`.

Define and export named schedules for the latest issue flow:

```bash
uv run xs2n report schedule create morning --at 08:30 --weekdays mon,wed,fri --lookback-hours 24
uv run xs2n report schedule list
uv run xs2n report schedule show morning
uv run xs2n report schedule run morning
uv run xs2n report schedule export morning --target cron
uv run xs2n report schedule export morning --target launchd
uv run xs2n report schedule export morning --target systemd
uv run xs2n report schedule delete morning
```

`xs2n report schedule` stores named definitions in `data/report_schedules.json`, uses `data/report_schedule_locks/<name>.lock` to prevent overlap, records `last_run` on success/failure/lock-skip, and prints install-ready scheduler output without mutating the OS in v1.

Browse run artifacts in a native desktop app:

```bash
uv run xs2n ui
uv run xs2n ui --data-dir data
```

The desktop browser is intentionally simple. It scans every `data/report_runs*` directory, shows the discovered run folders on the left, the available artifacts in the middle, and the selected file content on the right. It is read-only for artifact inspection, but it stays aligned with the existing CLI by exposing refresh and the primary `report latest` run action through the same command surface.

Open `File -> Preferences` to edit the issues/latest run arguments used by the launch buttons before starting a new command from the UI. Draft edits stay local to the Preferences window until you click `Apply`; `Cancel` discards them.

Open `File -> Authentication` to inspect or refresh auth state. The window shows separate `Codex` and `X / Twitter` sections, always using the currently applied `Latest` cookies path from Preferences. When the UI launches `report latest`, it first runs `xs2n auth doctor --json` and blocks the run if the required auth state is not ready.

The `Run` menu also includes a dedicated action to refresh `data/sources.json` from the authenticated account's current following list. The UI does not reimplement this flow; it launches the same `xs2n onboard --refresh-following` shortcut and shows the transcript in the viewer.

Primary HTML artifacts such as `digest.html` now render as documents in the right-hand pane instead of raw source text. Markdown, JSON, logs, directories, and command output still render through the preview pipeline as appropriate.

On macOS, the native app menu is also trimmed down to `xn2s` with only `About xn2s` and `Quit xn2s`, so the desktop tool feels more like a small utility app than a generic Python host window.

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
data/report_runs/<run_id>/timeline_window.json
data/report_runs/<run_id>/threads.json
data/report_runs/<run_id>/filtered_threads.json
data/report_runs/<run_id>/issue_assignments.json
data/report_runs/<run_id>/issues.json
data/report_runs/<run_id>/phases.json
data/report_runs/<run_id>/llm_calls/*.json
data/report_runs/<run_id>/run.json
data/report_runs/<run_id>/digest.html
```

## Tests

```bash
uv run pytest
```

## Project Notes

- Autolearning and milestone notes: `docs/codex/autolearning.md`
- Execution plans: `docs/codex/execplans/`
- Desktop artifact browser plan: `docs/codex/execplans/ui-artifact-browser.md`

## Legacy Install (pip)

```bash
python -m pip install -e .[dev]
xs2n --help
```
