# UI Latest Primary And Saved-Run HTML Alias

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the desktop UI makes the right operational path obvious: `xs2n report latest` is the primary run action instead of sitting beside an equally prominent raw `issues` launcher. A user can still build issues from an existing timeline snapshot in the CLI, and they now have a more obvious command for turning a saved issue run into `digest.html` when they need to recover HTML for an older run that only wrote JSON artifacts.

The visible proof is:

- the desktop `Run` menu keeps `Latest 24h` and `Refresh Following Sources`, but no longer exposes a peer `Issues` launcher;
- the toolbar keeps one primary run button for `report latest`;
- `xs2n report html --run-dir <run_id>` renders HTML from an existing saved issue run;
- `xs2n report render --run-dir <run_id>` still works for compatibility.

## Progress

- [x] (2026-03-19 11:45Z) Audited the current report CLI, desktop UI launch surfaces, README, and direct-call tests to map the smallest safe change.
- [x] (2026-03-19 11:52Z) Pulled fresh Typer command and FLTK help-view guidance through Context7 before editing the CLI/UI surfaces.
- [x] (2026-03-19 11:57Z) Added failing tests for the new `report html` entrypoint, `report issues` follow-up hint, and the UI contract that treats `latest` as the only primary run action.
- [x] (2026-03-19 12:04Z) Implemented the CLI helper/alias and updated the desktop UI command strip and run menu to prioritize `latest`.
- [x] (2026-03-19 12:08Z) Updated `README.md` and `docs/codex/autolearning.md` to reflect the new HTML command naming and the latest-first UI.
- [x] (2026-03-19 12:10Z) Verified the milestone with `uv run pytest tests/test_report_cli.py tests/test_ui_app.py -q`.

## Surprises & Discoveries

- Observation: the repository already had the saved-run HTML behavior in code, but the command name was easy to miss.
  Evidence: `src/xs2n/cli/report.py` already exposed `report render`, and the user still asked for “a CLI command” to produce HTML from issues.

- Observation: the current UI confusion was mostly about prominence, not capability.
  Evidence: `src/xs2n/ui/app.py` already preferred `digest.html` in the viewer, but the menu and toolbar still presented `report issues` and `report latest` as peers.

## Decision Log

- Decision: keep the raw issue-building path in the CLI, but remove it from the primary desktop launch surfaces.
  Rationale: the desktop app is the cron-friendly, operator-facing surface, and for that audience `report latest` is the main workflow while `report issues` is a narrower offline/replay tool.
  Date/Author: 2026-03-19 / Codex

- Decision: add `xs2n report html` while preserving `xs2n report render`.
  Rationale: the new name is more literal and easier to discover, but preserving the older command avoids breaking scripts or habits already built around `render`.
  Date/Author: 2026-03-19 / Codex

## Outcomes & Retrospective

The UI now pushes users toward the end-to-end path instead of asking them to choose between two similarly weighted commands. The CLI also better matches the operator mental model: if a run already has issue JSON artifacts, `report html` says exactly what it does. The main lesson from this milestone is that command discovery matters as much as implementation completeness; the code already knew how to render HTML, but the naming and UI prominence still produced friction.

## Context and Orientation

The report CLI lives in `src/xs2n/cli/report.py`. The `issues` command builds issue artifacts from an existing timeline file. The `latest` command is the broader workflow: ingest recent timeline data, create a time-window snapshot, build issues from that snapshot, and then render `digest.html`. The saved-run HTML renderer itself lives behind `render_issue_digest_html(...)`, imported from `xs2n.agents`.

The desktop UI lives in `src/xs2n/ui/app.py`. The menu bar and command strip are built inside `ArtifactBrowserWindow._build_window(...)`. That file also owns the empty-state message shown when there are no run folders yet. The right-hand viewer already prefers `digest.html` when it exists, so this milestone does not need a second rendering stack or a custom issue document viewer.

