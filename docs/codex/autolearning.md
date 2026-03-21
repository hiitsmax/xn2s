# xs2n Autolearning Framework

## Goal

Continuously improve this codebase by capturing implementation choices, fragility points, and hardening opportunities after each milestone.

## Current Report Surface

The active report contract is `xs2n report issues`, `xs2n report html`, and `xs2n report latest`.

The notes below are chronological history. Older references to `report digest` or `report schedule` are intentionally preserved where they describe the pre-simplification surface or earlier milestones.

## Loop

1. Build a narrow milestone with observable output.
2. Record what worked and where it was brittle.
3. Add tests for deterministic parts.
4. Add one operational hardening step in the next milestone.
5. Repeat.

## UI Digest Issue List Table Sorting (2026-03-21)

- Simplified the digest viewer issue list to the literal data the user wanted in the middle column:
  - one `Title` column,
  - one `Threads` column,
  - no rank badge, no density token, no extra sort control.
- Kept the classic desktop interaction model instead of introducing dropdowns or mode toggles:
  - clicking `Title` sorts alphabetically and flips between ascending and descending,
  - clicking `Threads` sorts numerically and flips between descending and ascending,
  - the active header shows its current direction directly in the label.
- Decoupled display order from the existing issue density rank:
  - `DigestIssueRow.rank` still tracks the original density-based digest priority used by the right-side summary surface,
  - the visible row order is now controlled by explicit UI sort state in `DigestBrowserState`.
- Preserved selection stability while reordering:
  - changing sort order does not kick the user onto a different issue if the currently selected issue is still present.
- Verified with:
  - `uv run pytest tests/test_digest_browser.py tests/test_digest_browser_state.py -q`
  - `uv run pytest tests/test_digest_browser_probe.py tests/test_ui_app_rendering.py -q`
  - `uv run python -m xs2n.ui.digest_browser_probe --run-dir data/report_runs/20260318T225654Z --issue-limit 3`
- Current measured probe output on that saved run:
  - `load_run_ms: 30.44`
  - `issue_timings_ms: [1.03, 3.05, 0.73]`
  - `issue_count: 110`
- The reusable lesson here is straightforward:
  - when the user asks for a classic sortable table, the cleanest UI is usually the obvious one,
  - keep semantic ranking metadata for the reading surface, but do not force that ranking vocabulary into the navigation list.

## UI Digest Issue Reading Surface (2026-03-19)

- Reframed the native digest viewer around issue-level reading instead of thread-level drilling:
  - the issue navigator is now ranked by signal density using current saved data (`thread_count`, `tweet_count`),
  - selecting an issue immediately opens one issue canvas with all thread cards and posts already expanded,
  - the intermediate thread list inside the digest viewer is gone.
- Follow-up debugging showed that the remaining freeze did not come from loading data or building the issue text:
  - `load_saved_digest_preview(...)`, `DigestBrowserState(...)`, and issue rendering were all sub-5ms,
  - the stall was specifically `Fl_Help_View.value(...)` on the issue canvas, even with only about `20k` characters of HTML.
- Replaced the issue canvas transport from `Fl_Help_View` HTML to `Fl_Text_Display` + `Fl_Text_Buffer`, keeping the ranked issue navigator and summary header but moving the expanded issue body to native wrapped text.
- Added a real UI probe module at `src/xs2n/ui/digest_browser_probe.py` that:
  - opens the real native digest viewer,
  - measures `load_run` and per-issue selection timings,
  - captures a PNG screenshot using `fl_capture_window(...)` and `fl_write_png(...)`.
- Kept the visual language inside the existing classic desktop theme instead of introducing a new UI vocabulary:
  - compact ranked navigator on the left,
  - editorial issue summary header on the right,
  - one continuous native text canvas below for thread cards.
- Added coverage in `tests/test_digest_browser_state.py` for:
  - ranked issue ordering,
  - issue-level expanded preview defaults,
  - multi-thread issue rendering output.
- Added `tests/test_digest_browser_probe.py` to run the real probe module with a timeout and assert that it both stays responsive and writes a screenshot.
- Verified with:
  - `uv run pytest tests/test_digest_browser_state.py -q`
  - `uv run pytest tests/test_digest_browser_state.py tests/test_digest_browser_probe.py -q`
  - `uv run pytest tests/test_digest_browser_state.py tests/test_ui_app.py tests/test_ui_app_rendering.py -q`
  - a real-run probe against `data/report_runs/20260318T225654Z` that confirmed the top navigator rows reorder to `17/17`, `8/8`, `5/5` issue clusters and that rendering the top issue stays around `20k` HTML characters.
  - `uv run python -m xs2n.ui.digest_browser_probe --run-dir data/report_runs/20260318T225654Z --screenshot /tmp/xs2n-digest-browser-probe.png --issue-limit 3`
