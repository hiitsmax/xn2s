# UI Digest Source Snapshot

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `/Users/mx/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, someone browsing a saved digest in `xs2n ui` can click `source` on a thread card and stay inside the desktop UI. Instead of jumping straight to X, the right-hand viewer will show an internal source snapshot page that keeps the Windows-classic feel, summarizes the selected issue/thread context, lists the thread tweets as compact breadcrumb-like rows, and requires an explicit `Open on X` click to leave the app.

The observable result is simple: run `uv run xs2n ui`, open a run with `digest.html`, click `source`, and watch the viewer swap from the digest overview to the new source snapshot page without changing the run/artifact selection.

## Progress

- [x] (2026-03-19 18:33Z) Confirmed the product direction with the user: use an internal source page instead of embedded X or iframe content.
- [x] (2026-03-19 18:35Z) Re-read the local planning rules in `/Users/mx/.agents/PLANS.md` and the repo guidance in `AGENTS.md`.
- [x] (2026-03-19 18:36Z) Re-checked the current viewer architecture and confirmed the desktop app uses `fltk.Fl_Help_View` with HTML subset rendering in `src/xs2n/ui/app.py` and `src/xs2n/ui/viewer.py`.
- [x] (2026-03-19 18:38Z) Verified fresh documentation and live headers showing that direct `iframe` of `x.com/.../status/...` is blocked (`X-Frame-Options: DENY`), so the internal snapshot path remains the chosen design.
- [x] (2026-03-19 18:43Z) Wrote failing tests for digest source navigation and source snapshot rendering in `tests/test_ui_viewer.py` and `tests/test_ui_app_rendering.py`.
- [x] (2026-03-19 18:48Z) Implemented internal source snapshot rendering, saved-digest loading helpers, and the digest preview layout refresh.
- [x] (2026-03-19 18:50Z) Ran focused and broader UI regression tests and confirmed the new navigation stays green.
- [ ] Update the autolearning note and create the final atomic feature commit.

## Surprises & Discoveries

- Observation: the local Python environment used for repo work currently does not have `fltk` installed, so runtime widget introspection is unavailable here.
  Evidence: `python - <<'PY' import fltk PY` raised `ModuleNotFoundError: No module named 'fltk'`.
- Observation: pyFLTK does expose `Fl_Help_View.link(...)`, so the viewer can intercept followed links even though the current app does not use that hook yet.
  Evidence: the pyFLTK API reference at `https://pyfltk.sourceforge.io/docs/fltk.html` lists `Fl_Help_View.link = __Fl_Help_ViewLink(self, *args)`.
- Observation: the pyFLTK `link(...)` wrapper injects extra callback arguments, so the safest app-level handler is tolerant of `*args` and resolves the clicked URI from the last string argument.
  Evidence: `uv run python - <<'PY' import inspect, fltk; print(inspect.getsource(fltk.Fl_Help_View.link)) PY` shows `new_args = (self, args[0], self)` before calling `_fltk.Fl_Help_View_link(...)`.

## Decision Log

- Decision: keep the implementation inside the existing `Fl_Help_View` pipeline instead of introducing a real embedded browser.
  Rationale: the user explicitly chose the internal snapshot approach, and the current UI already rebuilds digest HTML into FLTK-safe markup.
  Date/Author: 2026-03-19 / Codex
- Decision: use an internal `source` page with compact tweet rows and explicit `Open on X` links rather than rendering full X chrome or automatic outbound navigation.
  Rationale: this matches the user's request for a sincere internal verification surface while keeping the “look deeper” action deliberate.
  Date/Author: 2026-03-19 / Codex

## Outcomes & Retrospective

The desktop digest viewer now supports internal source snapshots without introducing an embedded browser. The implementation stayed inside the existing `Fl_Help_View` flow by splitting saved-digest loading into `src/xs2n/ui/saved_digest.py`, adding a dedicated source snapshot renderer in `src/xs2n/ui/source_preview.py`, refreshing the digest overview layout in `src/xs2n/ui/digest_preview.py`, and wiring link handling in `src/xs2n/ui/app.py`.

The strongest result is that the user-visible behavior is now aligned with the chosen product direction: `source` keeps you inside the app, shows breadcrumb context plus a compact thread outline, and makes `Open on X` an explicit escape hatch instead of the default action.

## Context and Orientation

The desktop artifact browser lives in `src/xs2n/ui/app.py`. It creates a three-pane window and renders the right-hand preview with `fltk.Fl_Help_View`. The helper `src/xs2n/ui/viewer.py` decides how each artifact becomes HTML for that widget. Saved issue digests get special treatment through `src/xs2n/ui/digest_preview.py`, which does not show the saved `digest.html` file directly; instead it rebuilds a simpler HTML preview from `issues.json`, `issue_assignments.json`, and `run.json`.

