# UI Performance Audit (2026-03-18)

## Scope

Audit of the native desktop UI package under `src/xs2n/ui/` to understand whether the current interaction patterns are efficient and aligned with best practices, with special attention to the stutter seen while browsing run artifacts.

## What Was Checked

- Source review of:
  - `src/xs2n/ui/app.py`
  - `src/xs2n/ui/artifacts.py`
  - `src/xs2n/ui/viewer.py`
  - `src/xs2n/ui/run_list.py`
  - `src/xs2n/ui/run_list_browser.py`
- Parallel sub-reviews on:
  - run-list interaction patterns
  - artifact/viewer rendering path
  - app lifecycle and main-thread behavior
- Fresh FLTK docs via Context7 for event-loop and threading guidance
- Focused UI test run
- Live timing probes against the local `data/` folder

## Verified Facts

- Focused UI tests passed:
  - `uv run pytest tests/test_ui_app.py tests/test_ui_artifacts.py tests/test_ui_run_list.py tests/test_ui_viewer.py tests/test_ui_run_arguments.py tests/test_ui_run_preferences.py tests/test_ui_run_list_browser.py`
- Current local data shape:
  - newest run has `1211` visible artifacts
  - `1200` of them are individual `llm_calls/*` files
- Measured timings on the current local data:
  - `scan_runs(data)` -> about `13.57 ms`
  - `list_run_artifacts(run)` for the newest run -> about `510.45 ms`
  - `render_artifact_html(filtered_threads.json)` -> about `111.67 ms`
  - full UI-side idle render after selecting artifacts:
    - `filtered_threads.json` (`908.2 KB`) -> `21853.67 ms`
    - `categorized_threads.json` (`798.5 KB`) -> `19536.04 ms`
    - `threads.json` (`531.7 KB`) -> `14433.06 ms`
    - `issue_assignments.json` (`348.2 KB`) -> `8949.86 ms`
    - `processed_threads.json` (`280.7 KB`) -> `7161.04 ms`

## Main Findings

### 1. Heavy viewer work still runs on the FLTK main thread

The current pattern defers rendering to the next idle cycle, but it does not offload it to a background worker. That means the UI still freezes while the pending artifact is actually rendered.

Relevant code:
- `src/xs2n/ui/app.py` queues the render in `_apply_selected_artifact_name(...)`
- `src/xs2n/ui/app.py` executes it in `_drain_pending_viewer_render(...)`
- `src/xs2n/ui/viewer.py` reads, transforms, and wraps the entire artifact into HTML

Why this matters:
- FLTK idle callbacks still run on the main event loop
- FLTK docs recommend using worker threads plus `Fl::awake(...)` for cross-thread GUI handoff
- current behavior improves click acknowledgment, but not freeze duration

### 2. Large JSON artifacts are rendered in the most expensive possible way

The JSON path currently:
1. reads the full file
2. parses the full JSON
3. pretty-prints the full JSON
4. escapes the full text into HTML
5. hands a very large HTML string to `Fl_Help_View`

This is correct but not efficient for trace files and thread snapshots.

Relevant code:
- `src/xs2n/ui/artifacts.py` -> `load_artifact_text(...)`
- `src/xs2n/ui/viewer.py` -> `render_artifact_html(...)`
- `src/xs2n/ui/viewer.py` -> `_render_plain_text_block(...)`

### 3. Run selection also does noticeable synchronous filesystem work

Selecting a run rebuilds artifact navigation on the UI thread:
- scans run entries
- reparses phase metadata
- expands the `llm_calls/` directory into individual rows

That is not catastrophic, but on the current local run it already costs about half a second before viewer rendering is even considered.

Relevant code:
- `src/xs2n/ui/app.py` -> `_apply_selected_run(...)`
- `src/xs2n/ui/artifacts.py` -> `list_run_artifacts(...)`
- `src/xs2n/ui/artifacts.py` -> `_artifact_phase_map(...)`

### 4. The run list itself is mostly fine, but some interaction paths are O(n)

The width/layout logic is reasonable and memoized. The weaker part is selection bookkeeping for multi-select, which scans rows and rebuilds selections on release. With many rows, that can add friction, though it is not the primary cause of the freezes measured above.

Relevant code:
- `src/xs2n/ui/app.py` -> `_sync_run_list_layout(...)`
- `src/xs2n/ui/run_list_browser.py` -> `selected_indexes(...)`
- `src/xs2n/ui/run_list_browser.py` -> `set_selection(...)`

## What Looks Good

- The code is generally readable and split by responsibility in a healthy way.
- The deferred-render change was directionally correct: click callbacks stay fast and “last selection wins” avoids wasted stale renders.
- The resize/layout math is not the main problem.
- Test coverage is solid for functional behavior, but it is not yet performance-oriented.

## Best-Practice Verdict

Partially aligned with best practice, but not efficient enough for large artifact sets.

More specifically:
- good:
  - clear orchestration
  - good UI state separation
  - sensible coalescing of pending renders
- not good enough:
  - expensive artifact rendering still happens on the UI thread
  - large JSON is fully materialized every time
  - the artifact navigator eagerly expands very large trace directories

## Recommended Next Steps

1. Move artifact load/transform work to a worker thread and return only the final GUI update to the main thread via FLTK wakeup.
2. Add size-aware rendering rules for big JSON:
   - preview/truncate by default
   - optionally lazy-load full content on demand
   - skip pretty-print for very large files unless explicitly requested
3. Stop eagerly expanding all `llm_calls/*` entries into the main raw-files list for large runs.
4. Add one performance regression check around large-artifact rendering and one around large artifact lists.

## Bottom Line

The stutter is real and expected from the current architecture. The main culprit is not the run-list layout code; it is the viewer pipeline and the fact that heavy render work still executes inside the FLTK event loop.