- Current measured probe output on that run:
  - `load_run_ms: 11.78`
  - `issue_timings_ms: [0.97, 1.01, 1.65]`
  - screenshot saved successfully to `/tmp/xs2n-digest-browser-probe.png`
- Follow-up visual refinement after human review:
  - the secondary summary column now carries only title, compact meta, and one blurb line instead of reprinting timestamps and verbose metadata,
  - the lower viewer drops repeated issue-level headers and heavy field labels such as `Summary:` and `Why this matters:`,
  - `Fl_Text_Display` now uses a cleaner proportional text face and slightly larger body size so the digest reads more like an editorial surface than a terminal dump.
- Follow-up typographic pass after another human review:
  - the issue summary area now renders as one inset surface with internal padding instead of stacking title/meta/blurb directly against the right-pane edge,
  - the lower issue canvas no longer repeats the issue blurb before the thread list, which reduces the feeling of duplicated copy at the top of the reading surface,
  - thread rendering now carries a dedicated FLTK style buffer so thread titles, thread summaries, editorial context, tweet metadata, and tweet text can read as different text roles rather than one flat block.
- Follow-up comprehension pass after another human review:
  - thread cards now present the source tweet before the editorial rationale, because users understand ambiguous summaries faster when they can see the underlying post immediately,
  - the rationale line is explicitly introduced as `Why here:` so the digest’s own interpretation no longer blends into the source material,
  - source metadata is explicitly introduced as `Source post NN.` so the lower canvas reads like a curated note with evidence, not a single undifferentiated text block.
- Follow-up native-card pass after another human review:
  - when a human asks for actual per-thread borders and padding, treat that as a surface-change request, not as a spacing tweak inside one long text widget,
  - `Fl_Text_Display` is still useful for quick readable text, but the moment the UI needs local visual containers, switch to a scrollable stack of native thread cards,
  - the card pattern that worked here was: bold title, regular summary, compact source label + source text, then a muted italic `Why here` label with the editorial rationale beneath it.
- Follow-up responsive pass after another human review:
  - once the lower pane becomes a real card stack, the left issue navigator width can no longer stay hard-coded if the overall viewer is expected to resize gracefully,
  - a proportional width with clamp bounds worked better than a fixed `320px`: it keeps the navigator usable on narrow windows without starving the reader surface, and it does not let the navigator become comically wide on large windows,
  - geometry regressions here are worth locking with widget-level tests, not just screenshots, because the bug showed up as an unhealthy ratio between navigator and reader rather than as a logic failure.
- The reusable lesson here is twofold:
  - this UI does not need more stored ranking metadata to feel prioritized,
  - once `Fl_Help_View` starts parsing richer, repeated structures, the correct fix is often to stop feeding it HTML and move that surface to native FLTK widgets.

## UI Native Digest Viewer (2026-03-19)

- Split the digest presentation contract in two:
  - `src/xs2n/agents/digest/steps/render_digest_html.py` is again just a simple Windows-classic export HTML renderer,
  - `xs2n ui` now treats `digest.html` as a semantic digest artifact and shows a native right-pane viewer instead of piping rebuilt digest HTML into `Fl_Help_View`.
- Added `src/xs2n/ui/digest_browser_state.py` for the small overview/thread navigation state and `src/xs2n/ui/digest_browser.py` for the native FLTK widget container.
- After user review, reshaped the native viewer into a mail-client-style layout:
  - issue list on the left inside the right pane,
  - thread list on the upper right,
  - thread preview below.
