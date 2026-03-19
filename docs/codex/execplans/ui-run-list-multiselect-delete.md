# UI Run List Multi-Select Delete

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`. It builds on the already-shipped run-list column work in `docs/codex/execplans/ui-run-list-preferences.md`, but repeats the implementation context needed for this follow-up interaction milestone.

## Purpose / Big Picture

After this change, the left run pane in `uv run xs2n ui` supports real multi-selection instead of a single highlighted row. A user can hold Shift or Control while selecting runs, then open a context menu on the run list and delete the selected run folders from disk after an explicit confirmation prompt. The visible proof is that multiple rows can stay selected together, the viewer still follows the active row, and right-clicking the run list offers a delete action that removes the chosen run directories and refreshes the browser.

## Progress

- [x] (2026-03-16 18:06Z) Audited the current `Fl_Hold_Browser` run-list wiring, run discovery helpers, and the existing tests that assume a single selected row.
- [x] (2026-03-16 18:10Z) Pulled fresh FLTK guidance through Context7, then verified the actual `pyfltk` binding surface locally for `Fl_Multi_Browser`, `Fl_Menu_Button`, browser selection methods, and dialog helpers.
- [x] (2026-03-16 18:27Z) Added `src/xs2n/ui/run_list_browser.py`, switched the app to `RunListBrowser`, and added `delete_runs(...)` in `src/xs2n/ui/artifacts.py`.
- [x] (2026-03-16 18:32Z) Wired delete confirmation, fallback run selection, and post-delete refresh behavior into `src/xs2n/ui/app.py`.
- [x] (2026-03-16 18:36Z) Added focused tests in `tests/test_ui_artifacts.py`, `tests/test_ui_run_list_browser.py`, and `tests/test_ui_app.py`, then passed `uv run pytest tests/test_ui_artifacts.py tests/test_ui_run_list_browser.py tests/test_ui_app.py`.
- [x] (2026-03-16 18:38Z) Passed `uv run pytest` (`156 passed`) and a live FLTK bootstrap smoke that instantiated `ArtifactBrowserWindow(data_dir=Path("data"))` with `RunListBrowser` as the real left-pane widget.

## Surprises & Discoveries

- Observation: the existing `pyfltk` binding exposes a dedicated `Fl_Multi_Browser` class with built-in multi-selection semantics, so the cleanest path is to switch widgets rather than simulate selection state in Python.
  Evidence: local `uv run python` inspection showed `Fl_Multi_Browser.selected(line)`, `select(line, val)`, and `value()` on the installed binding, and the bundled wrapper docs describe multi-selection behavior directly.

- Observation: the FLTK context-menu surface is available through `Fl_Menu_Button` and `fl_choice`/`fl_ask`, but the current app does not yet have a reusable browser subclass for right-click handling.
  Evidence: local inspection exposed `Fl_Menu_Button.popup()` and the bundled `pyfltk` test program `menubar.py` demonstrates `POPUP3` usage, while `src/xs2n/ui/app.py` currently instantiates the run list as a plain browser with no custom event handling.

- Observation: deleting a run is not just a UI concern because the authoritative state is the run directory tree under `data/report_runs*`.
  Evidence: `src/xs2n/ui/artifacts.py` rebuilds the run list from `scan_runs(data_dir)`, which walks run-root directories on disk every refresh.

- Observation: the stock `Fl_Multi_Browser` semantics are not enough for the exact modifier behavior the user asked for, because the bundled docs emphasize Mac-style toggling rather than the more familiar Shift-range plus Ctrl-add/remove pattern.
  Evidence: the local wrapper docs in `.venv/lib/python3.12/site-packages/fltk/fltk.py` describe `Fl_Multi_Browser` as “Macintosh style,” so the custom subclass now normalizes Shift/Ctrl behavior after the base widget processes the click.

## Decision Log

- Decision: add a dedicated run-list browser class instead of putting right-click event logic directly into `src/xs2n/ui/app.py`.
  Rationale: the main app file already owns layout, command launching, focus mode, and viewer orchestration. A small browser-specific abstraction keeps widget behavior isolated and easier to test.
  Date/Author: 2026-03-16 / Codex

- Decision: require a confirmation dialog before deleting selected runs from disk.
  Rationale: the requested delete action is destructive, and the UI should make the permanence explicit before removing run folders.
  Date/Author: 2026-03-16 / Codex

- Decision: keep the viewer tied to one active run even when multiple rows are selected for deletion.
  Rationale: the center and right panes still need one concrete run to inspect. Multi-selection is a batch action affordance for deletion, not a change to the single-run artifact viewer model.
  Date/Author: 2026-03-16 / Codex

- Decision: add a dedicated `RunListBrowser` subclass in `src/xs2n/ui/run_list_browser.py` instead of embedding modifier-key bookkeeping in `src/xs2n/ui/app.py`.
  Rationale: the subclass now owns multi-select normalization, context-click handling, and the hidden popup menu widget, which keeps the main browser window focused on orchestration rather than FLTK event details.
  Date/Author: 2026-03-16 / Codex

## Outcomes & Retrospective

The milestone is complete. The left run pane now uses a real `RunListBrowser` built on `Fl_Multi_Browser`, so multiple rows can stay selected together. Right-clicking the run pane opens a delete context menu, and the delete path confirms before removing the selected run folders from disk. The main architectural lesson was that this feature only stayed readable once the browser-specific event logic moved into its own module; trying to keep modifier handling inside `src/xs2n/ui/app.py` would have made the app file noticeably harder to trust.

## Context and Orientation

The desktop browser lives in `src/xs2n/ui/app.py`. That file builds a three-pane FLTK window. The left pane is the run list, the middle pane contains sections plus raw files for the selected run, and the right pane is a viewer. The run-list formatting rules such as visible columns and column widths live in `src/xs2n/ui/run_list.py`. Run discovery lives in `src/xs2n/ui/artifacts.py`, which scans `data/report_runs*` directories into `RunRecord` objects.

In this milestone, “multi-selection” means standard desktop behavior where more than one run row can stay selected at once, including additive selection with modifier keys. An “active run” means the one run whose artifacts are currently shown in the center and right panes. A “context menu” means the small right-click menu opened on the run list itself, not a top-menu-bar command.

The shipped implementation now uses `src/xs2n/ui/run_list_browser.py` for the left pane. That module wraps `fltk.Fl_Multi_Browser`, adds helper methods to read or set selected rows, and owns the right-click delete menu. `src/xs2n/ui/artifacts.py` now exposes `delete_runs(...)`, and `src/xs2n/ui/app.py` keeps the center/right panes on a single active run while letting multiple rows stay selected for deletion.

## Plan of Work

First, add a small UI-specific module that owns run-list widget behavior. This shipped as `src/xs2n/ui/run_list_browser.py`, which exposes `RunListBrowser` plus deterministic helpers for context-click detection, selected-index extraction, delete-message building, and fallback run selection after deletion.

Second, add a filesystem helper in `src/xs2n/ui/artifacts.py` for deleting one or more `RunRecord.run_dir` directories safely. The helper should delete the run directories themselves, ignore already-missing paths, and raise a useful `OSError` when deletion fails so the UI can alert the user instead of silently desynchronizing.

Third, update `src/xs2n/ui/app.py` to instantiate the new multi-select browser, translate browser selection into an active run for the viewer, and wire a delete-selected-runs action that confirms with the user, deletes the selected run folders, refreshes the run list, and lands on a sensible remaining run when possible.

Fourth, update the tests. `tests/test_ui_artifacts.py` now verifies the delete helper removes run directories safely. `tests/test_ui_run_list_browser.py` locks the pure selection/context-menu helpers. `tests/test_ui_app.py` covers app-level delete confirmation, cancel behavior, empty-selection alerts, and fallback selection after removal.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, the intended implementation and validation flow is:

    uv run pytest tests/test_ui_artifacts.py tests/test_ui_run_list_browser.py tests/test_ui_app.py
    uv run pytest
    uv run xs2n ui

During the interactive check, confirm these behaviors:

1. Click one run and the viewer updates as before.
2. Hold Shift or Control and select multiple run rows so more than one stays highlighted.
3. Right-click the run pane and see a delete action for the current selection.
4. Confirm deletion and see the selected run folders disappear from the left pane after refresh, with the next remaining run becoming active when possible.

## Validation and Acceptance

Acceptance is behavioral:

1. The run list supports selecting multiple rows at once through the native FLTK multi-selection browser behavior.
2. The viewer still follows one active run and does not crash when multiple rows are selected.
3. A context-menu delete action exists on the run list and only runs after a confirmation prompt.
4. Deleting selected runs removes the corresponding run directories from disk and refreshes the run list.
5. Focused pytest coverage passes for the delete helper, run-list browser helpers, and app wiring.

Observed validation:

1. Passed: `uv run pytest tests/test_ui_artifacts.py tests/test_ui_run_list_browser.py tests/test_ui_app.py` -> `24 passed`.
2. Passed: `uv run pytest` -> `156 passed`.
3. Passed: `uv run python - <<'PY' ... ArtifactBrowserWindow(data_dir=Path("data")) ... PY` -> `{'runs': 13, 'selected_run_id': '20260316T000914Z', 'browser_class': 'RunListBrowser'}`.

## Idempotence and Recovery

Re-running the tests is safe. Re-opening the UI is safe. The destructive path in the actual product is not reversible because it deletes run folders from disk, so the confirmation dialog is the main safety barrier. If deletion logic regresses during implementation, the safe fallback is to keep multi-selection shipped while temporarily disabling the delete action rather than risking silent filesystem damage.

## Artifacts and Notes

Key files expected to change in this milestone:

- `docs/codex/execplans/ui-run-list-multiselect-delete.md`
- `src/xs2n/ui/artifacts.py`
- `src/xs2n/ui/app.py`
- `src/xs2n/ui/run_list_browser.py`
- `tests/test_ui_artifacts.py`
- `tests/test_ui_app.py`
- `tests/test_ui_run_list_browser.py`
- `docs/codex/autolearning.md`

## Interfaces and Dependencies

At the end of this milestone, the app should still expose:

    run_artifact_browser(*, data_dir: Path, initial_run_id: str | None = None) -> None

The run-artifact layer should expose a stable delete helper equivalent to:

    delete_runs(runs: Sequence[RunRecord]) -> None

The UI layer should expose a run-list browser or helper capable of:

    context_click_requested(...) -> bool
    selected_run_indexes(browser, *, row_count: int) -> list[int]
    fallback_run_id_after_delete(runs: Sequence[RunRecord], *, selected_indexes: Sequence[int]) -> str | None

`RunListBrowser` itself should provide methods equivalent to:

    selected_indexes() -> list[int]
    set_selection(*, selected_indexes: Sequence[int], active_index: int | None) -> None
    show_delete_context_menu() -> None

Revision note (2026-03-16): Created this ExecPlan for the follow-up run-list interaction milestone covering multi-selection and delete-via-context-menu behavior.
Revision note (2026-03-16): Updated the plan after implementation to record the shipped `RunListBrowser`, the delete-on-disk flow, the fallback active-run behavior, and the passing validation results.
