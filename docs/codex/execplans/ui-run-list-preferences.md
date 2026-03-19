# UI Run List Preferences

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`. It builds on the existing desktop artifact browser and the in-progress run-arguments panel already present in `src/xs2n/ui/app.py`, but repeats the implementation context needed for this narrower milestone.

## Purpose / Big Picture

After this change, the left-most pane in `uv run xs2n ui` becomes easier to understand and easier to tune. By default it shows only the run date and the digest title, which is the information a human usually wants first. The pane also gains visible column headers and a small preferences panel where the user can choose additional columns such as source, status, model, counts, and run id. The visible proof is that the run list opens with `Date` and `Digest` headers, dragging the left pane keeps the columns readable, and toggling columns in the preferences tab updates both the header row and the run rows immediately.

## Progress

- [x] (2026-03-16 17:08Z) Audited the current FLTK browser layout, the in-progress run-arguments panel, and the run artifact shape to identify the cleanest integration point for run-list preferences.
- [x] (2026-03-16 17:10Z) Pulled fresh FLTK guidance through Context7 and verified the actual `pyfltk` widget methods locally, including `column_widths()`, `resize()`, `align()`, and `show()/hide()`.
- [x] (2026-03-16 17:23Z) Added `RunRecord.digest_title` extraction in `src/xs2n/ui/artifacts.py` with useful fallbacks for runs that do not yet have a meaningful digest heading.
- [x] (2026-03-16 17:30Z) Added `src/xs2n/ui/run_list.py` to own the default visible columns, row rendering, and responsive width math.
- [x] (2026-03-16 17:39Z) Reworked the left pane in `src/xs2n/ui/app.py` into a header strip plus a browser whose column widths track pane-size changes during idle processing.
- [x] (2026-03-16 17:44Z) Extended `src/xs2n/ui/run_preferences.py` with a `Run List` tab so column toggles live beside the existing digest/latest preferences.
- [x] (2026-03-16 17:47Z) Added focused tests and verified the behavior with `uv run pytest tests/test_ui_artifacts.py tests/test_ui_run_list.py tests/test_ui_run_preferences.py tests/test_ui_app.py` plus a live `ArtifactBrowserWindow(...)` smoke.

## Surprises & Discoveries

- Observation: while the first sketch assumed the right-side inspector tabs would host the new controls, the current worktree had already pulled command arguments into a standalone `RunPreferencesWindow`.
  Evidence: `src/xs2n/ui/app.py` now launches `src/xs2n/ui/run_preferences.py` from the File -> Preferences action, and that window already owns the digest/latest form widgets.

- Observation: `Fl_Hold_Browser` supports real tab-delimited columns, but it does not provide a high-level spreadsheet-style header row by itself in this binding.
  Evidence: Context7 and live `uv run python` inspection both exposed `column_char()` and `column_widths()` on `Fl_Hold_Browser`, while header-specific browser APIs were not present in the inspected binding surface.

- Observation: the current digest file title line is generic (`# xs2n Digest Issue ...`) and not useful as the default run-list title.
  Evidence: live `digest.md` inspection showed the meaningful human title is usually the first `### ...` issue heading, with fallback copy such as `No high-signal issues were produced in this run.` when no issue heading exists.

## Decision Log

- Decision: move the run-list formatting and width calculation out of `src/xs2n/ui/artifacts.py` into a dedicated `src/xs2n/ui/run_list.py` module.
  Rationale: the run browser columns, header labels, and width rules are UI behavior, not artifact-scanning behavior, and keeping them separate makes the orchestration file easier to scan.
  Date/Author: 2026-03-16 / Codex

- Decision: derive the default “digest title” from the rendered digest artifact rather than from `run.json`.
  Rationale: the existing run metadata does not currently store a human-readable digest title, while `digest.md` already contains the best available headline for the run.
  Date/Author: 2026-03-16 / Codex

- Decision: keep the run-list preferences session-local for this milestone.
  Rationale: the user asked for a preference panel and configurable columns, but there is no existing UI-settings storage layer in this repository. In-memory preferences keep the feature focused on navigation quality first.
  Date/Author: 2026-03-16 / Codex

- Decision: add the run-list controls to the existing `RunPreferencesWindow` instead of creating a second preference surface inside `src/xs2n/ui/app.py`.
  Rationale: the current codebase already had a native preferences window for digest/latest command settings, so reusing it kept control flow honest and avoided splitting app configuration across two UI surfaces.
  Date/Author: 2026-03-16 / Codex

## Outcomes & Retrospective

The milestone is complete. The left pane now opens as a compact `Date` + `Digest` list with a real header strip, the digest title comes from the first meaningful heading inside `digest.md`, and the existing Preferences window gained a `Run List` tab that can toggle extra columns such as source, status, model, counts, and run id. The result feels much closer to a retro desktop outliner than a raw log browser, while still letting debugging-oriented users opt back into denser metadata. The most useful lesson was architectural: once the repo already had a standalone preferences window, using it was cleaner than continuing to push configuration into the main browser layout.

## Context and Orientation

The desktop artifact browser lives in `src/xs2n/ui/app.py`. That file builds a three-pane FLTK window. The left pane now contains a header strip plus a `Fl_Hold_Browser` for runs. The middle pane lists curated sections and raw files for the selected run. The right pane is the artifact viewer. The separate preferences window lives in `src/xs2n/ui/run_preferences.py` and now owns digest arguments, latest arguments, and run-list column toggles.