- Kept the outer three-column shell and focus mode intact, but added a new preference-backed rule: when digest viewer is active, the middle navigation column is hidden by default and its space is given to the right pane; Preferences can turn that column back on.
- Removed the digest-specific HTML preview path from `src/xs2n/ui/viewer.py`, and deleted the now-dead `src/xs2n/ui/digest_preview.py` and `src/xs2n/ui/source_preview.py` modules.
- Verified the milestone with:
  - `uv run pytest tests/test_render_digest_html.py tests/test_ui_app_rendering.py tests/test_ui_viewer.py tests/test_digest_browser_state.py -q`
  - `uv run pytest tests/test_render_digest_html.py tests/test_ui_app.py tests/test_ui_app_rendering.py tests/test_ui_viewer.py tests/test_ui_artifacts.py tests/test_digest_browser_state.py -q`
  - `uv run pytest tests/test_render_digest_html.py tests/test_ui_app.py tests/test_ui_app_rendering.py tests/test_ui_viewer.py tests/test_ui_artifacts.py tests/test_ui_run_preferences.py tests/test_ui_state_storage.py tests/test_digest_browser_state.py -q`
  - a live callback timing probe against `ArtifactBrowserWindow._apply_selected_artifact_name('digest.html')`
  - a live widget-introspection probe that opened the real `ArtifactBrowserWindow`, selected run `20260318T225654Z`, selected `digest.html`, and read back the FLTK widget state (`header`, issue rows, thread rows, preview length)
- Current repository status after the change:
  - focused verification reached `14 passed`
  - broader regression verification reached `56 passed`
  - the live selection probe on run `20260318T225654Z` measured `digest.html` callback time at about `5.67 ms`
  - the most robust anti-freeze lesson here is architectural: when the desktop UI needs interaction, stop encoding that interaction as HTML for `Fl_Help_View` and give the right pane a native widget path instead
  - the most useful “self-test the UI” lesson here is pragmatic: for FLTK, widget introspection from a real `ArtifactBrowserWindow` instance is more reliable and scriptable than trying to infer behavior from HTML output alone

## UI Digest Auto-Selection Hardening (2026-03-19)

- Root-caused the “middle navigation still visible” regression to sticky fallback artifact selection, not to preference persistence or FLTK visibility state.
- The concrete failure mode was: the UI booted into a newer run without `digest.html`, auto-selected `run.json`, and then carried that fallback into an older run that did have `digest.html`, which prevented the digest viewer from activating and therefore kept the middle pane open.
- Added a small distinction in `src/xs2n/ui/app.py` between automatic artifact selection and explicit user-pinned selection:
  - automatic selection now re-prefers `digest.html` and `digest.md` whenever a run provides them,
  - explicit clicks in the middle pane still stay sticky across runs when the artifact exists.
- Added focused coverage in `tests/test_ui_app_rendering.py` for the new selection-resolution rule.
- Verified with:
  - `uv run pytest tests/test_ui_app.py tests/test_ui_app_rendering.py tests/test_ui_run_preferences.py tests/test_ui_state_storage.py -q`
  - a live widget probe that opened `ArtifactBrowserWindow`, switched to run `20260318T225654Z`, and confirmed `selected_artifact_name == 'digest.html'` plus `navigation_visible == False`

## UI Digest Source Snapshot (2026-03-19)

- Extended the saved-digest desktop preview so `source` now opens an internal snapshot page instead of leaving the UI immediately.
- Split the old single-file preview logic into two honest responsibilities:
  - `src/xs2n/ui/saved_digest.py` loads and validates saved digest artifacts,
  - `src/xs2n/ui/source_preview.py` renders the compact thread/source page.
- Refreshed `src/xs2n/ui/digest_preview.py` into a more structured Windows-classic layout with issue panels, clearer thread summaries, and internal `xs2n://thread/...` links.
- Wired `fltk.Fl_Help_View.link(...)` inside `src/xs2n/ui/app.py` so internal links render new HTML in place while external `https://x.com/...` links open through the system browser.
- Verified the milestone with:
  - `uv run pytest tests/test_ui_viewer.py tests/test_ui_app_rendering.py -q`
  - `uv run pytest tests/test_render_digest_html.py tests/test_ui_viewer.py tests/test_ui_app_rendering.py tests/test_ui_app.py -q`
- Current repository status after the change:
  - focused verification reached `14 passed`
  - broader regression verification reached `35 passed`
  - one runtime hardening detail was captured: `pyFLTK` passes extra callback args to `Fl_Help_View.link(...)`, so the handler now resolves the clicked URI from `*args` instead of assuming a rigid callback signature

## CLI UI JSONL Job Events (2026-03-19)