The most relevant direct-call tests are `tests/test_report_cli.py` for report commands and `tests/test_ui_app.py` for app-level launch behavior.

## Plan of Work

First, keep the CLI implementation boring and explicit. Add one small helper in `src/xs2n/cli/report.py` that renders a saved issue run into HTML and converts runtime failures into Typer exits. Use that helper from both the existing `render` command and the new `html` command so the behavior stays identical. Also update the `issues` command output to print the exact follow-up command a user can run later against the saved run directory.

Second, simplify the desktop launch surface in `src/xs2n/ui/app.py`. Remove the peer `Issues` action from the run menu and command strip, keep `Latest 24h` as the only primary run launcher, give it the direct “play/run” button symbol, and keep the existing `Refresh Following Sources` utility action. Update the empty-state copy so it points only at `xs2n report latest`, because that is now the recommended way to create runs from the UI.

Third, update user-facing docs. `README.md` should describe `report html` as the primary saved-run HTML command and mention `report render` as an alias. `docs/codex/autolearning.md` should record the naming and UI-prominence lesson so later milestones do not regress back to equal-weight issue/latest launchers.

## Concrete Steps

Run these commands from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Write the failing tests:

       uv run pytest tests/test_report_cli.py tests/test_ui_app.py -q

   Before the implementation, expect an import/contract failure because `html_render` and the latest-primary UI constants do not exist yet.

2. Implement the CLI and UI changes in:

   - `src/xs2n/cli/report.py`
   - `src/xs2n/ui/app.py`
   - `README.md`
   - `docs/codex/autolearning.md`

3. Re-run the focused verification:

       uv run pytest tests/test_report_cli.py tests/test_ui_app.py -q

   Expected result after the implementation:

       39 passed

## Validation and Acceptance

Acceptance is behavioral.

Run `uv run xs2n report html --run-dir data/report_runs/<run_id>` and expect a line ending with `digest.html`. Run `uv run xs2n report render --run-dir data/report_runs/<run_id>` and expect the same result, proving compatibility.

Open `uv run xs2n ui` and inspect the main launch surface. The run menu should expose `Refresh Following Sources` and `Latest 24h`, and the toolbar should have one primary run button that launches `report latest`. There should no longer be a peer `Issues` launch button competing with it.

The empty-state viewer text should point the operator at `xs2n report latest` when no run folders exist yet.

## Idempotence and Recovery

The new `report html` command is idempotent for a saved run: re-running it overwrites `digest.html` with a fresh render from the saved `issues.json` and `issue_assignments.json`. The `render` alias remains available as a rollback path if any user muscle memory still depends on it.

The UI changes are presentation-only around existing CLI launchers. If a future contributor needs to re-expose `report issues` in the UI, they can restore the removed menu/button wiring without touching the artifact viewer or CLI runtime behavior.

## Artifacts and Notes

Focused verification command used for this milestone:

    uv run pytest tests/test_report_cli.py tests/test_ui_app.py -q

Observed result after implementation:

    39 passed, 218 warnings in 0.71s

## Interfaces and Dependencies

`src/xs2n/cli/report.py` must expose:

    @report_app.command("html")
    def html_render(...): ...

and keep:

    @report_app.command("render")
    def render(...): ...

with both commands routing through one shared helper that calls `render_issue_digest_html(run_dir=...)`.

`src/xs2n/ui/app.py` must define the constants that describe the latest-first launch contract:

    PRIMARY_RUN_BUTTON_SYMBOL = "@>"
    PRIMARY_RUN_BUTTON_TOOLTIP = "Run the configured `xs2n report latest` command."
    RUN_MENU_LAUNCH_LABELS = ("&Run/&Refresh Following Sources", "&Run/&Latest 24h")

Revision note (2026-03-19): Created and completed this ExecPlan in one implementation pass so the repository keeps a restartable record of why the desktop UI now prioritizes `report latest` and why `report html` exists alongside `report render`.
