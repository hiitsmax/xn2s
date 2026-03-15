# UI Artifact Browser

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `~/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, a user can run `uv run xs2n ui` and inspect digest-run artifacts in a small native desktop window instead of manually opening JSON and Markdown files in Finder or a text editor. The browser stays aligned with the existing CLI because it reads the artifact folders the pipeline already writes and shells out to the same CLI commands for `report digest` and `report latest`.

The visible proof is:

- `xs2n ui` exists as a top-level command.
- the desktop window scans every `data/report_runs*` root and tolerates old, partial, and newer traced runs.
- selecting a run shows its artifacts and renders the selected file content in a read-only viewer.
- the optional GUI install path is documented, including the macOS `brew install fltk` runtime caveat.

## Progress

- [x] (2026-03-15 23:05Z) Audited the current CLI entrypoints, run artifact layouts, and test style to identify the cleanest integration path.
- [x] (2026-03-15 23:09Z) Pulled fresh FLTK guidance through Context7 and inspected the current `pyfltk` wheel wrapper to confirm the real widget names and callback entry points.
- [x] (2026-03-15 23:12Z) Confirmed the current `pyfltk` Python wheel imports only when the native FLTK shared library is present on macOS.
- [x] (2026-03-15 23:18Z) Implemented the read-only run and artifact scanner in `src/xs2n/ui/artifacts.py`, including support for multiple `report_runs*` roots and partial runs.
- [x] (2026-03-15 23:20Z) Implemented the PyFLTK desktop window in `src/xs2n/ui/app.py` with three panes, refresh controls, and background CLI-driven run actions.
- [x] (2026-03-15 23:21Z) Added the thin `xs2n ui` command in `src/xs2n/cli/ui.py`, wired it into `src/xs2n/cli/cli.py`, and kept the GUI dependency optional in `pyproject.toml`.
- [x] (2026-03-15 23:22Z) Added focused tests in `tests/test_ui_cli.py` and `tests/test_ui_artifacts.py`.
- [x] (2026-03-15 23:24Z) Updated `README.md` and `docs/codex/autolearning.md` with install and usage notes.
- [x] (2026-03-15 23:26Z) Ran focused tests, the full pytest suite, a real pyFLTK import/bootstrap smoke, and an end-to-end `uv run xs2n ui` launch check.
- [x] (2026-03-15 23:48Z) Upgraded the viewer pane from raw text-only output to FLTK-native HTML rendering for Markdown artifacts, while keeping JSON/log inspection preformatted and read-only.
- [x] (2026-03-16 00:33Z) Added a dedicated `src/xs2n/ui/macos/` helper that renames the native macOS app menu to `xn2s`, suppresses FLTK's default Window menu, and leaves only `About xn2s` and `Quit xn2s` in the system menu bar.

## Surprises & Discoveries

- Observation: `pyfltk` on this macOS machine needs the system FLTK library outside the Python wheel.
  Evidence: importing the wheel initially raised `ImportError: Library not loaded: /opt/homebrew/opt/fltk/lib/libfltk_images.1.4.dylib`, and the import only succeeded after `brew install fltk`.

- Observation: the current repository contains multiple generations of run folders, from partial folders with only `threads.json` to newer traced folders with `run.json`, `phases.json`, `taxonomy.json`, and `llm_calls/`.
  Evidence: live inspection of `data/report_runs*` showed old folders such as `data/report_runs/20260307T173044Z` and newer folders such as `data/report_runs_last24h_limit100/20260315T203138Z`.

- Observation: the simplest resilient browsing model is filesystem-first, not metadata-first.
  Evidence: older runs may not have `run.json`, and interrupted runs may reference files in metadata that do not exist yet, while the actual directory contents always tell the truth about what is inspectable.

- Observation: Typer defaults can still leak `OptionInfo` objects when command functions are called directly in tests.
  Evidence: `tests/test_ui_cli.py::test_ui_command_uses_default_data_dir` initially failed until `src/xs2n/cli/ui.py` normalized `OptionInfo` to real defaults.

- Observation: on macOS, FLTK can suppress its automatic Window menu, but the visible application name in the native menu bar still belongs to Cocoa rather than to the FLTK widget tree.
  Evidence: fresh FLTK docs exposed `Fl_Sys_Menu_Bar.window_menu_style(no_window_menu)` for the Window menu, while Apple docs and live runtime testing showed the app label followed the process name and needed a separate AppKit-level override.

## Decision Log

- Decision: implement the desktop UI in `pyfltk` even though Qt would be the safer default toolkit.
  Rationale: the user explicitly wanted a NeXT/OpenStep-like 90s desktop feel, and the first version is narrow enough that `pyfltk` is a credible fit.
  Date/Author: 2026-03-15 / Codex

- Decision: keep the GUI dependency optional and lazily imported.
  Rationale: this repository remains CLI-first, and the GUI currently needs an extra native FLTK install on macOS. Headless users and cron jobs should not pay that cost.
  Date/Author: 2026-03-15 / Codex

- Decision: scan every directory under `data/` whose name starts with `report_runs`.
  Rationale: the repository already stores real runs in `report_runs`, `report_runs_fake`, `report_runs_subset`, `report_runs_last24h`, and `report_runs_last24h_limit100`.
  Date/Author: 2026-03-15 / Codex

- Decision: keep the GUI file-oriented and lightweight in version one.
  Rationale: the browser should stay close to the artifacts on disk and avoid a heavier document system, while still rendering the highest-value artifact type, `digest.md`, in a friendlier way.
  Date/Author: 2026-03-15 / Codex

- Decision: render `.md` artifacts through `Fl_Help_View` using a lightweight Markdown-to-HTML conversion instead of embedding a browser widget.
  Rationale: the GUI already depends on FLTK, and `Fl_Help_View` gives formatted digest rendering without adding Electron-style runtime weight or a second rendering stack.
  Date/Author: 2026-03-15 / Codex

- Decision: keep the macOS native-menu override in its own `ui/macos/` helper and use a tiny Cocoa bridge instead of adding PyObjC as a new dependency.
  Rationale: FLTK handles most of the desktop UI, but exact macOS menu-bar control belongs to AppKit. A small isolated bridge keeps the dependency footprint low and avoids polluting `app.py` with platform-specific Objective-C details.
  Date/Author: 2026-03-16 / Codex

- Decision: use multiple focused subagents during implementation.
  Rationale: the user explicitly asked to avoid context rot. In this task, that meant keeping the CLI integration, artifact-model audit, tests, and docs as separate focused work streams rather than one overloaded thread.
  Date/Author: 2026-03-15 / Codex

## Outcomes & Retrospective

The feature is implemented and working. `xs2n ui` now opens a small desktop artifact browser, the optional dependency path is explicit, the scanner handles the messy real-world run history already present in the repository, and the GUI can trigger the existing CLI actions without inventing a second orchestration layer. The newest refinements are that Markdown artifacts such as `digest.md` now render as formatted documents inside the same FLTK window and the macOS app menu now presents itself as `xn2s` with only `About xn2s` and `Quit xn2s`, which makes the tool feel much less like a generic Python host window. The most important lesson was environmental rather than architectural: on macOS, the native FLTK runtime matters just as much as the Python wheel, so the docs and import error path had to make that obvious.

## Context and Orientation

The top-level CLI entrypoint is `src/xs2n/cli/cli.py`. That file registers `onboard`, `timeline`, and the `report` Typer group. This feature adds one more top-level command, `xs2n ui`, implemented in `src/xs2n/cli/ui.py`.

The digest pipeline writes timestamped run directories under multiple `data/report_runs*` roots. A “run folder” is one timestamped directory under one of those roots. A run folder may contain only a few legacy files or a full traced artifact set. The best current metadata contract is `run.json` plus optional `phases.json`, but the filesystem remains the source of truth because interrupted runs may reference files that do not exist yet.

The new GUI package lives under `src/xs2n/ui/`. `src/xs2n/ui/artifacts.py` owns read-only scanning and text loading. `src/xs2n/ui/app.py` owns the FLTK window, callbacks, and subprocess launching. The CLI module `src/xs2n/cli/ui.py` stays thin and only parses options, lazily imports the GUI launcher, and surfaces install-time errors cleanly.

The first GUI version does not introduce a second pipeline. When the user clicks `Run Digest` or `Run Latest 24h`, the GUI shells out to the existing `xs2n` CLI so the feature stays aligned with the current runtime contract.

## Plan of Work

First, add `src/xs2n/ui/artifacts.py` with small dataclasses for runs, phases, and artifacts. The scanner must walk every `report_runs*` directory under a configurable `data/` root, ignore hidden files, tolerate missing or malformed JSON, derive fallback run metadata when `run.json` is absent, and sort runs newest-first using `started_at` when available and the folder name as a fallback.

Second, add `src/xs2n/ui/app.py` with a narrow PyFLTK desktop window. The window should use a menu bar and a compact control shelf, a resizable three-pane layout, a run browser on the left, an artifact browser in the middle, and a read-only text viewer on the right. New CLI-driven runs should execute in a background thread and trigger a rescan when they complete.

Third, add `src/xs2n/cli/ui.py` as a thin Typer command, wire it into `src/xs2n/cli/cli.py`, and keep the GUI dependency optional in `pyproject.toml`.

Fourth, add focused tests in `tests/test_ui_cli.py` and `tests/test_ui_artifacts.py`. The tests must not require FLTK to be installed; they should cover the lazy CLI import path and the filesystem scanner behavior using temporary directories.

Fifth, update `README.md` and `docs/codex/autolearning.md` so the optional install path, the macOS native FLTK requirement, and the `xs2n ui` usage are visible to users and future contributors.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, the implementation and validation flow that succeeded was:

    brew install fltk
    uv sync --extra gui --extra dev
    uv run pytest tests/test_ui_cli.py tests/test_ui_artifacts.py
    uv run pytest
    uv run python - <<'PY'
    import fltk
    from pathlib import Path
    from xs2n.ui.app import ArtifactBrowserWindow
    browser = ArtifactBrowserWindow(data_dir=Path("data"))
    print(len(browser.runs), browser.runs[0].run_id)
    browser.window.hide()
    PY
    uv run xs2n ui

Expected and observed behavior:

    1. `uv run xs2n ui` opened the FLTK event loop without crashing.
    2. The window bootstrap discovered 12 real runs and selected `20260315T203138Z` first.
    3. The focused UI tests passed.
    4. The full repository test suite stayed green.

## Validation and Acceptance

Acceptance is behavioral:

1. `uv run pytest tests/test_ui_cli.py tests/test_ui_artifacts.py` passes with coverage for lazy GUI import, friendly dependency errors, scanner resilience, and newest-first ordering.
2. `uv run pytest` passes for the full repository.
3. `xs2n ui` is wired into the main CLI and opens the GUI when the optional GUI dependency and native FLTK library are present.
4. The GUI can browse at least one real run folder and display artifact contents in a read-only viewer.

Current status:

1. Passed: `6 passed, 215 warnings in 1.56s`.
2. Passed: `101 passed, 215 warnings in 7.15s`.
3. Passed: `uv run xs2n ui` entered the FLTK event loop and had to be interrupted manually because it is a real GUI process.
4. Passed: an `ArtifactBrowserWindow(data_dir=Path("data"))` bootstrap smoke discovered 12 runs and 235 artifacts in the newest real run.

## Idempotence and Recovery

The scanner and the GUI are read-only over existing run artifacts, except when the user explicitly triggers a CLI run action from the UI. Re-running the tests is safe. Re-running `xs2n ui` is safe. If FLTK is not installed on macOS, install it with Homebrew and retry. If the optional GUI dependency is missing, run `uv sync --extra gui` and retry. If a background CLI run fails, its output remains visible in the UI and the user can rerun the action after fixing the underlying issue.

## Artifacts and Notes

Context and packaging notes captured during this milestone:

- `pyfltk` package name confirmed via package index lookup:

      pyFLTK (1.4.4.0)
      Available versions: 1.4.4.0, 1.4.3.0, 1.4.2.0, ...

- Observed macOS import failure before Homebrew FLTK:

      ImportError: dlopen(.../site-packages/fltk/_fltk.cpython-312-darwin.so, 0x0002):
      Library not loaded: /opt/homebrew/opt/fltk/lib/libfltk_images.1.4.dylib

- Successful post-install bootstrap smoke:

      fltk-import-ok 10404
      window-ok 12 20260315T203138Z
      artifacts-ok 235 digest.md

Primary files touched by this milestone:

- `pyproject.toml`
- `src/xs2n/cli/cli.py`
- `src/xs2n/cli/ui.py`
- `src/xs2n/ui/__init__.py`
- `src/xs2n/ui/app.py`
- `src/xs2n/ui/artifacts.py`
- `tests/test_ui_cli.py`
- `tests/test_ui_artifacts.py`
- `README.md`
- `docs/codex/autolearning.md`
- `docs/codex/execplans/ui-artifact-browser.md`

## Interfaces and Dependencies

At the end of this milestone, the repository exposes:

    xs2n ui

through the existing `xs2n` console script. The command lives in `src/xs2n/cli/ui.py` and lazily imports a launcher from `xs2n.ui.app`.

`pyproject.toml` now defines an optional GUI extra:

    gui = ["pyfltk>=1.4.4.0"]

`src/xs2n/ui/artifacts.py` exposes a stable read-only interface that can:

    scan_runs(data_dir: Path) -> list[RunRecord]
    list_run_artifacts(run: RunRecord) -> list[ArtifactRecord]
    load_phase_records(run: RunRecord) -> list[PhaseRecord]
    load_artifact_text(path: Path) -> str

`src/xs2n/ui/app.py` exposes the launcher:

    run_artifact_browser(*, data_dir: Path, initial_run_id: str | None = None) -> None

Revision note (2026-03-15): Replaced the draft plan with the implementation-complete version so the repository keeps one canonical, restartable history for the pyFLTK artifact browser feature.
