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
- Updated onboarding UX: `xs2n onboard` without mode now returns explicit usage examples, and interactive mode is opt-in via `--wizard`.
