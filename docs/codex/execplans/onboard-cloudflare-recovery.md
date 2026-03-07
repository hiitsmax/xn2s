# Onboard Following Cloudflare Recovery

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document is maintained in accordance with `~/.agents/PLANS.md`.

## Purpose / Big Picture

When `xs2n onboard --from-following ...` hits an X/Cloudflare `403` block, users currently see a long traceback and do not know how to recover. After this change, the command will detect this specific failure, explain what happened in plain language, offer to open a real browser session to generate a cookies file, and retry automatically. Users will be able to recover inside the same command run.

## Progress

- [x] (2026-03-01 23:36Z) Read current onboarding/auth/following code paths and confirm where `Forbidden` bubbles up.
- [x] (2026-03-01 23:37Z) Gather fresh docs from Context7 for Typer confirmations and Playwright cookie/session capture.
- [x] (2026-03-01 23:40Z) Implemented Cloudflare-block detection and browser-cookie bootstrap utility.
- [x] (2026-03-01 23:42Z) Wired onboarding flow to catch 403, prompt user, run bootstrap, and retry.
- [x] (2026-03-01 23:44Z) Added tests covering Cloudflare detection and recovery path behavior.
- [x] (2026-03-01 23:45Z) Updated README/autolearning notes and ran full test suite (`13 passed`).

## Surprises & Discoveries

- Observation: The immediate user issue is not a stale library; `twikit` is already updated to `2.3.3`.
  Evidence: Local command `uv run python -c "import twikit; print(twikit.__version__)"` returned `2.3.3`.

- Observation: Existing onboarding notes had drifted and incorrectly claimed wizard-by-default behavior.
  Evidence: `docs/codex/autolearning.md` contained an outdated bullet; updated to match current explicit-mode design.

## Decision Log

- Decision: Implement recovery inside the existing `onboard` command instead of adding a separate command first.
  Rationale: The user asked for this to be part of onboarding when a `403` occurs; in-flow recovery minimizes friction.
  Date/Author: 2026-03-01 / Codex

- Decision: Use optional Playwright import with clear install guidance if missing.
  Rationale: Keeps default install lightweight while still supporting first-class recovery automation.
  Date/Author: 2026-03-01 / Codex

## Outcomes & Retrospective

Implemented the intended user-facing behavior end-to-end. Following-import onboarding now intercepts Cloudflare 403 blocks, explains the issue without traceback noise, offers an in-flow browser-cookie recovery step, and retries import automatically once cookies are refreshed. Tests were added for both detection and recovery logic, and all tests pass. Remaining gap: browser automation is only exercised in production flow (unit tests mock this path), which is acceptable for now but could be complemented later by an integration test with a fake cookie provider.

## Context and Orientation

The onboarding command is implemented in `src/xs2n/cli/onboard.py`. Following-import runtime is in `src/xs2n/profile/following.py`, and Twikit authentication bootstrap is in `src/xs2n/profile/auth.py`. Right now, Twikit exceptions propagate to CLI and print full tracebacks.

The term `Cloudflare block` here means an HTTP 403 response from X that contains Cloudflare block page content, usually with text like "Attention Required" or "Sorry, you have been blocked".

## Plan of Work

Add a small recovery utility in `src/xs2n/profile/auth.py`:

1. A detector function that identifies Cloudflare-block flavored Twikit `Forbidden` errors by inspecting exception text.
2. A browser-cookie bootstrap function using Playwright sync API that opens X login, waits for user confirmation, extracts cookies from browser context, and writes `cookies.json` in the same format consumed by `client.load_cookies`.

Then update `src/xs2n/cli/onboard.py` following-import branch to:

1. Catch Twikit `Forbidden`.
2. If it is Cloudflare-like, print a concise explanation and ask user confirmation with `typer.confirm`.
3. Attempt browser-cookie bootstrap, then retry import once.
4. Exit cleanly with actionable guidance if user declines or bootstrap fails.

Add tests under `tests/` for detection and command flow helpers without launching a real browser.

## Concrete Steps

Run from repository root:

    uv run pytest
    uv run xs2n onboard --from-following mx

Expected behavior after change:

1. On Cloudflare block, CLI prints short guidance instead of traceback.
2. CLI asks whether to open browser to bootstrap cookies.
3. On confirmation and successful cookie capture, command retries following import.

## Validation and Acceptance

Acceptance criteria:

1. `uv run pytest` passes including new tests.
2. A simulated Cloudflare `Forbidden` in tests triggers recovery messaging and optional retry logic.
3. Existing onboarding tests continue to pass, proving no regression for paste mode and baseline merging.

## Idempotence and Recovery

Running onboarding multiple times remains safe because profile merging already deduplicates handles. Browser-cookie bootstrap is idempotent: writing `cookies.json` again simply refreshes session cookies. If Playwright is missing, CLI returns explicit install commands and exits non-zero.

## Artifacts and Notes

Key validation transcript:

    uv run pytest
    ...
    collected 13 items
    tests/test_auth_recovery.py ..
    tests/test_cli_helpers.py ......
    tests/test_onboard_recovery.py ..
    tests/test_onboarding.py ...
    ...
    13 passed

## Interfaces and Dependencies

Use:

- `twikit.errors.Forbidden` for targeted handling.
- `typer.confirm` for interactive yes/no recovery prompt.
- `playwright.sync_api.sync_playwright` for headed browser login and cookie extraction.

New functions expected after implementation:

- `xs2n.profile.auth.is_cloudflare_block_error(error: Exception) -> bool`
- `xs2n.profile.auth.bootstrap_cookies_via_browser(cookies_file: Path) -> Path`

Revision note (2026-03-01 23:45Z): Updated progress and outcomes after implementation completed; added discovery about documentation drift and included test evidence transcript.
