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
- Stored source profiles in `data/sources.yaml` to keep downstream pipeline simple.

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

- Added persistent onboarding state in `data/onboard_state.yaml`.
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
