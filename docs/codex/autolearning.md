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
  - processed threads,
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
  - `steps/load_threads.py`
  - `steps/categorize_threads.py`
  - `steps/filter_threads.py`
  - `steps/process_threads.py`
  - `steps/group_issues.py`
- Replaced the older per-step backend methods with one generic structured-output LLM wrapper in `src/xs2n/agents/digest/llm.py`.
- Kept deterministic code only for thread loading, virality scoring, artifact writing, and markdown rendering; the semantic steps now loop thread-by-thread and call the same LLM wrapper with different prompts.
- Simplified the CLI surface for `xs2n report digest` down to `--timeline-file`, `--output-dir`, `--taxonomy-file`, and `--model`.

## Thread Processing Naming Cleanup (2026-03-07)

- Renamed the thread-level raw-output step from `extract_signals.py` to `process_threads.py`.
- Moved the step files under `src/xs2n/agents/digest/steps/` so the package layout matches the conceptual pipeline shape.
- Renamed the core thread-processing schemas from `SignalResult`/`SignalThread` to `ThreadProcessResult`/`ProcessedThread`.
- Renamed the run artifact from `signals.json` to `processed_threads.json` so the artifact matches the thread-centric operation.

## Digest Naming Cleanup (2026-03-07)

- Renamed the generic model wrapper from `OpenAIDigestAgent` to `DigestLLM`.
- Renamed the module from `src/xs2n/agents/digest/agents.py` to `src/xs2n/agents/digest/llm.py`.
- Renamed digest step parameters from `agent` to `llm` and removed the leftover `backend` vocabulary from `run_digest_report(...)`.
- Kept the “agentic” language for the step files conceptually, not for the thin model client.

## Digest Schema Extraction (2026-03-07)

- Moved the digest Pydantic/data classes out of `src/xs2n/agents/digest/pipeline.py`.
- Added a root-level `src/xs2n/schemas/` package with `src/xs2n/schemas/digest.py` as the source of truth for digest schemas.
- Kept `pipeline.py` focused on orchestration, rendering, and deterministic helpers while the step files now import their schemas from `xs2n.schemas.digest`.

## Digest Parallel Worker Pool (2026-03-15)

- Added bounded per-stage parallelism for the three thread-local digest phases:
  - `categorize_threads`
  - `filter_threads`
  - `process_threads`
- Kept the orchestration shape the same: the stages still run in order, but each stage can fan out across multiple threads.
- Added `--parallel-workers` to both `xs2n report digest` and `xs2n report latest`.
- Recorded the configured worker count in each run's `run.json` so artifact review explains the execution mode.
- Locked the fake LLM trace writer in tests and added ordering assertions so concurrency changes preserve deterministic stage outputs.

## Desktop Artifact Browser (2026-03-15)

- Chose `pyfltk` for the optional desktop artifact browser because it matches the desired lightweight NeXT/OpenStep-style feel better than a heavier Qt stack.
- Kept the GUI as an optional extra instead of a core dependency so the CLI-first and cron-first workflows stay unaffected.
- Locked the UI data model to the existing run artifacts rather than inventing a new backend:
  - scan every `data/report_runs*` root,
  - treat the filesystem as the source of truth,
  - use `run.json` and `phases.json` when present,
  - tolerate old or interrupted runs that only contain a subset of files.
- Kept the viewer FLTK-native by switching the right-hand pane to `Fl_Help_View` and converting `.md` artifacts to HTML at load time instead of embedding a browser engine.
- Discovered a concrete macOS caveat during packaging research: `pyfltk` needs the native FLTK shared libraries from Homebrew, or imports fail with a missing `libfltk*.dylib` error.
- Split the macOS-specific native menu override into `src/xs2n/ui/macos/` so the main FLTK app stays readable and the Cocoa bridge stays isolated to the platform that needs it.
- Used FLTK's `Fl_Sys_Menu_Bar.window_menu_style(no_window_menu)` before first show, then a tiny Cocoa/AppKit bridge after show to rename the app to `xn2s` and replace the default macOS menu with only `About xn2s` and `Quit xn2s`.
- Updated the user-facing docs to make the install path explicit:
  - `uv sync --extra gui`
  - `brew install fltk` on macOS

## OpenStep Font Defaults (2026-03-16)

- Verified a concrete FLTK quirk on macOS: after `Fl.set_fonts()`, the default `FL_HELVETICA` slot still resolved to `Arial` in this environment.
- Added `src/xs2n/ui/openstep.py` so the UI can remap the four built-in Helvetica slots to the real system `Helvetica` family when those faces are available.
- Kept the HTML viewer on legacy `Fl_Help_View`-friendly markup by using explicit `<font face=\"Helvetica\">` tags instead of relying on modern CSS support.
- Added regression coverage for both the FLTK font-slot remapping logic and the viewer HTML output.

## UI Terminal Interrupt Shutdown (2026-03-16)

- Reproduced a concrete `pyfltk` quirk on macOS: pressing `Ctrl+C` while `Fl.run()` is active can surface `KeyboardInterrupt` from an idle callback without actually closing the native window.
- Added an explicit `SIGINT` handler around the UI event loop that defers the shutdown to the next FLTK idle tick, then closes the browser window cleanly.
- Added a deterministic unit test for the signal-handler lifecycle so the CLI-launched desktop UI exits cleanly from the terminal without relying on manual verification alone.

