# UI Run Arguments Panel

> Historical context: this ExecPlan captures the earlier UI work for digest/latest run arguments. The current active report surface is `report issues`, `report html`, `report latest`, and `report schedule`.

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a user can open `uv run xs2n ui`, edit the arguments used for the report runs, and launch those commands from the desktop UI without being locked into the current hardcoded defaults. The visible proof is that the UI shows a dedicated run-arguments panel, the launch buttons use the values shown in that panel, and invalid values are rejected before the subprocess starts.

## Progress

- [x] (2026-03-15 23:52Z) Audited the current report and desktop UI code paths to map the real argument surface and find the smallest safe integration point.
- [x] (2026-03-15 23:52Z) Pulled fresh FLTK documentation through Context7 to confirm the widget APIs needed for text inputs, check buttons, grouped panels, and tabbed layout.
- [x] (2026-03-15 23:54Z) Added `src/xs2n/ui/run_arguments.py` with deterministic digest/latest defaults, form normalization, validation, and CLI argument rendering helpers.
- [x] (2026-03-15 23:56Z) Added a dedicated `Preferences` window for digest/latest arguments, wired it into `File -> Preferences`, and routed both run buttons through that window instead of embedding the forms in the main inspector pane.
- [x] (2026-03-16 00:12Z) Added explicit `Apply` and `Cancel` buttons so preference edits remain draft-only until applied and are discarded when cancelled or when the window closes.
- [x] (2026-03-15 23:57Z) Added focused tests in `tests/test_ui_run_arguments.py` and `tests/test_ui_app.py`, then ran the focused UI suite and the full pytest suite successfully.
- [x] (2026-03-15 23:57Z) Updated `README.md` and `docs/codex/autolearning.md` so the new UI behavior and implementation notes are captured in the repository.

## Surprises & Discoveries

- Observation: the current UI hardcodes both run actions directly inside `src/xs2n/ui/app.py`, so adding a panel cleanly depends on extracting command-building logic first rather than bolting more parsing into the window callbacks.
  Evidence: `_on_run_digest_clicked()` always launches `["report", "digest"]`, and `_on_run_latest_clicked()` always launches `["report", "latest", "--lookback-hours", "24"]`.

- Observation: the FLTK surface already available in this environment includes `Fl_Tabs`, `Fl_Input`, `Fl_Int_Input`, `Fl_Check_Button`, and `Fl_Group`, which is enough for a native panel without introducing a second toolkit.
  Evidence: `uv run python` import checks confirmed those widget classes are present in the installed `pyfltk` package.

- Observation: argument editing belongs in its own window rather than in the always-visible artifact inspector.
  Evidence: after moving the form into `File -> Preferences`, the main browser recovered a simpler `Run Details` pane and the preferences flow stayed discoverable without crowding the artifact viewer.

- Observation: moving preferences into their own window is not enough by itself; if run actions read straight from live widgets, the behavior still feels “applied on the go”.
  Evidence: the final implementation now keeps separate applied state and draft widget state, and focused tests prove that editing a field does not change the launched command until `Apply` is clicked.

## Decision Log

- Decision: model digest and latest arguments in a dedicated module instead of storing raw widget strings directly in `app.py`.
  Rationale: the command defaults, validation rules, and CLI rendering are deterministic logic that deserve tests and would make the window file harder to scan if left inline.
  Date/Author: 2026-03-15 / Codex

- Decision: keep the existing two launch buttons and give each command its own form state rather than collapsing the UI down to one generic “run” action.
  Rationale: the current browser already teaches the user that there are two workflows, `digest` and `latest`, and preserving that affordance keeps the UI closer to the CLI mental model.
  Date/Author: 2026-03-15 / Codex

- Decision: keep digest/latest forms in a dedicated `Preferences` window opened from the menu, and keep the main inspector focused on run metadata plus artifact viewing.
  Rationale: the browser’s primary job is inspection. Separating configuration into preferences matches desktop utility conventions better and keeps the main pane calm.
  Date/Author: 2026-03-15 / Codex

- Decision: treat the entire Preferences window as a draft editor with explicit `Apply` and `Cancel` actions.
  Rationale: this prevents accidental live changes while typing, makes cancellation behavior clear, and keeps run launches pinned to the last acknowledged configuration.
  Date/Author: 2026-03-16 / Codex

## Outcomes & Retrospective

The feature is implemented and working. `xs2n ui` now exposes editable digest and latest argument forms in a dedicated `Preferences` window, and the launch buttons use the last applied values instead of hardcoded defaults or live widget state. The important architectural win was keeping deterministic command-building logic in its own module so the FLTK file stayed readable and the new behavior could be verified with ordinary unit tests instead of brittle GUI automation. The main lesson was placement-related and state-related: command configuration feels better as a secondary preferences surface, and preferences need an explicit draft/apply model to avoid surprising “live” behavior.

## Context and Orientation

The top-level desktop command is `xs2n ui`, implemented in `src/xs2n/cli/ui.py`. That command lazily imports `run_artifact_browser(...)` from `src/xs2n/ui/app.py`. The FLTK window in `app.py` already has a menu bar, a compact command strip, a list of run folders, a list of artifacts, a read-only details panel, and a viewer that renders the selected artifact.

