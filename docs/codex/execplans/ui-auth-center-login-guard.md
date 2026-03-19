# UI Auth Center And Login Guard

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the desktop UI can show two separate authentication sections, one for `Codex` model access and one for the `X / Twitter` session used by timeline ingestion. The UI refreshes auth status when it starts, offers explicit login/reset actions, and blocks `report digest` or `report latest` before they start if the required sessions are not ready. A user can see this working by opening `xs2n ui`, opening the new auth surface, and observing that `report latest` refuses to launch until both providers are ready.

## Progress

- [x] (2026-03-18 10:36Z) Audited current UI, CLI, auth, and recovery surfaces plus existing UI/auth tests.
- [x] (2026-03-18 10:40Z) Pulled fresh docs from Context7 for Typer and Codex auth command behavior, then verified local `codex` CLI help/output.
- [x] (2026-03-18 10:47Z) Captured the approved design: two separate auth sections, startup health check, and pre-run guard.
- [x] (2026-03-18 11:18Z) Wrote failing tests for the new CLI auth surface (`auth doctor`, `auth x login`, `auth x reset`) and UI auth/preflight behavior.
- [x] (2026-03-18 11:31Z) Implemented CLI auth status and X session bootstrap helpers with UI-safe, non-terminal browser login waiting.
- [x] (2026-03-18 11:45Z) Implemented the dedicated UI auth surface plus startup and pre-run health checks.
- [x] (2026-03-18 11:58Z) Updated README/autolearning and ran focused plus full verification, recording remaining unrelated failures.

## Surprises & Discoveries

- Observation: the shared worktree is already dirty in multiple UI files, so new edits must be additive and conflict-aware instead of assuming a clean base.
  Evidence: `git status --short --branch` shows existing modifications and untracked UI files on `main`.

- Observation: `codex login status` is available locally and currently exits successfully with the text `Logged in using ChatGPT`.
  Evidence: local command execution on 2026-03-18 in this workspace.

- Observation: the default `cookies.json` in this workspace exists but does not currently contain the required X session cookies.
  Evidence: local inspection found no `auth_token` or `ct0`, and `resolve_screen_name_from_cookies(...)` returned `None`.

- Observation: the new auth/UI slice verifies cleanly, but the repository still has unrelated failures in report/digest/schedule flows.
  Evidence: `uv run pytest` ended at `189 passed, 6 failed`; the remaining failures are in `tests/test_report_digest.py`, `tests/test_report_runtime.py`, and `tests/test_report_schedule.py`.

## Decision Log

- Decision: keep `xs2n report auth` as the only explicit Codex login command and add a new `xs2n auth` group only for X-session login/reset plus combined health checks.
  Rationale: `report auth` is already the real Codex contract used by digest execution, so a second wrapper command would add indirection without value.
  Date/Author: 2026-03-18 / Codex

- Decision: create a dedicated auth window instead of adding immediate auth actions to the draft/apply `Preferences` window.
  Rationale: login actions are operational and immediate, while the existing preferences model is intentionally draft-based.
  Date/Author: 2026-03-18 / Codex

- Decision: make the UI auth guard depend on a machine-readable CLI command (`xs2n auth doctor --json`) rather than parsing human text output.
  Rationale: the UI needs stable startup and pre-run gating, and transcript parsing would be brittle.
  Date/Author: 2026-03-18 / Codex

## Outcomes & Retrospective

The intended outcome was achieved for this feature: the desktop UI now has a dedicated auth surface, startup/pre-run health checks, and explicit CLI-driven actions for Codex and X/Twitter session management. Remaining repository work is outside this feature: unrelated report/digest/schedule tests are still failing in the shared workspace.

## Context and Orientation

The desktop UI lives in `src/xs2n/ui/`. The main orchestration file is `src/xs2n/ui/app.py`, which currently knows how to launch `report digest` and `report latest` commands in the background and then render a transcript when the subprocess exits. The run-argument forms live in `src/xs2n/ui/run_preferences.py` and `src/xs2n/ui/run_arguments.py`.

Codex authentication already exists as `xs2n report auth` in `src/xs2n/cli/report.py`. Digest model access can also come from `OPENAI_API_KEY`, but the current user intent is to expose the Codex login flow explicitly in the UI.

X authentication does not have a dedicated CLI entrypoint today. It is embedded inside `xs2n onboard`, `xs2n timeline`, and `xs2n report latest`. Those commands call prompt-driven recovery helpers that are not suitable for the desktop UI because they expect terminal interaction (`typer.prompt`, `typer.confirm`, and a Playwright `Press Enter after login` checkpoint).

In this plan, “doctor” means a CLI command that checks auth state and returns a stable JSON payload that the UI can trust for decisions. “Pre-run guard” means a UI check that runs just before `report digest` or `report latest`; if the required auth state is not ready, the run is blocked and the auth window is shown.

## Plan of Work

First, add focused tests that describe the missing behavior. The CLI tests should prove that `xs2n auth doctor --json` reports Codex and X readiness, that `xs2n auth x login` can finish without terminal prompts, and that `xs2n auth x reset` removes a cookies file cleanly. The UI tests should prove that startup health checks update an auth snapshot, that the auth window launches the expected CLI commands, and that `report digest` or `report latest` are blocked when their required auth state is not ready.

Next, add the new CLI auth surface under `src/xs2n/cli/auth.py` and register it in `src/xs2n/cli/cli.py`. Keep the flow obvious: one function to compute the structured doctor result, one function to run the UI-safe X login, and one function to reset the X cookies file. Put the shared JSON contract in `src/xs2n/schemas/auth.py` so the data shape is not buried in a CLI module.

