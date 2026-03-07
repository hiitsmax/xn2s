# xs2n Autolearning Framework

## Goal

Continuously improve this codebase by capturing implementation choices, fragility points, and hardening opportunities after each milestone.

## Loop

1. Build a narrow milestone with observable output.
2. Record what worked and where it was brittle.
3. Add tests for deterministic parts.
4. Add one operational hardening step in the next milestone.
5. Repeat.

## Current Milestone Notes (2026-03-01)

- Implemented onboarding CLI with two paths:
  - Manual paste of handles or profile URLs.
  - Import from account followings via Twikit.
- Added deterministic tests for parsing and dedupe merge behavior.
- Stored source profiles in `data/sources.json` to keep downstream pipeline simple.

## Known Fragility

- Twikit behavior can change when X changes internal endpoints.
- Fresh Context7 lookup is currently unavailable (`Transport closed`), so docs were verified from primary upstream repositories directly.
- Login flow can fail for accounts with additional verification challenges.

## Next Hardening Candidates

1. Add `xs2n auth login` and `xs2n auth check` commands for explicit session management.
2. Add a retry/backoff wrapper around Twikit calls for transient failures.
3. Add a local Playwright fallback collector for profile pages when Twikit fails.
4. Add integration tests with mocked Twikit responses.

## Refactor Notes (2026-03-01)

- Moved Twikit authentication prompt and session bootstrap into `src/xs2n/profile/auth.py`.
- Moved following-import runtime and normalization usage into `src/xs2n/profile/following.py` + `src/xs2n/profile/helpers.py`.
- Introduced `src/xs2n/cli/__init__.py` to expose `app` for `xs2n.cli:app` entrypoint compatibility.
- Fixed CLI parameter plumbing so paste onboarding and following import both call shared helpers with correct types.
- Removed `src/xs2n/onboarding.py` compatibility indirection and updated imports to use `profile.helpers`/`profile.types` directly to keep module ownership clear.
- Extracted the `onboard` command flow into `src/xs2n/cli/onboard.py`, keeping `src/xs2n/cli/cli.py` focused on app bootstrap and command registration.

## Developer Experience Notes (2026-03-01)

- Switched onboarding docs to a `uv`-first flow (`uv sync --extra dev`, `uv run ...`) for a faster and more predictable local setup.
- Added a `Makefile` with short aliases (`make setup`, `make run`, `make test`) to mirror Node-style script ergonomics.
- Kept legacy `pip install -e .[dev]` instructions as a fallback to reduce adoption risk for contributors without `uv`.

## Onboarding Input Normalization (2026-03-01 22:19Z)

- Added a dedicated CLI helper to normalize `--from-following` input through shared handle parsing rules.
- Interactive wizard now accepts `mx`, `@mx`, and `https://x.com/mx` with identical behavior.
- Added tests to verify consistent normalization and invalid-input rejection for following account selection.
- Updated onboarding UX: `xs2n onboard` without mode now prints explicit mode examples; interactive behavior is opt-in via `--wizard`.

## Cloudflare Recovery UX (2026-03-01 23:40Z)

- Added targeted handling for Twikit `403` Cloudflare blocks during `--from-following` onboarding.
- When a Cloudflare block is detected, CLI now explains the issue and asks to open browser login for cookie bootstrap.
- Implemented Playwright-based browser cookie bootstrap (`cookies.json`) and automatic retry after successful login.
- Added tests for Cloudflare detection plus retry/decline recovery paths.

## Username Inference UX (2026-03-01 23:59Z)

- Reused the onboarding X screen name as default for the Twikit `Username (without @)` login prompt.
- Kept the prompt editable so users can override when login username differs from public handle.
- Added auth-focused tests to lock inferred-username wiring between onboarding flow and authentication prompt.

## Playwright Dependency Hardening (2026-03-01)

- Promoted `playwright` to core project dependency in `pyproject.toml`.
- Added automatic Chromium install/retry when browser-cookie bootstrap detects missing Playwright browser binaries.
- Updated setup flow (`make setup`) to provision Chromium ahead of first interactive recovery attempt.
- Added auth recovery tests covering missing-browser error detection and installer failure surfacing.

