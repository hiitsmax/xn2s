# UI Appearance Theme

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository does not contain a checked-in `PLANS.md`; this document follows the global guidance in `/Users/mx/.agents/PLANS.md`. It also captures the approved design direction from the current conversation so implementation can continue safely even in a dirty worktree with multiple concurrent agents.

## Purpose / Big Picture

After this change, `uv run xs2n ui` can follow the operating system appearance by default while still letting the user override it in Preferences with `System`, `Classic Light`, or `Classic Dark`. The entire desktop browser, including the FLTK chrome and the HTML-based artifact viewer, should switch coherently instead of mixing a dark shell with a light viewer or vice versa. The visible proof is that the UI opens in a light or dark classic theme based on the host system, the override persists across restarts, and changing the override from Preferences updates the open window immediately.

## Progress

- [x] (2026-03-18 18:48Z) Gathered current UI ownership and FLTK theming constraints from the codebase plus fresh Context7 FLTK docs.
- [x] (2026-03-18 18:48Z) Validated the approved design direction: optional appearance override, `system` default, full-theme viewer support, and a retro dark mode that stays Windows-classic rather than modern-flat.
- [x] (2026-03-18 20:02Z) Added failing tests for appearance-mode normalization, system-theme resolution, appearance persistence, dark viewer rendering, Preferences apply/cancel behavior, app-level theme switching, and authentication-window theming.
- [x] (2026-03-18 20:19Z) Added `src/xs2n/ui/theme.py` and `src/xs2n/storage/ui_state.py`, then made `src/xs2n/ui/viewer.py` consume shared theme tokens instead of hard-coded beige HTML colors.
- [x] (2026-03-18 21:05Z) Extended `src/xs2n/ui/run_preferences.py` with an Appearance tab plus an apply-time appearance callback, and wired `src/xs2n/ui/app.py` to persist the override, resolve the effective theme, and repaint the open UI.
- [x] (2026-03-18 21:24Z) Extended `src/xs2n/ui/auth_window.py` so the authentication window now follows the same light/dark palette as the rest of the desktop UI.
- [x] (2026-03-18 21:52Z) Fixed a concurrent-worktree verification blocker by making `src/xs2n/schemas/__init__.py` import-safe and by lazily importing digest execution in `src/xs2n/report_runtime.py`.
- [x] (2026-03-18 22:11Z) Root-caused the unexpected quit-confirmation prompt to automatic startup auth refresh, added a focused regression test, and removed the eager auth refresh from `ArtifactBrowserWindow.__init__`.
- [x] (2026-03-18 22:47Z) Verified the feature with focused UI tests, the full `tests/test_ui_*.py` pass, `py_compile`, and a runtime smoke that instantiated and closed `ArtifactBrowserWindow` without triggering the old auth-warning side effect.
- [x] (2026-03-18 22:47Z) Closed follow-up review findings by theming HTML artifacts in the viewer, adding dark-capable CSS to `digest.html`, making `ui_state.json` writes atomic, reconciling the auth-bootstrap documentation with the final behavior, and fixing the stale preview-failure request-id bug in the async renderer path.

## Surprises & Discoveries

- Observation: the desktop chrome and the viewer are currently themed by two unrelated systems.
  Evidence: `src/xs2n/ui/app.py` defines FLTK colors such as `COMMAND_STRIP_COLOR`, while `src/xs2n/ui/viewer.py` hard-codes HTML `bgcolor` values independently.

- Observation: FLTK gives enough global palette hooks for a system-aware theme, but `Fl_Help_View` still needs explicit HTML palette changes.
  Evidence: fresh Context7 FLTK docs confirm `Fl::background`, `Fl::background2`, `Fl::foreground`, `Fl::set_color`, and `Fl::reload_scheme`, while `Fl_Help_View` only supports limited HTML styling and does not automatically inherit the app’s semantic palette.

- Observation: the worktree is already dirty in the same UI files this feature must touch.
  Evidence: `git status --short` before implementation shows local modifications in `src/xs2n/ui/app.py`, `src/xs2n/ui/viewer.py`, `src/xs2n/ui/fonts.py`, and multiple UI test files, plus untracked `src/xs2n/ui/run_preferences.py` and related tests.