Then make the X browser bootstrap UI-safe. Update `src/xs2n/profile/playwright.py` so browser login can wait autonomously for required cookies instead of prompting for Enter. Reuse browser-cookie discovery helpers from `src/xs2n/profile/browser_cookies.py` where possible, but avoid importing prompt-driven CLI code.

After the CLI layer is stable, add a dedicated `src/xs2n/ui/auth_window.py` that shows two sections: `Codex` and `X / Twitter`. The window should display the last doctor snapshot and expose explicit actions: refresh, Codex login/logout, X login, and X reset. The window should not own the cookies-file setting; it should display the path coming from the already-applied latest-run arguments so there is only one place where that path is edited. Every auth CLI action launched from the window must receive that same configured `--cookies-file` path, so the doctor/login/reset flow always refers to the same X session file that `report latest` will later use.

Finally, update `src/xs2n/ui/app.py` so it can run auth commands without pretending they are report runs. Add an explicit menu destination, `File -> Authentication`, that opens the auth window even before any blocked run. Startup should trigger a doctor refresh. Run buttons should trigger a doctor refresh first and only continue to the actual run command when readiness is satisfied. The command runner may need a lightweight per-command completion hook so auth refreshes update UI state without forcing an artifact rescan every time.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n` run the red/green cycle in small slices:

    uv run pytest tests/test_report_cli.py tests/test_ui_app.py tests/test_auth_recovery.py
    uv run pytest tests/test_ui_auth_window.py tests/test_ui_auth_commands.py tests/test_auth_cli.py -q

During implementation, use more focused commands such as:

    uv run pytest tests/test_auth_cli.py -q
    uv run pytest tests/test_ui_auth_window.py tests/test_ui_app.py -q

At the end, run the full suite:

    uv run pytest

Manual validation after code changes:

    uv run xs2n ui

Open the auth window from `File -> Authentication`, confirm the two sections render, press refresh, and verify that the status text changes based on the current local Codex/X sessions while showing the same cookies path configured for latest runs. Then try to launch `report latest` with missing X auth and confirm the UI blocks the run instead of starting it.

## Validation and Acceptance

Acceptance is met when:

1. `xs2n auth doctor --json` prints valid JSON describing `codex`, `x`, and run readiness.
2. `xs2n auth x login` can complete browser-based X login without terminal prompts, writing a valid cookies file.
3. The desktop UI shows two separate auth sections and refreshes them from the CLI at startup.
4. `report digest` is blocked when model auth is not ready, and `report latest` is blocked when either model auth or X auth is not ready.
5. Focused auth/UI tests pass, then the full `uv run pytest` suite passes.

## Idempotence and Recovery

`xs2n auth doctor --json` is safe to run repeatedly. `xs2n auth x login` is also safe to rerun; it should refresh or replace the cookies file rather than mutating unrelated state. `xs2n auth x reset` must only remove the configured cookies file and should not fail if the file is already absent.

If a browser-login attempt times out or Playwright is missing, the CLI should exit non-zero with an explicit recovery message. If the UI shows stale status, rerunning refresh must repair it because the source of truth lives in the CLI and the real auth files, not in the window state.

## Artifacts and Notes

Useful real-world evidence gathered before implementation:

    $ codex login status
    Logged in using ChatGPT

    $ python - <<'PY'
    from xs2n.agents.digest.credentials import resolve_digest_credentials
    print(resolve_digest_credentials().source)
    PY
    codex_auth_file

Real command output after implementation:

    $ uv run xs2n auth doctor --json --cookies-file cookies.json
    {
      "codex": {
        "status": "ready",
        "summary": "Codex credentials available.",
        "detail": "Source: codex_auth_file"
      },
      "x": {
        "status": "expired",
        "summary": "X session cookies are present but could not be verified.",
        "detail": "/Users/mx/Documents/Progetti/mine/active/xs2n/cookies.json"
      },
      "run_readiness": {
        "digest_ready": true,
        "latest_ready": false
      }
    }

## Interfaces and Dependencies

Define the shared auth result contract in `src/xs2n/schemas/auth.py`. The contract must contain a top-level doctor result with:

    codex: provider status
    x: provider status
    run_readiness: booleans for digest and latest

Each provider status should include, at minimum:

    status: string
    summary: string
    detail: string | None

In `src/xs2n/cli/auth.py`, define CLI entrypoints for:

    auth doctor --json --cookies-file <path>
    auth x login --cookies-file <path>
    auth x reset --cookies-file <path>

In `src/xs2n/ui/auth_window.py`, define a small window object that can:

    show()
    hide()
    update_status(...)

and invoke callbacks for:

    refresh
    codex_login
    codex_logout
    x_login
    x_reset

Revision note (2026-03-18): Initial implementation plan written after design approval. The plan chooses a dedicated auth window, a structured `auth doctor` CLI contract, and a UI-safe X login path to avoid terminal prompts in desktop-launched subprocesses.
Revision note (2026-03-18): Updated the plan after review to carry the configured `--cookies-file` through all auth commands and to require an explicit `File -> Authentication` menu entry as the direct UI affordance for the auth center.
Revision note (2026-03-18): Updated progress and outcomes after implementation. The auth feature is complete and verified with focused auth/UI tests plus a full-suite run that exposed 6 remaining unrelated failures in report/digest/schedule areas.