- Added a neutral run-event contract in `src/xs2n/schemas/run_events.py` so CLI adapters and UI adapters now share one honest machine-readable progress schema.
- Taught `src/xs2n/report_runtime.py` and `src/xs2n/agents/digest/pipeline.py` to emit structured run, phase, and artifact events instead of leaving the UI to infer all state from shell transcripts and post-run disk scans.
- Added `--jsonl-events` to `xs2n report issues` and `xs2n report latest`, with one deliberate contract: JSONL events go to stdout, human-oriented logs go to stderr.
- Replaced the FLTK runner in `src/xs2n/ui/app.py` with a `subprocess.Popen(...)` reader so the desktop app can consume events live, update status text during the run, and refresh artifact lists as files appear.
- Kept the final `refresh_runs()` path as reconciliation rather than the primary state mechanism, which means the UI now has live process state and still converges on on-disk truth at completion.
- Verified the milestone with:
  - `uv run pytest tests/test_report_runtime.py tests/test_report_digest.py tests/test_report_cli.py tests/test_ui_app.py tests/test_ui_run_arguments.py tests/test_ui_run_preferences.py -q`
  - `uv run pytest -q`
  - `uv run xs2n report latest --help`
- Current repository status after the change:
  - focused verification reached `64 passed`
  - full regression verification reached `222 passed`
  - one adapter hardening detail was captured: direct Python calls into Typer command functions can receive `OptionInfo` defaults instead of plain booleans, so CLI code that supports both Typer invocation and direct unit calls now normalizes those values explicitly before branching

## UI Digest Help View Simplification (2026-03-19)

- Root-caused the digest freeze to `Fl_Help_View.value(...)` parsing the saved browser-oriented `digest.html`, not to worker-thread preview generation or JSON preview loading.
- Re-checked fresh FLTK guidance through Context7 and aligned the UI with the documented reality that `Fl_Help_View` understands a subset of HTML, so the desktop app now avoids handing it the full browser digest markup.
- Kept the saved `digest.html` file untouched for browser use, but taught the desktop viewer to rebuild that artifact from `run.json`, `issues.json`, and `issue_assignments.json` into a simpler FLTK-friendly document with only basic headings, paragraphs, and links.
- Left generic HTML artifacts on the previous path so non-digest HTML still renders verbatim in light mode and with the existing dark-theme override in dark mode.
- Verified the milestone with:
  - `uv run pytest tests/test_ui_app_rendering.py tests/test_ui_viewer.py -q`
  - a live timing probe against `data/report_runs/20260318T225654Z/digest.html`
- Current repository status after the change:
  - focused verification reached `12 passed`
  - measured `digest.html` apply time dropped from about `13.8s` to about `9.7ms`
  - measured end-to-end digest selection-to-render time dropped to about `122ms`

## UI Latest Primary And Saved-Run HTML Alias (2026-03-19)

- Promoted `xs2n report latest` to the primary run action in the desktop UI by removing the peer `Issues` launcher from the main menu/toolbar instead of keeping two equally prominent run buttons.
- Kept the issue-building CLI path intact for offline and scripted use, but made saved-run HTML rendering easier to discover with a new `xs2n report html --run-dir ...` command while preserving `xs2n report render` as a compatibility alias.
- Updated `xs2n report issues` output so a completed issue run now tells the operator exactly how to render HTML later from the saved run directory.
- Verified the milestone with:
  - `uv run pytest tests/test_report_cli.py tests/test_ui_app.py -q`
- Current repository status after the change:
  - focused verification reached `39 passed`

## Report Schedule And Shared Latest Runtime (2026-03-18)

- Added `xs2n report schedule` with portable v1 commands: `create`, `list`, `show`, `run`, `export`, and `delete`.
- Kept the operating system as the real scheduler. The new CLI stores named definitions in `data/report_schedules.json`, acquires overlap locks in `data/report_schedule_locks/`, records `last_run`, and only prints install-ready `cron` / `launchd` / `systemd` output instead of mutating the OS directly.
- Added a reusable `report_runtime.py` helper for the current issue-based `report latest` flow, so the schedule runner reuses the same timeline-ingestion, windowing, issue-build, and HTML-render path as the CLI.
- Mid-implementation, the active branch reality turned out to be `report issues` / `report html` / `report latest`, not the older digest-only report surface. The schedule work was deliberately integrated with that newer truth instead of trying to keep both report contracts alive.
- Verified the milestone with:
  - `uv run pytest tests/test_report_digest.py tests/test_report_runtime.py tests/test_report_schedule.py tests/test_report_schedule_storage.py tests/test_report_cli.py tests/test_ui_run_arguments.py tests/test_ui_run_preferences.py`
  - `uv run xs2n report schedule --help`
  - `uv run xs2n report schedule create demo --every-hours 6 --lookback-hours 24 --schedules-file /tmp/...`
  - `uv run xs2n report schedule export demo --target cron --schedules-file /tmp/...`
  - `uv run pytest`