Run discovery lives in `src/xs2n/ui/artifacts.py`. That module scans every `data/report_runs*` directory, builds `RunRecord` instances, and knows where `digest.md` lives for each run when present. It currently also contains the old one-line run-summary formatter that the left pane uses.

For this milestone, a “run-list column” means one visible field in the left pane such as date, digest title, source root, status, model, counts, or run id. A “header strip” means the dedicated row of FLTK boxes above the browser that labels those columns. A “preferences panel” means the `Run List` tab inside `src/xs2n/ui/run_preferences.py`.

## Plan of Work

First, update `src/xs2n/ui/artifacts.py` so `RunRecord` carries a digest title derived from `digest.md` when available. The extraction should prefer the first `###` heading because that is the actual issue headline users care about. If no such heading exists, the extractor should fall back to the first non-empty line after `## Top Issues`, and then to a stable fallback such as the run id when the file is missing or generic.

Second, add `src/xs2n/ui/run_list.py` to own the run-list column definitions, default visible columns, row rendering, header labels, and responsive width calculation. This module should accept a `RunRecord` plus a sequence of visible column keys and return both the tab-delimited browser row and the integer column widths needed by FLTK. It should also normalize the visible-column list so invalid or empty selections fall back to a sensible default.

Third, reshape the left pane in `src/xs2n/ui/app.py` into a small group that contains a fixed-height header strip above the existing browser. The browser should continue to own row selection, but the header strip should be visually aligned to the same column widths. The app should recompute widths when the pane changes size by watching the browser width during idle processing and only refreshing the layout when the width or visible-column selection has changed.

Fourth, add a `Run List` tab in `src/xs2n/ui/run_preferences.py` with checkboxes for the available columns. The tab should update the visible columns immediately through a callback into `src/xs2n/ui/app.py`. The default checked state should be `Date` and `Digest`, with the other options off. The update path must preserve the current selection if possible.

Fifth, move the focused tests into deterministic places. `tests/test_ui_artifacts.py` should verify digest-title extraction. A new `tests/test_ui_run_list.py` should verify the default row shape, fallback behavior, and responsive width math. `tests/test_ui_app.py` should cover the run-list preference wiring without requiring a live FLTK event loop.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, the intended implementation and validation flow is:

    uv run pytest tests/test_ui_artifacts.py tests/test_ui_run_list.py tests/test_ui_run_preferences.py tests/test_ui_app.py
    uv run python - <<'PY'
    from pathlib import Path
    from xs2n.ui.app import ArtifactBrowserWindow
    browser = ArtifactBrowserWindow(data_dir=Path("data"))
    print(browser.runs_browser.text(1))
    print(browser.runs_browser.w())
    print(browser.run_list_header_boxes[0].label())
    browser.window.hide()
    browser.preferences_window.hide()
    PY

If an interactive check is helpful and the FLTK runtime is installed, also run:

    uv run xs2n ui

Then confirm that the left pane shows `Date` and `Digest` headers by default, toggling extra fields in the `Run List` tab inside Preferences updates the list immediately, and dragging the left pane wider gives more room primarily to the digest-title column.

## Validation and Acceptance

Acceptance is behavioral:

1. The left pane defaults to two visible columns: `Date` and `Digest`.
2. The left pane shows visible headers aligned to the run rows.
3. A `Run List` preferences tab exists in the Preferences window and can toggle additional columns on and off.
4. Dragging the pane width updates the column widths without corrupting the row layout.
5. Focused pytest coverage passes for digest-title extraction, run-list formatting/width rules, and app-level preference wiring.

## Idempotence and Recovery

This milestone is read-only over existing run artifacts and stores preferences only in memory. Re-running the tests is safe. Re-opening the UI is safe. If the responsive header strip regresses, the safe fallback is to keep the deterministic `src/xs2n/ui/run_list.py` helpers and temporarily restore a fixed-width browser layout while preserving the tests that lock the desired end behavior.

## Artifacts and Notes

Key files expected to change in this milestone:

- `docs/codex/execplans/ui-run-list-preferences.md`
- `src/xs2n/ui/artifacts.py`
- `src/xs2n/ui/run_list.py`
- `src/xs2n/ui/app.py`
- `src/xs2n/ui/run_preferences.py`
- `tests/test_ui_artifacts.py`
- `tests/test_ui_run_list.py`
- `tests/test_ui_run_preferences.py`
- `tests/test_ui_app.py`
- `docs/codex/autolearning.md`

## Interfaces and Dependencies

At the end of this milestone, `src/xs2n/ui/artifacts.py` should expose `RunRecord.digest_title` as a stable field populated during scan when possible.

At the end of this milestone, `src/xs2n/ui/run_list.py` should expose deterministic helpers equivalent to:

    DEFAULT_RUN_LIST_COLUMN_KEYS: tuple[str, ...]
    visible_run_list_columns(column_keys: Sequence[str]) -> list[RunListColumn]
    format_run_list_row(run: RunRecord, *, column_keys: Sequence[str]) -> str
    compute_run_list_widths(total_width: int, *, column_keys: Sequence[str]) -> tuple[int, ...]

`src/xs2n/ui/app.py` must keep exposing:

    run_artifact_browser(*, data_dir: Path, initial_run_id: str | None = None) -> None

Revision note (2026-03-16): Created this ExecPlan for the follow-up run-list usability milestone after the first-column cleanup revealed a need for explicit headers, digest-first defaults, and a dedicated preference surface.
Revision note (2026-03-16): Updated the plan after implementation to reflect the shipped design: the run-list controls landed in `RunPreferencesWindow`, the left pane now uses a dedicated header strip, and focused tests plus a live widget smoke passed.