The digest pipeline stores thread-level source information in `src/xs2n/schemas/digest.py`. Each `IssueThread` carries the tweet list and the source URLs needed to build both the internal source snapshot and the explicit X links. The relevant tests already live in `tests/test_ui_viewer.py` and `tests/test_ui_app_rendering.py`; these are the safest places to lock the new behavior before editing production code.

## Plan of Work

First, add failing tests that describe the expected UI behavior. One test will prove that the rebuilt digest preview now emits an internal `source` link rather than a raw outbound X link. A second test will prove that the source snapshot page shows breadcrumb context, compact thread rows, and `Open on X` actions. A third test will exercise the viewer link handler in `ArtifactBrowserWindow` so we know an internal source URI swaps the current viewer HTML in place and an external HTTP link opens in the system browser path instead of attempting to render the remote page inside FLTK.

Next, split saved-digest loading from digest preview rendering so the new source snapshot page can reuse the same run data without turning `digest_preview.py` into a junk drawer. Keep the naming honest: one module should load saved digest data, one should render the digest overview, and one should render source snapshots. The source snapshot HTML should stay within the FLTK-safe subset: tables, paragraphs, line breaks, and links, with Windows-classic palette blocks taken from the existing `UiTheme`.

Then, wire `Fl_Help_View.link(...)` in `src/xs2n/ui/app.py`. Internal `xs2n://...` links should be resolved by the app itself and rendered back into the same viewer widget. External `https://x.com/...` links should open through Python’s `webbrowser` module and leave the current viewer content unchanged. The artifact selection should remain on `digest.html`, because the source page is a navigation layer inside that artifact, not a new disk artifact.

Finally, refresh the digest overview layout so it reads more clearly in the Windows-classic theme. Improve spacing, issue/thread framing, and metadata grouping with simple table-based panels instead of the current mostly linear paragraph flow.

## Concrete Steps

Work from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Run the focused tests that cover the current viewer and confirm the new behavior is missing.
   Expected: the new assertions fail because internal source navigation does not exist yet.

   `uv run pytest tests/test_ui_viewer.py tests/test_ui_app_rendering.py -q`

2. Implement the new saved-digest/source-preview modules and the app link handler.

3. Re-run the focused UI tests.
   Expected: all selected tests pass and demonstrate internal source rendering.

   `uv run pytest tests/test_ui_viewer.py tests/test_ui_app_rendering.py -q`

4. Run the broader digest/viewer regression tests.

   `uv run pytest tests/test_render_digest_html.py tests/test_ui_viewer.py tests/test_ui_app_rendering.py tests/test_ui_app.py -q`

Observed result:

   `35 passed, 218 warnings in 0.70s`

## Validation and Acceptance

Acceptance is both automated and user-visible.

Automated proof means the focused UI tests pass and include assertions that:

- a saved digest preview renders a `source` link using the internal URI scheme,
- the source snapshot page includes breadcrumb context, compact tweet rows, and explicit `Open on X` links,
- the app-level link handler updates the viewer in place for internal URIs and launches the browser path for external X links.

User-visible proof means opening `xs2n ui`, selecting a run with `digest.html`, clicking `source`, and observing that:

- the right pane stays inside the desktop UI,
- the page now shows the issue/thread context and compact thread outline,
- leaving the app requires an explicit `Open on X` click.

## Idempotence and Recovery

This work is additive inside the UI layer and safe to repeat. Re-running tests is idempotent. If the `Fl_Help_View.link(...)` wiring behaves unexpectedly on a local machine with `pyfltk` installed, the safe rollback is to comment out the link registration and fall back to the previous static preview while keeping the new render helpers and tests as a guide.

## Artifacts and Notes

Important repo files for this change:

- `src/xs2n/ui/app.py`
- `src/xs2n/ui/viewer.py`
- `src/xs2n/ui/digest_preview.py`
- `src/xs2n/schemas/digest.py`
- `tests/test_ui_viewer.py`
- `tests/test_ui_app_rendering.py`

Plan revision note: created this ExecPlan after the user approved the internal source snapshot design, to guide implementation and keep discoveries recorded in one place.

Plan revision note (2026-03-19 18:50Z): updated the progress, discoveries, and outcomes after implementation and verification so the document now reflects the working feature instead of the original intent only.

## Interfaces and Dependencies

The implementation will continue using the existing FLTK/pyFLTK desktop stack. `ArtifactBrowserWindow` in `src/xs2n/ui/app.py` must gain a link resolver with a shape equivalent to:

    def _handle_viewer_link(self, widget, uri: str) -> str | None:
        ...

The saved-digest loader must expose a reusable function that accepts a run directory path and returns the parsed digest/thread models. The source snapshot renderer must accept the selected digest artifact path, a thread identifier, and the current `UiTheme`, then return one HTML string ready for `Fl_Help_View.value(...)`.