- Current repository status after the change: `208 passed`.

## Following Source Refresh (2026-03-18)

- Added `xs2n onboard --refresh-following` as a CLI-first shortcut for replacing `data/sources.json` with the authenticated account's current following list.
- Kept the existing `xs2n onboard --from-following <handle>` path merge-oriented so explicit-handle onboarding still behaves as a non-destructive import.
- Added a dedicated replace helper in `src/xs2n/storage/sources.py` so replacement semantics stay separate from merge semantics and remain easy to test.
- Wired the desktop UI to launch the same CLI shortcut from the `Run` menu instead of duplicating onboarding logic inside the FLTK layer.
- Locked the empty-following edge case with tests so refresh can intentionally clear stale source rows instead of failing when the authenticated account follows nobody.
- Verified the feature with focused tests only; the full `uv run pytest` is currently blocked by unrelated missing modules already present in this workspace (`xs2n.cli.auth`, `xs2n.schemas.auth`, `xs2n.report_runtime`, and related auth/schedule UI paths).

## UI Auth Center And Login Guard (2026-03-18)

- Added an explicit CLI auth surface for the desktop app:
  - `xs2n auth doctor --json`
  - `xs2n auth x login`
  - `xs2n auth x reset`
- Kept Codex login on the existing `xs2n report auth` path instead of adding a wrapper command with duplicated semantics.
- Added a dedicated desktop auth window with separate `Codex` and `X / Twitter` sections, plus a direct `File -> Authentication` menu entry.
- The UI now refreshes auth state on explicit demand from `File -> Authentication` and as a preflight before the active report runs, using the CLI as the source of truth instead of inferring state from viewer transcripts.
- The auth window does not duplicate the cookies-path setting: it displays the currently applied `Latest` cookies path from Preferences and passes that exact path into doctor/login/reset commands.
- Updated Playwright X bootstrap so browser login can wait for `auth_token` and `ct0` automatically instead of depending on a terminal `Press Enter` checkpoint.
- Verified the feature with:
  - `uv run pytest tests/test_auth.py tests/test_auth_cli.py tests/test_auth_recovery.py tests/test_browser_cookies.py tests/test_onboard_recovery.py tests/test_ui_app.py tests/test_ui_auth_commands.py tests/test_ui_auth_window.py tests/test_ui_cli.py tests/test_ui_following_refresh.py tests/test_ui_run_arguments.py tests/test_ui_run_preferences.py -q`
  - `uv run xs2n auth doctor --json --cookies-file cookies.json`
- Repository status after full-suite verification:
  - `uv run pytest` reaches `189 passed`
  - 6 failures remain outside this feature in report/digest/schedule flows (`tests/test_report_digest.py`, `tests/test_report_runtime.py`, `tests/test_report_schedule.py`)

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

## UI Run Arguments Panel (2026-03-15)

- Moved digest/latest argument editing out of the main browser pane and into a dedicated `Preferences` window opened from `File -> Preferences`.
- Extracted deterministic argument defaults, normalization, and validation into `src/xs2n/ui/run_arguments.py`, then isolated the window-specific FLTK form code in `src/xs2n/ui/run_preferences.py` so the main browser stays readable.
- Added explicit `Apply` and `Cancel` controls so preferences no longer affect launches while the user is typing. The active commands now read from stored applied state, not directly from the live widgets.
- Added focused tests for digest/latest CLI argument rendering plus lightweight callback wiring tests in `tests/test_ui_run_arguments.py`, `tests/test_ui_run_preferences.py`, and `tests/test_ui_app.py`.
- Verified the feature with:
  - `uv run pytest tests/test_ui_run_arguments.py tests/test_ui_run_preferences.py tests/test_ui_app.py tests/test_ui_cli.py`
  - `uv run pytest`
  - a bootstrap smoke that instantiated `ArtifactBrowserWindow`, opened the Preferences window, and confirmed the `Latest` tab could be selected without crashing.

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
- Split the macOS-specific native menu override into `src/xs2n/ui/macos/` so the main FLTK app stays readable and the Cocoa bridge stays isolated to the platform that needs it.
- Used FLTK's `Fl_Sys_Menu_Bar.window_menu_style(no_window_menu)` before first show, then a tiny Cocoa/AppKit bridge after show to rename the app to `xn2s` and replace the default macOS menu with only `About xn2s` and `Quit xn2s`.
- Discovered a concrete macOS caveat during packaging research: `pyfltk` needs the native FLTK shared libraries from Homebrew, or imports fail with a missing `libfltk*.dylib` error.
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

