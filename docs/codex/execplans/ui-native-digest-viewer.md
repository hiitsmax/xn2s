# UI Native Digest Viewer

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `/Users/mx/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the CLI and the desktop UI stop sharing the same digest presentation path. `xs2n report html` goes back to producing one simple Windows-classic HTML export that is safe to open in a browser, while `xs2n ui` treats `digest.html` as a semantic digest artifact and renders a native right-pane viewer from the saved JSON files. The left run list and middle navigation panes stay unchanged; the right pane becomes a real digest browser with overview, thread/source detail, back navigation, and `Open on X`.

The observable result is: run `uv run xs2n ui`, select a run, click `digest.html`, and the right pane shows a native digest browser instead of a file preview. The focus button still expands that viewer. Separately, run `uv run xs2n report html --run-dir ...` and the generated `digest.html` is again a lightweight export rather than a UI-specific surrogate.

## Progress

- [x] (2026-03-19 20:16Z) Reproduced and re-measured the regression: `Fl_Help_View.value(...)` is again the blocking point when applying the rebuilt digest preview HTML.
- [x] (2026-03-19 20:18Z) Compared the current rebuilt digest preview with the pre-regression version and confirmed the new markup reintroduced massive nested-table complexity.
- [x] (2026-03-19 20:22Z) Locked the new product direction with the user: keep the 3-column shell, keep focus mode, move digest interaction into a native right-pane viewer, and keep CLI HTML simple.
- [x] (2026-03-19 20:31Z) Added failing tests for native digest viewer activation, digest-view navigation, and simple CLI digest HTML.
- [x] (2026-03-19 20:37Z) Implemented the native digest viewer modules and app-level viewer switching.
- [x] (2026-03-19 20:39Z) Simplified the CLI/export digest HTML renderer and removed digest-specific HTML preview logic from the generic file viewer path.
- [x] (2026-03-19 20:43Z) Ran focused verification plus a live callback timing probe and confirmed the digest selection path now stays fast.
- [ ] Update docs/autolearning and create the final atomic commit.

## Surprises & Discoveries

- Observation: the same run (`data/report_runs/20260318T225654Z`) that applied in about `114.4 ms` with the simpler digest preview now stalls for more than 15 seconds with the current rebuilt markup.
  Evidence: a live FLTK probe against the current code never returned within the 15-second polling window, while the pre-regression renderer from commit `70d0700` completed in `114.4 ms`.
- Observation: the current rebuilt digest preview is much larger and structurally more complex than the version that fixed the morning freeze.
  Evidence: current preview metrics were `343474` chars, `1122` `<table>` tags, and `2023` `<tr>` tags; the earlier simpler preview was `153863` chars, `2` `<table>` tags, and `6` `<tr>` tags.
- Observation: once `digest.html` stopped going through `Fl_Help_View`, selecting it in the real app dropped back to effectively instant callback timing.
  Evidence: live probe on `ArtifactBrowserWindow._apply_selected_artifact_name('digest.html')` for run `20260318T225654Z` reported `{'callback_ms': 5.67, 'selected_artifact': 'digest.html', 'digest_visible': 1}`.

## Decision Log

- Decision: stop using `Fl_Help_View` for digest interaction in the desktop UI.
  Rationale: we now have direct proof that even FLTK-friendly rebuilt HTML regresses as soon as the markup becomes moderately rich, so the robust fix is to stop making `Fl_Help_View` carry the digest UI at all.
  Date/Author: 2026-03-19 / Codex
- Decision: keep the digest browser inside the existing right pane instead of changing the three-column shell.
  Rationale: the user explicitly wants the left and middle panes unchanged and wants focus mode to keep widening the right pane only.
  Date/Author: 2026-03-19 / Codex

## Outcomes & Retrospective

This milestone achieved the intended split. The CLI/export path now produces a simple Windows-classic digest HTML again, while the desktop UI no longer tries to synthesize digest interaction through `Fl_Help_View`. Instead, `digest.html` activates a native right-pane digest browser backed by `run.json`, `issues.json`, and `issue_assignments.json`.

The biggest outcome is that the original regression class disappears by construction. The app no longer depends on large nested digest HTML to present digest interaction, so the right-pane callback stays fast and the left/middle shell plus focus mode remain unchanged.

## Context and Orientation

`src/xs2n/ui/app.py` currently owns the whole FLTK window. It creates the run list on the left, the section/raw-file browsers in the middle, and a single `fltk.Fl_Help_View` on the right. The generic file preview path is routed through `src/xs2n/ui/viewer.py`. Right now that helper still special-cases `digest.html` and rebuilds it into synthetic HTML, which is the path that reintroduced the freeze.

`src/xs2n/ui/saved_digest.py` already knows how to load `run.json`, `issues.json`, and `issue_assignments.json` into typed models. That loader should stay as the shared foundation. The new viewer should be native FLTK, minimal, and split across small files. The CLI HTML path lives in `src/xs2n/agents/digest/steps/render_digest_html.py`; that renderer should become a light export again and should not carry UI-only interaction concerns.

## Plan of Work

First, add failing tests. `tests/test_ui_app_rendering.py` must prove that selecting `digest.html` no longer schedules generic HTML rendering but instead activates a native digest viewer path. A second test must prove that the native viewer can move from overview to one thread/source detail and back without touching `Fl_Help_View`. `tests/test_render_digest_html.py` must prove the CLI/export digest HTML returns a simple Windows-classic document rather than the current magazine-style page.

Second, create a small native digest-viewer stack. Keep the state tiny: one loaded digest snapshot plus a current screen mode (`overview` or one selected thread). Use one coordinator module for the widget container and one helper module for turning saved digest data into simple display rows and labels. Do not add routers, protocols, or a component framework. The widget tree should use standard FLTK controls such as `Fl_Group`, `Fl_Box`, `Fl_Button`, and one list-style widget for the main scrollable content.

Third, update `src/xs2n/ui/app.py` so the right pane has two concrete rendering modes: the existing generic file viewer and the new digest viewer. The app should switch modes based on the selected artifact name and the availability of digest JSON data. Focus mode and resize logic must continue to operate on the whole right pane container rather than caring which viewer is mounted.

Fourth, remove digest-specific HTML rebuilding from `src/xs2n/ui/viewer.py`. Once the app routes `digest.html` to the native viewer, the generic file viewer can go back to treating HTML files generically. That also means the current `digest_preview.py` and `source_preview.py` helpers can be retired or shrunk away if no longer needed.

Finally, simplify `src/xs2n/agents/digest/steps/render_digest_html.py` back to a compact Windows-classic export with minimal structure and normal source links. This output is for browser/file consumption, not for the desktop digest browser.

## Concrete Steps

Work from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Run focused UI + digest-render tests and confirm the new native-viewer expectations fail first.

   `uv run pytest tests/test_render_digest_html.py tests/test_ui_app_rendering.py tests/test_ui_viewer.py -q`

2. Implement the native digest viewer modules and wire the app-level viewer switch.

3. Simplify the CLI/export HTML renderer and remove digest-specific HTML rebuilding from the generic viewer.

4. Re-run the focused tests.

   `uv run pytest tests/test_render_digest_html.py tests/test_ui_app_rendering.py tests/test_ui_viewer.py -q`

5. Run the broader regression set around the app shell and artifact browsing.

   `uv run pytest tests/test_render_digest_html.py tests/test_ui_app.py tests/test_ui_app_rendering.py tests/test_ui_viewer.py tests/test_ui_artifacts.py -q`

Observed results:

   `44 passed, 218 warnings in 0.64s`

Live callback probe:

   `{'callback_ms': 5.67, 'selected_run': '20260318T225654Z', 'selected_artifact': 'digest.html', 'digest_visible': 1}`

## Validation and Acceptance

Acceptance is behavioral:

1. In `xs2n ui`, selecting `digest.html` renders a native digest browser in the right pane instead of pushing rebuilt digest HTML into `Fl_Help_View`.
2. The native digest browser supports overview, opening a thread/source view, going back, and opening X links explicitly.
3. Focus mode still enlarges the right pane and does not care which viewer mode is active.
4. Generic HTML and other artifact files still render through the existing file viewer path.
5. `xs2n report html --run-dir ...` writes one simple Windows-classic export HTML document that is independent of the desktop UI implementation.

## Idempotence and Recovery

The refactor is safe to re-run. Tests are deterministic. If the native viewer wiring regresses, the safe rollback is to restore the prior right-pane `Fl_Help_View` path while keeping the saved-digest loader and focused tests as the reference for the next attempt.

## Artifacts and Notes

Likely touch points:

- `src/xs2n/agents/digest/steps/render_digest_html.py`
- `src/xs2n/ui/app.py`
- `src/xs2n/ui/viewer.py`
- `src/xs2n/ui/saved_digest.py`
- new native viewer modules under `src/xs2n/ui/`
- `tests/test_render_digest_html.py`
- `tests/test_ui_app_rendering.py`
- `tests/test_ui_viewer.py`
- `docs/codex/autolearning.md`

Plan revision note: created this ExecPlan after the user approved the split between simple CLI HTML and a native desktop digest viewer, following a measured regression in the rebuilt `Fl_Help_View` digest preview path.

Plan revision note (2026-03-19 20:43Z): updated the living sections after implementation, including the passing regression suite and the callback timing probe that confirmed `digest.html` no longer blocks the right-pane selection path.

## Interfaces and Dependencies

At the end of this milestone, the app should have one small digest-viewer interface that `src/xs2n/ui/app.py` can drive without knowing the internal widget layout. In plain terms, the right-pane digest viewer must expose methods equivalent to:

    show()
    hide()
    resize(x, y, w, h)
    apply_theme(theme)
    load_run(run_dir)
    show_overview()
    show_thread(thread_id)

The CLI renderer in `src/xs2n/agents/digest/steps/render_digest_html.py` should remain a plain function returning one HTML string and should not depend on any desktop UI modules.