- Observation: two unrelated import chains in the shared worktree blocked UI verification before the theme work itself even ran.
  Evidence: initial pytest collection failed because `xs2n.schemas.__init__` eagerly imported missing digest models, and `xs2n.report_runtime` imported digest execution eagerly even when the UI only needed argument dataclasses.

- Observation: the old app bootstrap triggered `auth doctor` automatically, which made the UI look busy and raised an intrusive quit-confirmation dialog even when the user had not launched any report command.
  Evidence: the live smoke originally hung on close and the user provided a screenshot of the native quit-confirmation prompt naming `auth doctor`; the new regression test `test_init_does_not_refresh_auth_state_automatically` failed before removing the eager refresh.

- Observation: the primary viewer path for `digest.html` needed a separate dark-theme treatment beyond the markdown/plain-text shell.
  Evidence: review caught that HTML artifacts were still returned verbatim from `src/xs2n/ui/viewer.py`, which kept the main digest artifact light until the viewer began injecting a theme-specific CSS override.

## Decision Log

- Decision: keep the theme architecture small and token-based instead of introducing a generic styling framework.
  Rationale: this repository already centralizes most desktop styling in `src/xs2n/ui/app.py` and `src/xs2n/ui/viewer.py`; a narrow `theme.py` plus a small persisted appearance state is enough to support `system`, `classic_light`, and `classic_dark` without speculative abstraction.
  Date/Author: 2026-03-18 / Codex

- Decision: persist the appearance override separately from run-command preferences.
  Rationale: `RunPreferencesWindow` currently owns editable command arguments and run-list columns, but appearance is application state rather than a transient form draft. A small storage document keeps responsibilities clearer and reduces merge pressure on the Preferences form logic.
  Date/Author: 2026-03-18 / Codex

- Decision: keep appearance side effects in `ArtifactBrowserWindow` and use a dedicated apply-time callback from `RunPreferencesWindow`.
  Rationale: `RunPreferencesWindow` should continue to own draft form state plus apply/cancel behavior, while the main app window should remain responsible for saving appearance state, resolving the effective theme, and repainting widgets. This avoids burying persistence or viewer refresh logic inside the Preferences window.
  Date/Author: 2026-03-18 / Codex

- Decision: avoid editing `src/xs2n/storage/__init__.py` in the first implementation pass unless an existing caller truly benefits from package-level re-exports.
  Rationale: the worktree is shared and that aggregator file is not necessary for this feature if the UI imports `src/xs2n/storage/ui_state.py` directly.
  Date/Author: 2026-03-18 / Codex

- Decision: theme the viewer fully in dark mode rather than leaving a light document inside a dark shell.
  Rationale: the user explicitly asked for the whole UI to change, and partial theming would make the artifact browser feel visually split.
  Date/Author: 2026-03-18 / Codex

- Decision: do not refresh authentication automatically during `ArtifactBrowserWindow` startup.
  Rationale: auth refresh is useful on explicit demand or as a preflight before running commands, but it should not make the browser look busy or block clean quitting just because the app opened.
  Date/Author: 2026-03-18 / Codex

- Decision: keep HTML artifact theming in the viewer as an override layer instead of trying to make every HTML artifact generator aware of the current in-app appearance mode.
  Rationale: the viewer owns the live appearance context, while generated artifacts such as `digest.html` may also be opened outside the app. A viewer-side CSS override plus a standalone `prefers-color-scheme` fallback in the HTML renderer covers both cases with minimal coupling.
  Date/Author: 2026-03-18 / Codex

## Outcomes & Retrospective

This milestone is complete. The desktop UI now resolves a classic light or classic dark theme from a persisted appearance mode, the Preferences window exposes `System`, `Classic Light`, and `Classic Dark`, the HTML viewer follows the same palette as the FLTK chrome, and the authentication window no longer sticks out as a light-themed orphan. The final result also removed a noisy startup side effect: authentication preflight now happens only when the user asks for it or when a report command needs it, so opening and closing the browser is calm again.

## Context and Orientation