## Artifact Browser Command Strip Refresh (2026-03-16)

- Restyled the artifact-browser command strip into a retro control bar with larger icon-first buttons, small engraved captions, and beige hover tooltips.
- Kept the command wiring unchanged so the UI polish stayed isolated to layout and widget styling instead of touching the digest/runtime code paths.
- Verified the FLTK bindings directly with `uv run --extra gui python` before changing widget APIs, which caught the real available methods/constants and reduced guesswork for the optional GUI dependency.
- User feedback pushed the design one step further toward a true Windows toolbar: the better fit was smaller monochrome icon buttons with tooltip-only labels, not “hero” buttons with extra emphasis.
- For FLTK menus, “padding” is effectively controlled through menu text metrics and bar height; a small bump to `textsize`/`MENU_HEIGHT` gives dropdown items more breathing room without custom drawing.

## UI Terminal Launch Fallback (2026-03-16)

- Reproduced a real macOS regression where `uv run xs2n ui` returned immediately with no visible feedback after the new app-bundle relaunch path was added.
- The underlying FLTK browser still worked when launched directly, so the safer contract for terminal users is to keep interactive launches in-process and reserve the detached app-bundle handoff for non-interactive contexts.
- Moved the optional-GUI import check ahead of the relaunch attempt so missing `pyfltk` or missing native FLTK runtime errors stay visible in the terminal instead of disappearing into a detached macOS `open` call.

## UI Markdown Font Fallback (2026-03-16)

- Reproduced a typography bug where rendered Markdown in `Fl_Help_View` showed up in a monospace-looking fallback font on macOS even though the rest of the window styling was intentional.
- The root cause was not Python-Markdown: it only emits HTML tags. The real issue was our wrapper forcing `<font face="Microsoft Sans Serif">`, which is a Windows face and not a safe HTML font choice for the FLTK help viewer on macOS.
- Kept the Windows-classic widget styling for FLTK controls, but split the HTML viewer font to a platform-appropriate face so macOS Markdown content now renders with `Helvetica` instead of falling back awkwardly.

## UI Run List Column Cleanup (2026-03-16)

- Tightened the left-hand run browser by switching from one verbose summary string to four explicit FLTK browser columns: source, started, status, and thread/kept/issue counts.
- Kept the retro desktop feel by using FLTK's native column support instead of custom drawing or a modern table widget.
- Verified the live widget API through Context7 plus `uv run python` introspection before changing the browser setup, which confirmed `column_char()`, `column_widths()`, and `linespacing()` were all available in the actual pyFLTK binding.
- A compact source label such as `[24H/100]` works better in the scan list than repeating the full `report_runs_*` directory name, while the full root still stays available in `run.json`.

## UI Artifact Browser Navigation Cleanup (2026-03-16)

- Removed the dedicated right-side run-details pane because it duplicated information already available in `run.json`.
- Split the middle artifact column into two stacked browsers:
  - curated sections at the top for the important artifacts,
  - raw files below for the full run folder listing.
- Kept both navigation surfaces on one artifact-selection path, so clicking `Run metadata` in the top pane and `run.json` in the bottom pane opens the same viewer content.
- Added focused regression coverage for section derivation and synchronized section/raw-file selection behavior, then verified the real FLTK bootstrap with `ArtifactBrowserWindow(data_dir=Path("data"))`.

## UI Run List Preferences (2026-03-16)

- Changed the left run pane default from metadata-heavy columns to a simpler `Date` + `Digest` view, which reads more like a digest inbox and less like a trace console.
- Added digest-title extraction during run scan by reading `digest.md` and preferring the first meaningful issue heading (`### ...`) over the generic top-level file title.
- Split the run-list rendering logic into `src/xs2n/ui/run_list.py`, which now owns visible-column normalization, row formatting, and responsive width math for the FLTK browser.
- Added a dedicated `Run List` tab to the existing Preferences window instead of inventing a second settings surface inside the browser window.
- Verified the feature with focused tests for digest-title extraction, run-list formatting, preferences wiring, and app-level live updates, plus a live widget smoke that confirmed the header strip and toggle behavior on a real `ArtifactBrowserWindow`.

## UI Viewer Focus Mode (2026-03-16)