## Onboard Prompt Memory Defaults (2026-03-01)

- Added persistent onboarding state in `data/onboard_state.json`.
- Interactive `xs2n onboard` now defaults to the last used mode (`paste` or `following`).
- When `following` mode is selected interactively, the previous handle is pre-filled as the prompt default.
- Added tests for default-mode recall, default-handle recall, and state persistence from explicit `--from-following` input.

## Browser Cookie Bootstrap (2026-03-01)

- Added `browser-cookie3` dependency to read authenticated cookies from installed user browsers.
- Recovery flow now tries local browser cookie import before asking users to log in in a Playwright window.
- Kept Playwright interactive login as fallback when no usable local browser cookies are available.
- Added deterministic tests for browser-cookie extraction logic and updated onboarding recovery tests for local-first fallback behavior.

## Browser Profile Selection Preflight (2026-03-01)

- Added local-cookie preflight before first Twikit import attempt when `cookies.json` is missing.
- Introduced browser-cookie candidate discovery with dedupe by session token pair (`auth_token`, `ct0`).
- Added interactive session selection when multiple logged-in browser sessions are discovered.
- Added profile labels (`@screen_name` when resolvable) to make selection explicit and reduce wrong-account imports.
- Added tests for candidate selection UI and preflight-before-first-attempt behavior.

## Timeline Scraping Pipeline (2026-03-02)

- Added `xs2n timeline --account <handle> --since <iso-datetime>` to ingest posts and retweets for a target account.
- Implemented Twikit timeline pagination with cutoff filtering and dedupe guards in `src/xs2n/profile/timeline.py`.
- Classified retweets using `tweet.retweeted_tweet` and skipped replies for a strict posts+retweets ingestion set.
- Added dedicated timeline persistence in `data/timeline.json` via `src/xs2n/timeline_storage.py`.
- Reused the existing Cloudflare/browser-cookie recovery strategy in the new timeline CLI path for operational consistency.
- Added deterministic tests for timeline fetcher behavior, storage merge idempotence, and timeline CLI recovery flow.

## Data Folder JSON Standardization (2026-03-02)

- Standardized all CLI-managed `data/` persistence to JSON (`sources`, `timeline`, and onboarding state).
- Updated default paths to `data/sources.json`, `data/timeline.json`, and `data/onboard_state.json`.
- Replaced YAML serialization with stdlib `json` across storage helpers and corresponding tests.
- Updated docs and examples so command outputs match JSON defaults end-to-end.

## Batch Timeline Ingestion From Sources (2026-03-02)

- Added `xs2n timeline --from-sources --sources-file <path>` to ingest all handles from the source catalog in one run.
- Added command validation to enforce either `--account` or `--from-sources`.
- Added legacy migration support: if `sources.json` is missing and matching `sources.yaml` exists, it is converted automatically.
- Added tests covering batch-mode handle loading, option validation, and YAML-to-JSON migration on first run.

## Timeline Rate-Limit Waiting And Throttling (2026-03-02)

- Added automatic active waiting on X `429` responses with retry progress logs and capped retry counts.
- Added configurable fetch throttling via `--slow-fetch-seconds` (between accounts) and `--page-delay-seconds` (between timeline page requests).
- Added rate-limit controls (`--wait-on-rate-limit`, wait/poll/max options) so runs can be either resilient or fail-fast.
- Added tests for wait-and-retry behavior, slower batch pacing, and pagination delay wiring.

## Timeline Thread-Aware Capture (2026-03-03)

- Updated timeline fetch to merge both `Tweets` and `Replies` feeds, so account thread continuations are no longer dropped.
- Added reply/thread linkage metadata to timeline records: `in_reply_to_tweet_id`, `conversation_id`, and `timeline_source`.
- Kept the storage shape flat and deduplicated by `tweet_id` to preserve existing downstream merge behavior.
- Added tests covering reply inclusion, kind classification (`post`/`reply`/`retweet`), and persistence of thread metadata fields.

## Thread Context Expansion Limits (2026-03-03)