The desktop UI entrypoint is `src/xs2n/cli/ui.py`, which lazily imports `run_artifact_browser(...)` from `src/xs2n/ui/app.py`. `app.py` builds the FLTK window, owns the command strip, run list, navigation panes, viewer widget, and most widget-level styling. `src/xs2n/ui/viewer.py` renders artifact content to HTML strings for `Fl_Help_View`, so it is effectively the second theme system in this app. `src/xs2n/ui/run_preferences.py` owns the Preferences window and already implements apply/cancel semantics for digest/latest command arguments plus run-list column visibility. Persistence helpers live under `src/xs2n/storage/`, where small JSON documents such as `onboard_state.json` and `report_state.json` are loaded and saved by focused modules.

For this feature, “appearance mode” means the user-facing selector with three values: `system`, `classic_light`, and `classic_dark`. “Resolved theme” means the actual palette applied to widgets and HTML after the app looks at the appearance mode and, if needed, the operating system. “System theme detection” means best-effort detection at app startup using the host platform APIs or commands, with a safe fallback to classic light when the platform does not expose a reliable dark-mode signal.

The worktree is currently shared with other agents. That means this feature should prefer additive changes in new files or small seams over refactoring existing UI ownership boundaries. It also means all touched files must be read carefully before editing, and no existing local changes should be reverted.

## Plan of Work

Start with tests. Add a new `tests/test_ui_theme.py` that defines the contract for appearance-mode normalization, system-theme resolution on macOS and Windows fallbacks, and the mapping from appearance mode to light or dark theme tokens. Add a small storage test file for appearance persistence, following the simple JSON document pattern already used in `src/xs2n/storage/onboard_state.py` and `src/xs2n/storage/report_state.py`.

Then add the implementation seam. Create `src/xs2n/ui/theme.py` for the theme dataclass, color tokens, mode normalization, system-theme detection, and FLTK global color application helpers. Create `src/xs2n/storage/ui_state.py` for persisted appearance mode with a single JSON document under `data/`. Import that module directly from the desktop UI code unless a concrete existing caller proves that package-level re-exports are necessary.

Next, update `src/xs2n/ui/viewer.py` so its rendering helpers accept a `UiTheme` object and render both classic light and classic dark HTML from shared tokens rather than hard-coded beige values. Add or update tests in `tests/test_ui_viewer.py` to prove the theme changes actually appear in the HTML output.

After that, extend `src/xs2n/ui/run_preferences.py` with a new Appearance tab or section that exposes `System`, `Classic Light`, and `Classic Dark` using the same apply/cancel semantics as the existing preferences. Keep the responsibility honest: the window should manage drafts, applied values, and callbacks, but not system-detection logic. The contract should mirror the existing run-list callback style: `RunPreferencesWindow` receives an `on_appearance_mode_changed(mode: str)` callback, and that callback only fires after `Apply` commits the new appearance mode.

Finally, update `src/xs2n/ui/app.py` to load the saved appearance mode, resolve the effective theme, apply FLTK palette defaults, apply widget-level colors, pass the theme to the viewer renderer, and react to appearance changes from Preferences by persisting the override and repainting the open window. Keep the code path additive and avoid reorganizing unrelated run-list or artifact-scanning logic. When the feature is in place, update this ExecPlan, update `docs/codex/autolearning.md`, and verify the desktop UI behavior through focused tests.

## Concrete Steps

From `/Users/mx/Documents/Progetti/mine/active/xs2n`, execute the work in this order:

1. Add failing tests for theme logic and state persistence.
2. Run:
     uv run pytest tests/test_ui_theme.py tests/test_ui_state_storage.py tests/test_ui_viewer.py tests/test_ui_run_preferences.py tests/test_ui_app.py
   Expectation before implementation: the new appearance-specific tests fail for missing modules, missing fields, or unchanged HTML.
3. Implement the smallest theme and storage modules needed to satisfy the new tests.
4. Re-run the focused test command after each red-green step until it passes.
5. Run a broader regression pass:
     uv run pytest tests/test_ui_fonts.py tests/test_ui_theme.py tests/test_ui_state_storage.py tests/test_ui_viewer.py tests/test_ui_run_preferences.py tests/test_ui_app.py tests/test_ui_cli.py
6. If the local FLTK runtime is available, smoke the app manually:
     uv run xs2n ui
   Open Preferences, switch Appearance between `System`, `Classic Light`, and `Classic Dark`, and confirm the shell plus viewer both repaint coherently.

Observed execution:

1. `uv run pytest tests/test_ui_theme.py tests/test_ui_state_storage.py tests/test_ui_viewer.py -q` -> `12 passed`.
2. `uv run pytest tests/test_ui_run_preferences.py tests/test_ui_app.py -q` -> `24 passed`.
3. `uv run pytest tests/test_ui_auth_window.py -q` -> `3 passed`.
4. `uv run pytest tests/test_ui_app.py::test_viewer_render_future_error_keeps_original_request_identity tests/test_ui_viewer.py tests/test_render_digest_html.py tests/test_ui_*.py -q` -> `93 passed`.
5. `uv run python -m py_compile src/xs2n/ui/theme.py src/xs2n/storage/ui_state.py src/xs2n/ui/viewer.py src/xs2n/ui/run_preferences.py src/xs2n/ui/auth_window.py src/xs2n/ui/app.py src/xs2n/ui/run_arguments.py src/xs2n/report_runtime.py src/xs2n/schemas/__init__.py` -> exit code `0`.
6. `uv run python - <<'PY' ... ArtifactBrowserWindow(...) ... PY` -> printed `{'appearance_mode': 'system', 'theme': 'classic_dark', 'runs': 2}` and closed cleanly after the startup auth-refresh side effect was removed.

## Validation and Acceptance

Acceptance is behavioral:

1. Launching `uv run xs2n ui` with no saved override uses the operating system appearance when detectable, or classic light when not.
2. Preferences expose exactly three appearance values: `System`, `Classic Light`, and `Classic Dark`.
3. Clicking `Apply` repaints the existing desktop window without requiring a restart.
4. The override persists across restarts by reading and writing a small JSON state document under `data/`.
5. The HTML viewer changes with the rest of the app instead of keeping the old hard-coded light palette.
6. Focused automated tests prove mode normalization, state persistence, viewer rendering, the apply-time Preferences callback contract, and app-level callback wiring.

## Idempotence and Recovery

The new appearance-state document must be safe to recreate and overwrite repeatedly. If it is missing or malformed, the app should fall back to `system` mode and resolve that safely to light or dark. All theme application should be additive and reversible: switching from dark to light in the same session must produce the same visible result as starting fresh in light mode. If the theme change path regresses, the safe rollback is to remove the appearance-state callback wiring and fall back to the current light theme while keeping the new tests as the acceptance contract.

## Artifacts and Notes

The most important evidence will be focused pytest output plus a short note in `docs/codex/autolearning.md` summarizing the architecture and any FLTK caveats. If the app-level repaint path requires a small compromise because of current FLTK limitations, that compromise must be recorded both here and in the Decision Log.

## Interfaces and Dependencies

At the end of this milestone, `src/xs2n/ui/theme.py` should expose stable, honest interfaces for:

- normalizing an appearance mode string to one of `system`, `classic_light`, or `classic_dark`;
- resolving the effective theme from appearance mode plus platform state;
- applying the resolved theme to FLTK global colors;
- providing shared tokens for both widget styling and viewer HTML rendering.

At the end of this milestone, `src/xs2n/storage/ui_state.py` should expose a tiny JSON-backed interface equivalent in spirit to:

- `DEFAULT_UI_STATE_PATH`
- `load_ui_state(path: Path | None = None) -> dict[str, str]`
- `save_ui_state(state: dict[str, str], path: Path | None = None) -> None`

At the end of this milestone, `RunPreferencesWindow` in `src/xs2n/ui/run_preferences.py` should accept and apply an appearance mode alongside the existing digest/latest/run-list state, expose a dedicated apply-time appearance callback, and keep persistence plus repaint side effects out of the window class itself. `ArtifactBrowserWindow` in `src/xs2n/ui/app.py` should own the active resolved theme, save the chosen override, and repaint the current UI when that mode changes.

Revision note (2026-03-18): Created this ExecPlan after the user approved an optional, system-aware appearance feature with a manual override and a fully themed dark-mode viewer.
Revision note (2026-03-18): Tightened the plan after review to specify the Preferences callback contract, include the persistence test in the required commands, and avoid unnecessary edits to `src/xs2n/storage/__init__.py`.
Revision note (2026-03-18): Marked the implementation complete, recorded the import-chain unblockers encountered in the shared worktree, documented the late auth-refresh fix that removed the unwanted quit-confirmation prompt, and captured the follow-up HTML-viewer/atomic-save hardening prompted by review.