- Added a right-aligned icon toggle to the desktop artifact browser command strip so the left run list and middle navigation pane can be hidden temporarily while reading in the viewer.
- Restored the previous run-list and navigation widths when focus mode is turned off, so the viewer-only pass does not discard the browsing layout the user already set up.
- Kept the change local to `src/xs2n/ui/app.py` instead of moving focus state into the preferences window, because this is an immediate reading-mode action rather than a persistent configuration choice.
- Added focused app-level regression tests for the toggle callback plus pane hide/show geometry restoration before running the live FLTK smoke.

## UI Running-Command Exit Warning (2026-03-16)

- Added a close-path confirmation in the desktop artifact browser so quitting while a digest or latest run is still active no longer closes the app silently.
- Reused FLTK's native `fl_choice(...)` dialog instead of inventing a custom modal, which keeps the warning consistent with the rest of the retro desktop style and covers menu quit, window-close, and terminal interrupt paths through the same `close_browser()` guard.
- Kept the warning text honest: it names the active command label and warns that the run may be interrupted, without promising exactly what the child process will do after the UI exits.
- Added focused regression coverage for both outcomes: cancel keeps the window open, confirm proceeds with shutdown.

## UI Deferred Artifact Rendering (2026-03-16)

- Measured a real responsiveness bug in the artifact browser and confirmed the slow part was `Fl_Help_View.value(...)`, not the section-to-raw-file selection sync.
- Moved heavy artifact rendering onto the browser's existing FLTK idle loop so list selection can repaint before large JSON artifacts are parsed into the viewer.
- Added a lightweight loading view plus focused tests for deferred rendering and last-selection-wins behavior, which gives the user immediate feedback without lying about when the expensive viewer work actually finishes.

## UI Run List Multi-Select Delete (2026-03-16)

- Split the left-pane interaction logic into `src/xs2n/ui/run_list_browser.py` so `src/xs2n/ui/app.py` does not have to own raw FLTK modifier-key handling and popup-menu plumbing.
- Switched the run list from `Fl_Hold_Browser` to a `RunListBrowser` built on `Fl_Multi_Browser`, then normalized the selection semantics after the base widget processes the click so Shift-range and Ctrl-add/remove behave the way the user expects.
- Added a destructive-action safety rule for this UI: delete selected run folders only after a native `fl_choice(...)` confirmation, and keep the center/right panes bound to one fallback run after deletion rather than trying to make the artifact viewer multi-run aware.
- Locked the feature with focused tests for the filesystem delete helper, the pure run-list browser helpers, and the app-level delete flow, then verified the real FLTK bootstrap still instantiates `ArtifactBrowserWindow` with `RunListBrowser` successfully.

## UI Main-Thread Hardening (2026-03-18)

- Re-audited the artifact browser after the earlier idle-deferred fix and confirmed the deeper problem was still main-thread viewer work, not just delayed selection repaint.
- The worst measured freezes on local data were severe: about `21.85 s` for `filtered_threads.json`, `19.54 s` for `categorized_threads.json`, `14.43 s` for `threads.json`, `8.95 s` for `issue_assignments.json`, and `7.16 s` for `processed_threads.json`.
- The run-selection path also showed avoidable work: the newest local run expanded to `1211` visible artifacts because `llm_calls/` contributed `1200` nested child rows, and `list_run_artifacts(...)` took about `510.45 ms`.
- Hardened `src/xs2n/ui/artifacts.py` by collapsing nested directories in the raw-files browser and adding bounded preview loading for large files and large directories.
- Hardened `src/xs2n/ui/viewer.py` so previews can report truncation explicitly and avoid extra repeated regex compilation on every Markdown render.
- Hardened `src/xs2n/ui/app.py` by moving preview generation onto a worker thread and waking the FLTK loop with `fltk.Fl.awake()` only to apply ready results on the main thread.
- Tightened `src/xs2n/ui/run_list_browser.py` so plain left-click release no longer snapshots the full previous selection when Shift/Ctrl logic is not needed.
- The same local timing probe dropped to about `157.85 ms` for `filtered_threads.json`, `130.44 ms` for `categorized_threads.json`, `146.11 ms` for `threads.json`, `507.62 ms` for `issue_assignments.json`, and `484.41 ms` for `processed_threads.json`.
- `list_run_artifacts(...)` on the same run dropped from `1211` artifacts / `510.45 ms` to `11` artifacts / `1.2 ms` once `llm_calls/` stopped expanding into individual child rows.
- Focused verification passed for the touched modules:
  - `uv run pytest tests/test_ui_artifacts.py tests/test_ui_viewer.py -q` -> `12 passed`
  - `uv run pytest tests/test_ui_run_list_browser.py -q` -> `6 passed`