- Added bounded thread-context hydration during timeline import:
  - parent-chain hydration for replies (`thread_parent` source),
  - recursive conversation reply expansion (`thread_reply` source),
  - dedicated cap for non-target-account replies.
- Exposed controls via CLI:
  - `--thread-parent-limit`
  - `--thread-replies-limit`
  - `--thread-other-replies-limit`
- Added tests locking limit behavior for parent-chain hydration and cross-author reply caps.

## Report Auth Bootstrap (2026-03-03)

- Added a new `report` CLI group with `xs2n report auth` as the first report-pipeline primitive.
- Wired `report auth` to delegate authentication to official Codex CLI flows:
  - `codex login` (ChatGPT OAuth),
  - `codex login --device-auth`,
  - `codex login status`,
  - `codex logout`.
- Added process hardening for missing `codex` binary and non-zero exit propagation.
- Added deterministic unit tests for login/status/logout routing and error handling.

## Storage Package Boundary (2026-03-07)

- Moved CLI-managed persistence into a dedicated `src/xs2n/storage/` package.
- Split storage ownership into `sources.py`, `timeline.py`, and `onboard_state.py` to match the three persisted documents managed by the app.
- Removed onboarding-state JSON read/write logic from `src/xs2n/cli/helpers.py` so the CLI layer now consumes storage helpers instead of implementing them.
- Kept `src/xs2n/timeline_storage.py` as a thin compatibility wrapper while internal code moved to `xs2n.storage`.

## Report Digest Scaffold (2026-03-07)

- Added `xs2n report digest` as the first runnable digest-generation command.
- Built the digest scaffold in the `src/xs2n/agents/digest/` package with a simpler split:
  - `pipeline.py` for models, orchestration, and deterministic steps,
  - `llm.py` for the semantic model-facing logic.
  It still writes explicit step artifacts:
  - selected timeline entries,
  - conversation candidates,
  - assembled units,
  - categorized/filtered units,
  - extracted signals,
  - clustered issues,
  - final markdown digest.
- Introduced `data/report_state.json` and `src/xs2n/storage/report_state.py` so heated threads can be revisited across runs.
- Added a checked-in editable taxonomy starter file at `docs/codex/report_taxonomy.json`.
- Used LangChain structured output with an OpenAI model wrapper for semantic steps while keeping numeric scoring and state tracking deterministic.
- Extended timeline persistence with `favorite_count`, `retweet_count`, `reply_count`, `quote_count`, and `view_count`.
- Changed timeline merge behavior so re-seen tweets refresh stored engagement metrics instead of freezing them at first ingest.
- Added tests for virality extraction, duplicate refresh behavior, heated-thread carry-over, digest CLI routing, and a fake-LLM end-to-end digest run.
- Refactored the original digest monolith into a flatter `src/xs2n/agents/digest/` package centered on `pipeline.py` and the model wrapper module, after the more granular split proved too abstract for the current codebase size.

## Digest Pipeline Simplification (2026-03-07)

- Simplified the active digest path again so it now starts directly from the thread-aware `timeline.json` file instead of maintaining a stateful preselection layer.
- Reworked the package around one orchestrator plus five explicit step files:
  - `load_threads.py`
  - `categorize_threads.py`
  - `filter_threads.py`
  - `extract_signals.py`
  - `group_issues.py`
- Replaced the older per-step backend methods with one generic structured-output LLM wrapper in `src/xs2n/agents/digest/llm.py`.
- Kept deterministic code only for thread loading, virality scoring, artifact writing, and markdown rendering; the semantic steps now loop thread-by-thread and call the same LLM wrapper with different prompts.
- Simplified the CLI surface for `xs2n report digest` down to `--timeline-file`, `--output-dir`, `--taxonomy-file`, and `--model`.

## Digest Naming Cleanup (2026-03-07)

- Renamed the generic model wrapper from `OpenAIDigestAgent` to `DigestLLM`.
- Renamed the module from `src/xs2n/agents/digest/agents.py` to `src/xs2n/agents/digest/llm.py`.
- Renamed digest step parameters from `agent` to `llm` and removed the leftover `backend` vocabulary from `run_digest_report(...)`.
- Kept the “agentic” language for the step files conceptually, not for the thin model client.