Today, the launch actions inside `app.py` do not read any UI state. They shell out to the CLI with hardcoded argument lists. The actual CLI contract lives in `src/xs2n/cli/report.py`. `report issues` accepts `timeline_file`, `output_dir`, `taxonomy_file`, `model`, and `parallel_workers`. `report latest` accepts timeline-ingestion options such as `since`, `lookback_hours`, `cookies_file`, `limit`, `sources_file`, and `home_latest`, then reuses the issue-building options for the second half of the flow.

The new feature needs two layers. First, a deterministic layer must convert UI values into validated CLI argument lists. Second, the UI must expose those values in a small native preferences window that matches the existing 90s utility-app style.

## Plan of Work

Create `src/xs2n/ui/run_arguments.py` with small data classes for the two run modes. That module should import the real defaults from the CLI-related packages, normalize empty text fields back to those defaults where appropriate, validate integer fields that must stay positive, and expose helper methods that return the exact CLI argument lists used by `subprocess.run(...)`.

Then add a dedicated preferences window module that owns the FLTK report forms. The issues form should expose the five real `report issues` options. The latest form should expose the meaningful `report latest` options, including the `home_latest` toggle. Update `src/xs2n/ui/app.py` so `File -> Preferences` opens that window, the run buttons pull commands from it, validation failures re-open the relevant preferences tab, and the main inspector returns to showing run metadata.

Add focused tests in `tests/test_ui_run_arguments.py` for default rendering, optional-argument omission, and validation failures. Add light UI-callback tests in `tests/test_ui_app.py` so the run buttons are proven to route through the new command builders without needing a live FLTK window. Update `docs/codex/autolearning.md` with the implementation and testing notes once the work is complete.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, the intended implementation and validation flow is:

    uv run pytest tests/test_ui_run_arguments.py tests/test_ui_app.py tests/test_ui_cli.py
    uv run pytest
    uv run python - <<'PY'
    from pathlib import Path
    from xs2n.ui.app import ArtifactBrowserWindow
    browser = ArtifactBrowserWindow(data_dir=Path("data"))
    print("window", browser.window.label())
    print("details_label", browser.run_details.label())
    browser.preferences_window.show_latest_tab()
    print("prefs_title", browser.preferences_window.window.label())
    print("prefs_tab", browser.preferences_window.tabs.value().label())
    browser.close_browser()
    PY

Observed results:

    1. `uv run pytest tests/test_ui_run_arguments.py tests/test_ui_app.py tests/test_ui_cli.py` passed with `15 passed`.
    2. `uv run pytest` passed with `129 passed`.
    3. The bootstrap smoke printed:

       window xn2s
       details_label Run Details
       prefs_title Preferences
       prefs_tab Latest

The proof is that the focused tests pass, the window still bootstraps, and the UI now exposes editable digest/latest arguments through `File -> Preferences` before launching commands.

## Validation and Acceptance

Acceptance is behavioral:

1. `uv run xs2n ui` shows a dedicated run-arguments preferences window reachable from the desktop app menu.
2. Editing the digest form changes the command launched by the digest action.
3. Editing the latest form changes the command launched by the latest action.
4. Invalid numeric values such as `0` parallel workers or `0` lookback hours are rejected before the subprocess starts.
5. The focused UI tests and the full pytest suite pass after the change.

Current status:

1. Passed by bootstrap smoke plus the real `ArtifactBrowserWindow` instantiation check and preferences-window tab selection.
2. Passed by `tests/test_ui_app.py::test_current_digest_command_reads_form_values`.
3. Passed by `tests/test_ui_app.py::test_current_latest_command_reads_form_values`.
4. Passed by `tests/test_ui_run_arguments.py` validation coverage and `tests/test_ui_app.py::test_run_latest_click_surfaces_form_validation_error`.
5. Passed: `15 passed` in the focused UI suite and `129 passed` in the full repository suite.

## Idempotence and Recovery

Re-running the tests is safe. Re-opening the UI is safe. The new panel only changes the subprocess arguments used when the user explicitly starts a command; it does not write configuration to disk. If a form value is invalid, the UI should refuse to launch the command and let the user correct the value in place.

## Artifacts and Notes

Key implementation files for this feature are expected to be:

- `src/xs2n/ui/app.py`
- `src/xs2n/ui/run_arguments.py`
- `tests/test_ui_app.py`
- `tests/test_ui_run_arguments.py`
- `docs/codex/autolearning.md`

## Interfaces and Dependencies

At the end of this work, the UI layer should expose deterministic helpers with interfaces shaped like:

    IssuesRunArguments.from_form(...)
    IssuesRunArguments.to_cli_args() -> list[str]
    LatestRunArguments.from_form(...)
    LatestRunArguments.to_cli_args() -> list[str]

`src/xs2n/ui/app.py` should keep exposing:

    run_artifact_browser(*, data_dir: Path, initial_run_id: str | None = None) -> None

Revision note (2026-03-15): Created the initial living ExecPlan before implementation so the feature can be resumed from this file alone.
Revision note (2026-03-15): Updated the plan to the implementation-complete state with validation evidence so this file remains restartable after the feature landed.