- New fragility discovered during verification: the broader UI test surface currently has unrelated concurrent blockers in the workspace, including a missing `xs2n.schemas.auth` module referenced by older tests and a separate `SyntaxError` in `src/xs2n/cli/report.py`, so the isolated rendering-path checks are the trustworthy signal for this milestone.

## CLI-First Issue Digest Simplification (2026-03-18)

- Replaced the old taxonomy-heavy `report digest` pipeline with a smaller CLI-first split:
  - `xs2n report issues` for loose filtering plus sequential issue building,
  - `xs2n report html` for deterministic HTML rendering from saved artifacts,
  - `xs2n report latest` for ingestion + latest-only snapshot + issue build + HTML render.
- Removed taxonomy and parallel-worker knobs from the primary report surface so the active product flow matches the simpler design instead of keeping legacy scaffolding visible.
- Extended timeline ingestion/storage with lightweight remote media metadata, which is now captured per tweet and reused only from the primary source-authored post when the issue-builder makes multimodal model calls.
- Updated the OpenAI wrapper to support Responses image inputs alongside structured JSON text payloads, while keeping the same trace-per-call artifact pattern in `llm_calls/`.
- Changed the desktop artifact browser to treat `digest.html` as the primary digest artifact and rely on `run.json.digest_title` / `primary_artifact_path` instead of scraping titles from markdown-only output.
- Verified the refactor with the full suite:
  - `uv run pytest -q` -> `207 passed`

## UI System Appearance Theme (2026-03-18)

- Added a small shared theme layer in `src/xs2n/ui/theme.py` with three appearance modes:
  - `system`
  - `classic_light`
  - `classic_dark`
- Kept the implementation honest by splitting persistence into `src/xs2n/storage/ui_state.py` instead of hiding app-wide appearance state inside `RunPreferencesWindow`.
- Hardened `save_ui_state(...)` to write through a temporary file and replace atomically, so a shared or concurrently running UI process is less likely to leave `data/ui_state.json` half-written.
- Updated the desktop browser, Preferences window, HTML viewer, and authentication window to consume the same theme tokens so dark mode no longer stops at the FLTK chrome.
- Taught the viewer to inject a dark-theme CSS override into HTML artifacts such as `digest.html`, and updated the digest HTML renderer itself to publish light/dark CSS variables for standalone viewing outside the app.
- Preserved the retro utility feel in dark mode by using warm charcoal and brown-gray surfaces, restrained blue selection, and slightly roomier row/header spacing rather than a flat modern dark palette.
- Tightened the async preview error path so a failed older render future no longer fabricates the current request id and overwrites the selected artifact with the wrong failure view.
- Added focused regression coverage for:
  - theme normalization and system resolution,
  - persisted appearance state,
  - dark viewer HTML rendering,
  - Preferences apply/cancel behavior for appearance,
  - app-level theme switching,
  - authentication-window theming.
- A concurrent-worktree verification blocker surfaced during the feature:
  - `xs2n.schemas.__init__` eagerly imported missing digest models,
  - `src/xs2n/report_runtime.py` eagerly imported digest execution when the UI only needed run-argument dataclasses.
  Both were narrowed just enough to unblock UI verification without dragging the theme work into the digest refactor.
- A late UX bug also surfaced in smoke testing: opening the UI immediately kicked off `auth doctor`, which made quit show a scary interruption dialog even when the user had not started any run. The root cause was the eager `_refresh_auth_state()` call in `ArtifactBrowserWindow.__init__`; removing that startup refresh fixed the prompt while keeping explicit auth refresh and command preflight behavior intact.
- Verified the final UI surface with:
  - `uv run pytest tests/test_ui_*.py -q` -> `90 passed`
  - `uv run python -m py_compile src/xs2n/ui/theme.py src/xs2n/storage/ui_state.py src/xs2n/ui/viewer.py src/xs2n/ui/run_preferences.py src/xs2n/ui/auth_window.py src/xs2n/ui/app.py src/xs2n/ui/run_arguments.py src/xs2n/report_runtime.py src/xs2n/schemas/__init__.py`
  - runtime smoke: `ArtifactBrowserWindow(data_dir=Path("data"))` printed `{'appearance_mode': 'system', 'theme': 'classic_dark', 'runs': 2}` and closed cleanly.