## Digest Helper And Render Split (2026-03-07)

- Moved shared digest utilities out of `src/xs2n/agents/digest/pipeline.py` into `src/xs2n/agents/digest/helpers.py`.
- Promoted markdown generation to a real step module at `src/xs2n/agents/digest/steps/render_digest.py`.
- Reduced `pipeline.py` down to run orchestration plus default path/model constants, which makes the digest flow easier to read and less deceptive about where logic actually lives.

## Digest Codex Auth Reuse (2026-03-07)

- Replaced the digest model transport with the OpenAI Python SDK Responses client.
- `xs2n report digest` now prefers `OPENAI_API_KEY` when present, otherwise reuses the Codex ChatGPT auth session from `CODEX_HOME/auth.json` or `~/.codex/auth.json`.
- Switched the default digest model to `gpt-5.4` so the Codex-auth path works without extra flags.
- Added deterministic tests for credential resolution, streamed structured-output parsing, and Codex-unsupported model errors.
- Removed the old LangChain dependency path from the digest flow because the new transport is smaller and matches the real supported auth surface better.

## Coding Preference Capture (2026-03-07)

- Added `docs/codex/coding-preferences.md` to preserve the coding-style lessons learned during the digest refactor in a reusable form.
- Kept the rules general and portable, while grounding each one with a concrete example taken from the same refactor session.
- Captured a few strong preferences explicitly: name modules by real responsibility, keep pipelines visually direct, avoid meaningless indirection, and prefer responsibility-based file boundaries over speculative abstraction.

## Digest Worker-Pool Parallelism (2026-03-15)

- Added bounded parallel execution for the three high-volume digest steps: `categorize_threads`, `filter_threads`, and `process_threads`.
- Exposed `--parallel-workers` on `xs2n report digest` and `xs2n report latest` so throughput can be tuned per run instead of being hard-coded.
- Hardened `DigestLLM` trace writing for concurrent requests and kept artifact ordering stable even when individual model calls finish out of order.
- Learned that concurrency in this pipeline is mostly an observability problem, not just a performance problem: trace IDs and artifact ordering must stay deterministic or the faster run becomes harder to debug.

## Report Latest End-To-End Command (2026-03-08)

- Added `xs2n report latest` to run a full report cycle with one CLI command: batch timeline ingestion from onboarded sources, then digest rendering.
- Added a small `--since` / `--lookback-hours` resolver so scheduled runs can be configured by fixed cutoff or rolling window.
- Kept orchestration explicit by reusing existing `timeline(...)` and `run_digest_report(...)` entrypoints in sequence instead of adding new hidden wrappers.
- Added deterministic tests for since-resolution behavior, timeline+digest orchestration wiring, and digest runtime error propagation.

## Home Latest Timeline Mode (2026-03-08)

- Added `xs2n timeline --home-latest` to ingest authenticated `Home -> Following` latest feed items, not just per-account timelines or onboarded source lists.
- Implemented Twikit `get_latest_timeline()` pagination with since-cutoff filtering, dedupe by tweet id, and normalization into the existing `TimelineEntry` schema.
- Added `xs2n report latest --home-latest` so one command can ingest platform feed data and render a digest run.
- Kept default `report latest` behavior unchanged (`--from-sources`) to avoid breaking existing cron flows.
- Added deterministic tests for home-latest importer behavior, timeline mode validation/routing, and report latest home-latest orchestration.

## Report Latest Reliability And Digest Run Tracing (2026-03-13)

- Fixed a real production bug in `xs2n report latest`: the command had been calling the Typer-decorated `timeline(...)` function directly, which leaked `typer.Option(...)` defaults into runtime code and crashed with `OptionInfo` type errors on live runs.
- Extracted a plain `run_timeline_ingestion(...)` helper in `src/xs2n/cli/timeline.py` so CLI parsing and reusable Python runtime logic are now separate and the end-to-end report flow can safely reuse ingestion.
- Added richer digest run observability without changing the existing semantic snapshot files:
  - `taxonomy.json` freezes the taxonomy used for the run,
  - `phases.json` records per-phase timing, counts, artifacts, and failures,
  - `llm_calls/*.json` records per-call prompt/payload/result plus response metadata,
  - `run.json` is now written incrementally with `running`, `completed`, or `failed` status.
- Added regression coverage for the new plain ingestion helper defaults and for partial-failure digest artifacts.
- Verified the repaired boundary with a real `xs2n report latest --home-latest --lookback-hours 24 --model gpt-5.4` run: it got past the old crash, ingested Home->Following items, and started writing trace artifacts immediately.
- Verified a completed real-model digest run on a trimmed timeline subset; the run folder now explains both execution flow and model decisions well enough to audit why threads were dropped.
- New fragility discovered during live verification: `xs2n report latest` still digests the whole accumulated `data/timeline.json` after ingesting new items, so long-lived timeline files can make a “latest” run much larger and slower than the lookback window suggests.
- New fragility discovered during manual interruption: externally terminated runs can leave `run.json` in `running` state because a process-level `SIGTERM` bypasses the normal Python exception cleanup path.
