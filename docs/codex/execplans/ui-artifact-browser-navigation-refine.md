# UI Artifact Browser Navigation Refine

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`. It builds on the shipped desktop browser described in `docs/codex/execplans/ui-artifact-browser.md`, but repeats the implementation context needed for this narrower navigation milestone.

## Purpose / Big Picture

After this change, a user opening `xs2n ui` can browse a run with clearer intent. The right column no longer duplicates `run.json` in a special read-only details widget. Instead, the center column becomes a two-level navigator: a short curated list of important sections at the top and the complete raw artifact list beneath it. Both navigators drive the same read-only viewer, so the user can jump to “Digest” or “Run metadata” quickly without losing access to every underlying file.

The visible proof is:

- the floating `Run Details` label is gone;
- the dedicated run-details pane is gone;
- the center column shows a top sections list plus a bottom raw-files list;
- selecting either a curated section or a raw file opens the same artifact in the right-hand viewer.

## Progress

- [x] (2026-03-16 15:12Z) Audited the current FLTK layout, artifact ordering rules, and tests to identify the smallest refactor that removes the duplicated run-details pane.
- [x] (2026-03-16 15:27Z) Implemented curated artifact sections in `src/xs2n/ui/artifacts.py` and wired the middle column to render sections above raw files.
- [x] (2026-03-16 15:35Z) Removed the dedicated run-details pane so the right column is now viewer-only and run metadata is reached through `run.json`.
- [x] (2026-03-16 15:41Z) Added focused regression tests for curated section labels and for synchronized section/raw-file selection behavior.
- [x] (2026-03-16 15:44Z) Ran the focused UI pytest targets, compiled the touched modules, and smoke-tested `ArtifactBrowserWindow(data_dir=Path("data"))`.

## Surprises & Discoveries

- Observation: the current browser already stores the real source of truth for run metadata in `run.json`, so the separate `Fl_Multiline_Output` details pane is redundant rather than additive.
  Evidence: `src/xs2n/ui/app.py` fills `self.run_details` with `format_run_details(run)`, while `src/xs2n/ui/artifacts.py` already exposes `run.json` as a first-class artifact and `load_artifact_text(...)` pretty-prints JSON for the viewer.

- Observation: appending phase names inline to every artifact label makes the current single artifact list harder to scan once a run has many files.
  Evidence: `src/xs2n/ui/app.py` currently renders labels like `run.json [render_digest]`, even though the most common user task is to jump to a small set of important artifacts first.

- Observation: this repository already has a separate `Preferences` window for digest/latest arguments, so removing the run-details pane became cleaner than expected because the right column no longer needed to reserve any space above the viewer.
  Evidence: the current `ArtifactBrowserWindow` constructs `RunPreferencesWindow()` during initialization and routes the run actions through `preferences_window.current_digest_command()` and `preferences_window.current_latest_command()`.

## Decision Log

- Decision: replace the dedicated right-side details widget with a curated section browser rather than trying to restyle the existing pane.
  Rationale: the data already exists as a real artifact (`run.json`), so a curated navigator removes duplication and aligns every selection path with one viewer contract.
  Date/Author: 2026-03-16 / Codex

- Decision: keep the complete raw artifact list visible under the curated sections list.
  Rationale: the curated list should speed up common navigation, but the browser still needs to expose every file and directory written by the run for debugging and trace inspection.
  Date/Author: 2026-03-16 / Codex

## Outcomes & Retrospective

The layout change is complete. The browser now has one viewer in the right column and two navigation surfaces in the middle column: curated sections and raw files. The biggest user-facing win is that run metadata is no longer duplicated in a special pane; `run.json` is now the single source of truth in the UI as well as on disk. The focused tests passed, and a real FLTK bootstrap smoke confirmed the window now initializes successfully with the new layout.

## Context and Orientation

The desktop browser lives in `src/xs2n/ui/app.py`. That file currently builds a three-pane FLTK window: runs on the left, a single artifact list in the middle, and a right column split between `Run Details` and the HTML/text viewer. The artifact data model lives in `src/xs2n/ui/artifacts.py`. That module already knows how to discover run folders, sort artifact names, infer file kinds, and pretty-print JSON files when they are opened.

In this repository, an “artifact” is any visible file or directory inside one run folder such as `digest.md`, `run.json`, `phases.json`, or `llm_calls/001_process_threads_....json`. A “section” in this milestone is a curated shortcut to one of those existing artifacts. It is not a new file format or a second storage layer.

The user-visible behavior to preserve is simple: selecting a run refreshes the middle and right columns, and selecting something in the middle column renders the chosen artifact in the right-hand viewer.

## Plan of Work

First, add a small navigation model in `src/xs2n/ui/artifacts.py` that can derive curated section entries from the already discovered `ArtifactRecord` list. The curated list should prefer the top-level artifacts that matter most for inspection, such as the digest, run metadata, phases, taxonomy, issues, thread snapshots, and the `llm_calls/` directory when present. Each section entry should keep a human-readable label and the artifact name it opens.

Second, reshape `src/xs2n/ui/app.py` so the middle column becomes its own grouped area with two stacked browsers: sections on top and raw files below. Remove the `Fl_Multiline_Output` run-details widget entirely and let `Fl_Help_View` fill the full right column height. Both middle-column browsers must feed the same artifact-selection path so the viewer stays the single rendering surface.

Third, add or update tests in `tests/test_ui_artifacts.py` and `tests/test_ui_app.py`. The artifact tests should lock the curated section labels and artifact targets. The app tests should cover the non-widget selection behavior that keeps section clicks and raw-file clicks consistent.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, the intended implementation and validation flow is:

    uv run pytest tests/test_ui_artifacts.py tests/test_ui_app.py
    uv run pytest tests/test_ui_viewer.py
    python -m py_compile src/xs2n/ui/app.py src/xs2n/ui/artifacts.py tests/test_ui_app.py tests/test_ui_artifacts.py

If the FLTK runtime is available locally and an interactive check is helpful, also run:

    uv run python - <<'PY'
    from pathlib import Path
    from xs2n.ui.app import ArtifactBrowserWindow
    browser = ArtifactBrowserWindow(data_dir=Path("data"))
    print({'runs': len(browser.runs), 'sections': len(browser.sections), 'selected': browser.selected_artifact_name})
    browser.close_browser()
    PY

Then open a real run, confirm the center column now has two stacked panes, and verify that choosing “Run metadata” from the top pane and `run.json` from the bottom pane both render the same JSON in the viewer.

## Validation and Acceptance

Acceptance is behavioral:

1. The UI no longer shows a separate `Run Details` pane or the floating `Run Details` label.
2. The center column shows curated sections above raw files.
3. Selecting either navigation surface opens the matching artifact in the same right-hand viewer.
4. Focused pytest coverage passes for the navigation model and app selection behavior.

Observed validation:

1. Passed: `uv run pytest tests/test_ui_app.py tests/test_ui_artifacts.py tests/test_ui_viewer.py tests/test_ui_run_arguments.py` -> `17 passed`.
2. Passed: `python -m py_compile src/xs2n/ui/app.py src/xs2n/ui/artifacts.py tests/test_ui_app.py tests/test_ui_artifacts.py`.
3. Passed: `ArtifactBrowserWindow(data_dir=Path("data"))` initialized successfully and reported `{'runs': 12, 'sections': 11, 'selected': 'digest.md'}`.

## Idempotence and Recovery

This milestone is UI-only and read-only over run artifacts. Re-running the tests is safe. Re-opening the GUI is safe. If the layout change regresses selection behavior, the safe rollback is to restore the previous single-browser middle column and keep the new tests as the guardrails that must be satisfied before retrying the refactor.

## Artifacts and Notes

Key files expected to change in this milestone:

- `docs/codex/execplans/ui-artifact-browser-navigation-refine.md`
- `src/xs2n/ui/app.py`
- `src/xs2n/ui/artifacts.py`
- `tests/test_ui_app.py`
- `tests/test_ui_artifacts.py`
- `docs/codex/autolearning.md`

## Interfaces and Dependencies

At the end of this milestone, `src/xs2n/ui/artifacts.py` should expose a stable helper that derives curated section records from artifact records. The exact dataclass and helper names may evolve during implementation, but the interface must preserve one invariant: both curated sections and raw files resolve to an existing `ArtifactRecord.name` so `src/xs2n/ui/app.py` can keep one viewer-selection path.

Revision note (2026-03-16): Created this ExecPlan to capture the follow-up navigation refinement that removes the dedicated run-details pane and replaces the single artifact list with curated sections plus raw files.

Revision note (2026-03-16): Updated the living sections after implementation to record the finished section-navigation model, the removal of the run-details pane, and the focused validation results.
