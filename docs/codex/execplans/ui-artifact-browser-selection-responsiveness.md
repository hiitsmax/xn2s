# UI Artifact Browser Selection Responsiveness

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`. It is intentionally self-contained so a future contributor can understand the responsiveness problem and the chosen fix without replaying prior UI work.

## Purpose / Big Picture

After this change, clicking a curated section or raw file in `xs2n ui` should feel immediate even when the selected artifact is large. The middle-column selection should visibly align right away, and the viewer should update one idle cycle later instead of blocking the click callback before FLTK has a chance to repaint.

The visible proof is:

- clicking a section immediately highlights the matching raw-file row;
- the status bar reports that the artifact is loading before the heavy viewer render completes;
- the final viewer content still appears for the chosen artifact;
- the regression tests lock the deferred-render behavior.

## Progress

- [x] (2026-03-16 18:30Z) Measured the live click path and confirmed the lag came from `Fl_Help_View.value(...)`, not from the section-to-raw-file synchronization.
- [x] (2026-03-16 18:39Z) Queried fresh FLTK Context7 docs for idle-callback guidance and chose to reuse the existing always-on idle hook instead of adding a second ad-hoc callback path.
- [x] (2026-03-16 18:53Z) Implemented deferred artifact rendering, lightweight loading feedback, and idle-drain handling in `src/xs2n/ui/app.py`.
- [x] (2026-03-16 18:57Z) Added focused regression coverage for deferred viewer rendering and last-selection-wins behavior in `tests/test_ui_app.py`, plus viewer-helper coverage in `tests/test_ui_viewer.py`.
- [x] (2026-03-16 19:00Z) Verified the new behavior with focused pytest coverage, `py_compile`, and a live FLTK timing probe that showed the click callback dropping to about `0.05 ms` for `threads.json` while the heavy viewer render remained in the deferred idle step.

## Surprises & Discoveries

- Observation: Python-side HTML generation was not the dominant cost for the laggy clicks.
  Evidence: live timing before the fix showed `_sync_navigation_selection()` at about `0.00-0.01 ms`, `render_artifact_html(...)` at about `4-13 ms` for the largest measured files, and `Fl_Help_View.value(...)` at about `245 ms` for `issue_assignments.json`, `1.50 s` for `filtered_threads.json`, and `13.98 s` for `threads.json`.

- Observation: `ArtifactBrowserWindow` already had a permanent FLTK idle callback for background command completion, which gave us a natural place to defer viewer work without inventing another event pump.
  Evidence: `src/xs2n/ui/app.py` registers `fltk.Fl.add_idle(...)` during initialization and drains command results there on every idle cycle.

- Observation: the deferred-render split materially changed the responsiveness profile even though the expensive viewer parse still exists.
  Evidence: after the fix, the same live timing probe reported `{'callback_ms': 0.05, 'idle_ms': 14057.56, 'selected': 'threads.json'}` for run `20260316T000914Z`, proving the cost moved out of the click callback.

## Decision Log

- Decision: defer only the heavy artifact-view render, not the selection synchronization.
  Rationale: the user complaint was specifically about the raw-files list aligning late; keeping selection updates inside the click callback preserves immediate visual feedback while moving the expensive viewer work off the critical path.
  Date/Author: 2026-03-16 / Codex

- Decision: reuse the existing long-lived idle callback instead of adding a second `Fl.add_idle(...)` registration that would need its own lifecycle bookkeeping.
  Rationale: one idle-drain loop is easier to reason about, avoids callback-registration drift, and matches the real job more honestly once the UI has both command-result work and deferred viewer work.
  Date/Author: 2026-03-16 / Codex

## Outcomes & Retrospective

This milestone is complete. The browser now treats “update selection” and “render viewer” as separate jobs. Section and raw-file clicks synchronize immediately, the viewer shows a lightweight loading state, and the existing FLTK idle loop performs the heavy artifact render one beat later. Focused regression tests passed, and the live timing probe confirmed that the selection callback is now effectively instantaneous even for the largest `threads.json` artifact measured.

## Context and Orientation

The artifact browser window lives in `src/xs2n/ui/app.py`. It builds a three-pane FLTK desktop UI: runs on the left, navigation in the middle, and a `Fl_Help_View` viewer on the right. The middle pane has two `Fl_Hold_Browser` widgets: `sections_browser` for curated shortcuts and `raw_files_browser` for the full artifact list.

An “artifact” in this repository is a file or directory inside one run folder such as `run.json`, `digest.md`, or `llm_calls/001_trace.json`. Selecting an artifact eventually calls `render_artifact_html(...)` from `src/xs2n/ui/viewer.py`, then pushes the resulting HTML string into `Fl_Help_View.value(...)`.

The important runtime detail is that FLTK does not repaint widgets in the middle of a callback. Before this change, a section click updated the browser selections and immediately called `Fl_Help_View.value(...)` in the same callback path. For large JSON snapshots, that meant the raw-files selection could not visibly repaint until the heavy viewer parse finished.

## Plan of Work

First, keep the selection path in `src/xs2n/ui/app.py` but split it into two phases. The click callback should still resolve the artifact name, update `selected_artifact_name`, and synchronize both browsers immediately. Instead of rendering the artifact inline, it should queue the artifact name for the next idle cycle and show a lightweight loading view so the user sees that the click was accepted.

Second, rename the old command-only idle callback so it honestly describes its broader responsibility. That idle handler should continue to drain background command results, then render the currently queued artifact if one exists and still matches the active selection.

Third, add focused tests in `tests/test_ui_app.py` for two behaviors: deferred rendering after selection and “last selection wins” if a second click happens before the idle render runs. Add a small viewer-level test in `tests/test_ui_viewer.py` for the lightweight loading HTML helper so the loading state stays visually coherent with the rest of the viewer.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, implement and validate with:

    uv run pytest tests/test_ui_app.py tests/test_ui_viewer.py
    uv run python - <<'PY'
    import time
    from pathlib import Path
    from xs2n.ui.app import ArtifactBrowserWindow
    browser = ArtifactBrowserWindow(data_dir=Path("data"))
    run = next(r for r in browser.runs if r.run_id == "20260316T000914Z")
    browser._apply_selected_run(next(i for i, item in enumerate(browser.runs) if item.run_id == run.run_id))
    start = time.perf_counter()
    browser._apply_selected_artifact_name("threads.json")
    callback_ms = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    browser._drain_pending_viewer_render()
    idle_ms = (time.perf_counter() - start) * 1000
    print({"callback_ms": round(callback_ms, 2), "idle_ms": round(idle_ms, 2), "selected": browser.selected_artifact_name})
    browser.close_browser()
    PY

Success means the pytest command passes and the timing probe shows a fast selection callback plus a slower deferred render step.

## Validation and Acceptance

Acceptance is behavioral:

1. Clicking a section updates both browser selections before the heavy viewer render runs.
2. The status bar shows `Loading <artifact>...` immediately after selection and `Viewing <artifact>.` after the idle render finishes.
3. The focused tests pass for deferred rendering and for queued-selection replacement.
4. The live timing probe shows `_apply_selected_artifact_name(...)` finishing quickly while `_drain_pending_viewer_render()` absorbs the expensive work.

Observed validation:

1. Passed: `uv run pytest tests/test_ui_app.py tests/test_ui_viewer.py` -> `15 passed`.
2. Passed: `uv run pytest tests/test_ui_app.py tests/test_ui_artifacts.py tests/test_ui_viewer.py tests/test_ui_run_arguments.py` -> `24 passed`.
3. Passed: `python -m py_compile src/xs2n/ui/app.py src/xs2n/ui/viewer.py tests/test_ui_app.py tests/test_ui_viewer.py`.
4. Passed: live FLTK timing probe for run `20260316T000914Z` -> `{'callback_ms': 0.05, 'idle_ms': 14057.56, 'selected': 'threads.json'}`.

## Idempotence and Recovery

This work only changes UI control flow. Re-running the tests is safe. If the deferred-render path regresses, the safe rollback is to restore the old synchronous render in `src/xs2n/ui/app.py` and remove the new pending-render state fields and tests together.

## Artifacts and Notes

Expected files for this milestone:

- `docs/codex/execplans/ui-artifact-browser-selection-responsiveness.md`
- `src/xs2n/ui/app.py`
- `src/xs2n/ui/viewer.py`
- `tests/test_ui_app.py`
- `tests/test_ui_viewer.py`
- `docs/codex/autolearning.md`

## Interfaces and Dependencies

At the end of this milestone, `src/xs2n/ui/app.py` should expose a clear separation between selection synchronization and viewer rendering. The window object must keep:

- the currently selected artifact name;
- the pending artifact name waiting for the next idle render;
- the most recently rendered artifact name for viewer-state bookkeeping.

`src/xs2n/ui/viewer.py` should also expose a lightweight helper for rendering the loading state of an artifact so the app code does not hand-roll viewer HTML.

Revision note (2026-03-16): Created this ExecPlan after measuring a real FLTK selection lag and choosing an idle-deferred viewer render as the fix.

Revision note (2026-03-16): Updated the living sections after implementation to record the deferred-render design, focused test coverage, and the post-fix timing probe.
