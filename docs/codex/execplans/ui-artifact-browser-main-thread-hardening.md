# UI Artifact Browser Main-Thread Hardening

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`. It is intentionally self-contained so a future contributor can implement or resume the work from this file alone.

## Purpose / Big Picture

After this change, `uv run xs2n ui` should stay responsive even when the newest run contains large JSON artifacts and a very large `llm_calls/` directory. The user should still see immediate selection feedback, but the browser must stop freezing for many seconds while large previews are built and handed to `Fl_Help_View`.

The visible proof is:

- selecting a large artifact shows loading feedback immediately;
- the final preview appears without multi-second UI freezes;
- large `llm_calls/` directories no longer explode the raw-files browser into thousands of rows;
- focused tests lock the new background-render and large-artifact behavior.

## Progress

- [x] (2026-03-18 18:07Z) Audited the current UI package, ran focused UI tests, and measured severe viewer freezes on large JSON artifacts.
- [x] (2026-03-18 18:09Z) Queried fresh FLTK docs via Context7 and confirmed the recommended threading pattern is worker-thread computation plus `Fl::awake(...)` for main-thread GUI handoff.
- [x] (2026-03-18 18:19Z) Added failing tests for large-artifact preview behavior and render-result handoff in `tests/test_ui_artifacts.py`, `tests/test_ui_viewer.py`, and `tests/test_ui_app_rendering.py`.
- [x] (2026-03-18 18:24Z) Changed artifact discovery so nested directories stay collapsed in the raw-files browser instead of expanding into thousands of rows.
- [x] (2026-03-18 18:27Z) Added size-aware preview generation so large JSON, text, and directory previews are bounded before they reach the viewer.
- [x] (2026-03-18 18:31Z) Moved preview generation off the FLTK main thread and added a worker-result queue plus `fltk.Fl.awake()` wakeups before the viewer applies ready results.
- [x] (2026-03-18 18:34Z) Applied the focused run-list multi-select optimization in `src/xs2n/ui/run_list_browser.py` and locked it with targeted tests.
- [ ] Re-run focused UI tests and live timing probes, then record the new measurements in this plan and `docs/codex/autolearning.md` (completed: `artifacts/viewer/run_list_browser` tests and fresh timing probes; remaining: old `tests/test_ui_app.py` is blocked by concurrent missing-schema / syntax-error work outside this task).

## Surprises & Discoveries

- Observation: the largest current freezes come from the viewer path, not from run-list column layout.
  Evidence: local timing probe on 2026-03-18 measured `_drain_pending_viewer_render()` at about `21.85 s` for `filtered_threads.json`, `19.54 s` for `categorized_threads.json`, and `14.43 s` for `threads.json`.

- Observation: the newest local run is dominated by nested LLM trace files rather than top-level artifacts.
  Evidence: `list_run_artifacts(...)` on run `20260316T003444Z` reported `1211` artifacts, including `1200` `llm_calls/*` children, and took about `510.45 ms`.

- Observation: Python-side HTML generation is noticeable but still much smaller than the full UI-side freeze.
  Evidence: `render_artifact_html(filtered_threads.json)` measured about `111.67 ms`, while the full UI-side render path measured about `21853.67 ms`.

- Observation: collapsing nested directories was enough to remove the biggest run-selection hitch without inventing a directory browser.
  Evidence: `list_run_artifacts(...)` on the same run dropped from `1211` artifacts / `510.45 ms` to `11` artifacts / `1.2 ms` once `llm_calls/` stopped expanding into individual child rows.

- Observation: the bounded-preview strategy removed the multi-second freeze even before any deeper viewer redesign.
  Evidence: after the change, the same local artifacts rendered in about `157.85 ms`, `130.44 ms`, `146.11 ms`, `507.62 ms`, and `484.41 ms` respectively instead of `7-22 s`.

- Observation: verification on the legacy `tests/test_ui_app.py` target is currently blocked by unrelated concurrent work in the tree.
  Evidence: collecting `tests/test_ui_app.py` fails because it imports `xs2n.schemas.auth`, and a separate import path also trips on a pre-existing `SyntaxError` in `src/xs2n/cli/report.py`.

## Decision Log

- Decision: keep the current FLTK-native viewer stack instead of replacing `Fl_Help_View`.
  Rationale: the real issue is that we feed it far too much content on the UI thread; the smaller and safer change is to bound preview size and move preview computation to a worker thread.
  Date/Author: 2026-03-18 / Codex

- Decision: collapse large nested directories in artifact discovery instead of eagerly expanding every child file into the raw-files browser.
  Rationale: the current data proves that `llm_calls/` dominates artifact count; collapsing it removes hundreds or thousands of mostly low-value rows from the hot path while preserving directory inspection through the viewer.
  Date/Author: 2026-03-18 / Codex

- Decision: use worker-thread preview generation plus `fltk.Fl.awake()` rather than relying only on the existing idle callback.
  Rationale: FLTK docs recommend `Fl::awake(...)` for worker-to-main-thread wakeups. The existing idle callback can still drain results, but the heavy preview generation should no longer happen on the main loop.
  Date/Author: 2026-03-18 / Codex

## Outcomes & Retrospective

This milestone is functionally complete for the artifact-browser performance path. The prior milestone solved “selection feedback is delayed” by deferring render work to the next idle cycle, but it did not solve the larger architectural issue that expensive preview work still ran on the FLTK main thread. This change hardens that path by reducing preview volume, collapsing nested trace directories, and moving preview generation out of the event loop. The only remaining gap is verification on an older `tests/test_ui_app.py` file that is currently blocked by unrelated concurrent auth/report-runtime changes already present in the workspace.

## Context and Orientation

The desktop UI entrypoint is `src/xs2n/ui/app.py`. `ArtifactBrowserWindow` builds a three-pane FLTK window and currently owns both selection state and preview rendering. When the user selects a run, `_apply_selected_run(...)` rebuilds the middle-pane navigation by calling `list_run_artifacts(...)` and `list_artifact_sections(...)`. When the user selects an artifact, `_apply_selected_artifact_name(...)` queues a pending render and `_drain_pending_viewer_render(...)` currently builds the full preview HTML synchronously on the FLTK thread.

The artifact discovery code lives in `src/xs2n/ui/artifacts.py`. Today `list_run_artifacts(...)` expands one nested directory level, which means `llm_calls/` becomes one browser row per trace file. `load_artifact_text(...)` reads the full file and pretty-prints full JSON payloads before the viewer turns them into HTML.

The HTML preview helpers live in `src/xs2n/ui/viewer.py`. `render_artifact_html(...)` currently reads the entire artifact text, optionally renders Markdown, and wraps the entire result into HTML for `Fl_Help_View`.

The run-list multi-select behavior lives in `src/xs2n/ui/run_list_browser.py`. It is not the primary bottleneck, but it still does avoidable list-wide work on every mouse release and should be kept in mind while touching responsiveness code.

In this repository, a “preview” is the read-only content shown in the right-hand viewer. A “collapsed directory” means the raw-files browser shows the directory row itself rather than one row per nested child file.

## Plan of Work

First, add the failing tests. `tests/test_ui_artifacts.py` must prove that large nested directories stay collapsed in the raw-files browser and that large files are shown as bounded previews rather than full pretty-printed payloads. `tests/test_ui_viewer.py` must prove that preview metadata clearly explains truncation. A dedicated rendering-path test file should prove that selecting an artifact starts asynchronous preview work and that only completed worker results update the viewer, without depending on unrelated in-flight auth/report-runtime test fixtures.

Second, change `src/xs2n/ui/artifacts.py` so `list_run_artifacts(...)` no longer expands every nested child file into the raw-files browser. Keep top-level files and top-level directories visible, but let directory contents stay inside the directory preview instead of multiplying browser rows. In the same module, replace the unbounded `load_artifact_text(...)` behavior with a preview-oriented loader that can cap directory entries, cap text bytes, and skip expensive full JSON pretty-printing for large files.

Third, update `src/xs2n/ui/viewer.py` so the preview helpers can render bounded previews cleanly. This includes showing truncation metadata and avoiding extra full-document work when the source preview is already intentionally limited.

Fourth, update `src/xs2n/ui/app.py` so artifact preview generation happens in a worker thread. The worker thread should build the preview HTML, push a ready result into a queue, and call `fltk.Fl.awake()` so the main loop wakes promptly. The main thread must only apply ready results, keep “last selection wins” semantics, and avoid touching FLTK widgets from the worker.

Fifth, make the small `src/xs2n/ui/run_list_browser.py` optimization so modifier-based multi-select only snapshots the previous selection when that state is actually needed.

Finally, rerun the focused tests and the live timing probe. Record the new timings both here and in `docs/codex/autolearning.md`.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, implement and validate with:

    uv run pytest tests/test_ui_artifacts.py tests/test_ui_viewer.py tests/test_ui_app_rendering.py tests/test_ui_run_list_browser.py

Then run a live timing probe:

    uv run python - <<'PY'
    from pathlib import Path
    from time import perf_counter
    from xs2n.ui.app import ArtifactBrowserWindow

    browser = ArtifactBrowserWindow(data_dir=Path("data"))
    artifacts = [
        artifact
        for artifact in browser.artifacts
        if artifact.path.exists() and artifact.path.is_file()
    ]
    artifacts.sort(key=lambda artifact: artifact.path.stat().st_size, reverse=True)
    for artifact in artifacts[:5]:
        start = perf_counter()
        browser._apply_selected_artifact_name(artifact.name)
        callback_ms = (perf_counter() - start) * 1000
        while browser.rendered_viewer_artifact_name != artifact.name:
            browser._drain_idle_work()
        idle_ms = (perf_counter() - start) * 1000
        print(
            {
                "artifact": artifact.name,
                "size_kb": round(artifact.path.stat().st_size / 1024, 1),
                "callback_ms": round(callback_ms, 2),
                "until_rendered_ms": round(idle_ms, 2),
            }
        )
    browser.close_browser()
    PY

Success means the focused pytest command passes and the timing probe no longer shows multi-second freezes for the same artifacts. If the broader `tests/test_ui_app.py` target is still blocked by unrelated concurrent work, document the blocker explicitly and rely on the isolated rendering-path tests plus the live timing probe for this milestone.

## Validation and Acceptance

Acceptance is behavioral:

1. Selecting large JSON artifacts still shows immediate loading feedback.
2. The final preview is bounded and informative rather than attempting to dump the full file into `Fl_Help_View`.
3. Large `llm_calls/` directories no longer expand into one raw-files row per child file.
4. Worker-thread preview generation never touches FLTK widgets directly.
5. The focused UI tests for `artifacts`, `viewer`, isolated app rendering, and `run_list_browser` pass.
6. The live timing probe shows no multi-second viewer freezes for the same local artifacts that previously froze for 7-22 seconds.

## Idempotence and Recovery

This work is safe to rerun. The tests are deterministic and the timing probe is read-only over `data/`. If the worker-thread path regresses, the safest rollback is to keep the size-aware preview logic, restore synchronous preview application, and then reintroduce the worker-thread handoff in a narrower patch.

## Artifacts and Notes

Measured baseline before implementation:

    {'scan_runs_ms': 13.57, 'run_count': 2}
    {'list_run_artifacts_ms': 510.45, 'artifact_count': 1211, 'run_id': '20260316T003444Z'}
    {'artifact': 'filtered_threads.json', 'size_kb': 908.2, 'callback_ms': 0.29, 'idle_render_ms': 21853.67}
    {'artifact': 'categorized_threads.json', 'size_kb': 798.5, 'callback_ms': 2.01, 'idle_render_ms': 19536.04}
    {'artifact': 'threads.json', 'size_kb': 531.7, 'callback_ms': 0.83, 'idle_render_ms': 14433.06}
    {'artifact': 'issue_assignments.json', 'size_kb': 348.2, 'callback_ms': 0.90, 'idle_render_ms': 8949.86}
    {'artifact': 'processed_threads.json', 'size_kb': 280.7, 'callback_ms': 0.61, 'idle_render_ms': 7161.04}

Measured results after implementation:

    {'run_id': '20260316T003444Z', 'artifact_count': 11, 'list_run_artifacts_ms': 1.2}
    {'artifact': 'filtered_threads.json', 'size_kb': 908.2, 'callback_ms': 0.09, 'until_rendered_ms': 157.85}
    {'artifact': 'categorized_threads.json', 'size_kb': 798.5, 'callback_ms': 0.15, 'until_rendered_ms': 130.44}
    {'artifact': 'threads.json', 'size_kb': 531.7, 'callback_ms': 0.15, 'until_rendered_ms': 146.11}
    {'artifact': 'issue_assignments.json', 'size_kb': 348.2, 'callback_ms': 0.17, 'until_rendered_ms': 507.62}
    {'artifact': 'processed_threads.json', 'size_kb': 280.7, 'callback_ms': 0.16, 'until_rendered_ms': 484.41}

Focused verification:

    uv run pytest tests/test_ui_artifacts.py tests/test_ui_viewer.py -q
    12 passed in 0.04s

    uv run pytest tests/test_ui_run_list_browser.py -q
    6 passed in 0.01s

## Interfaces and Dependencies

At the end of this milestone:

- `src/xs2n/ui/artifacts.py` must expose bounded preview loading behavior for files and directories.
- `src/xs2n/ui/viewer.py` must be able to render truncated previews without pretending they are full documents.
- `src/xs2n/ui/app.py` must own a worker-to-main-thread preview handoff, using `fltk.Fl.awake()` to wake the main loop after background preview computation.
- `src/xs2n/ui/run_list_browser.py` should avoid unnecessary full-list selection snapshots on plain clicks.

Revision note (2026-03-18): Created this ExecPlan after a fresh UI performance audit showed that the previous idle-deferred fix still left expensive artifact preview work on the FLTK main thread.

Revision note (2026-03-18): Updated the living sections after implementation to record the collapsed-directory design, bounded-preview behavior, fresh timing improvements, and the unrelated workspace blockers that currently prevent running the older monolithic `tests/test_ui_app.py` target.
