# UI Digest Issue Reading Surface

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `/Users/mx/.agents/PLANS.md`.

## Purpose / Big Picture

After this change, selecting an issue inside the native digest viewer no longer opens a second thread list that then opens a third-level preview. The issue itself becomes the reading surface: the left side ranks issues by density, the upper-right summary explains why the selected issue matters, and the lower-right canvas shows all thread cards and posts already expanded.

The observable result is: run `uv run xs2n ui`, select a run with `digest.html`, then click different issues in the digest viewer. The issue navigator is ranked instead of flat, and the selected issue immediately shows the full set of thread cards and posts without any extra click on a thread sublist.

## Progress

- [x] (2026-03-19 23:06Z) Read the existing native digest viewer modules, tests, and recent UI viewer work to identify the current issue-list -> thread-list -> preview shape.
- [x] (2026-03-19 23:16Z) Wrote failing tests for ranked issue rows, issue-level expanded previews, and multi-thread issue rendering.
- [x] (2026-03-19 23:22Z) Reworked digest browser state into issue-ranked rows plus issue-level preview data with expanded thread cards.
- [x] (2026-03-19 23:26Z) Rebuilt the digest browser layout to remove the intermediate thread list and show one issue canvas with expanded thread cards.
- [x] (2026-03-19 23:28Z) Ran focused regression tests for digest browser state plus app rendering.
- [x] (2026-03-19 23:30Z) Probed the real saved run `data/report_runs/20260318T225654Z` to confirm ranking order and preview HTML size stay reasonable.

## Surprises & Discoveries

- Observation: ranking issues by `thread_count` and `tweet_count` is enough to surface the important clusters without inventing new persisted metadata.
  Evidence: the real run `20260318T225654Z` immediately reordered the top of the navigator to `17/17`, `8/8`, and `5/5` issue clusters, which matches the user's complaint about the previous flat list having no priority.
- Observation: expanding all threads for one issue is cheap enough for the current native viewer path as long as the markup stays simple and local to one issue.
  Evidence: rendering the top-ranked real issue from `20260318T225654Z` produced `17` thread cards and an HTML payload of about `20704` characters, far below the previously problematic digest-wide rebuilt preview sizes.

## Decision Log

- Decision: remove the intermediate thread-list widget from the native digest viewer.
  Rationale: the extra level of navigation was the core usability problem. The user wants issue selection to feel like opening a prepared reading surface, not drilling into a nested list.
  Date/Author: 2026-03-19 / Codex
- Decision: rank issue rows using current saved data (`thread_count`, `tweet_count`) instead of adding a new stored score.
  Rationale: the existing artifacts already expose a useful density signal, which keeps the change local to the UI and avoids altering the report pipeline contract.
  Date/Author: 2026-03-19 / Codex
- Decision: keep the aesthetic direction inside the existing classic desktop language.
  Rationale: the project already established a native FLTK, Windows-classic visual language. The fix needed more hierarchy and rhythm, not a new design system.
  Date/Author: 2026-03-19 / Codex

## Outcomes & Retrospective

The native digest viewer now behaves more like a ranked editorial browser than a raw artifact explorer. The issue navigator tells the user what matters first, and selecting an issue opens the full stack of supporting thread cards and posts immediately.

This change stayed intentionally local. It did not add new report artifacts or change digest-generation semantics. The main lesson is that hierarchy can often be recovered from existing saved data if the UI stops mirroring raw storage structure one-to-one.

## Context and Orientation

The relevant UI lives under `/Users/mx/Documents/Progetti/mine/active/xs2n/src/xs2n/ui/`.

- `/Users/mx/Documents/Progetti/mine/active/xs2n/src/xs2n/ui/digest_browser.py` contains the native FLTK widget container shown when the selected artifact is `digest.html`.
- `/Users/mx/Documents/Progetti/mine/active/xs2n/src/xs2n/ui/digest_browser_state.py` converts saved digest data into ranked issue rows and issue-level preview models for rendering.
- `/Users/mx/Documents/Progetti/mine/active/xs2n/src/xs2n/ui/digest_browser_preview.py` renders the selected issue into simple HTML for the right-pane help view.
- `/Users/mx/Documents/Progetti/mine/active/xs2n/src/xs2n/ui/saved_digest.py` loads `issues.json` and `issue_assignments.json` from a saved run.
- `/Users/mx/Documents/Progetti/mine/active/xs2n/tests/test_digest_browser_state.py` covers the digest viewer's ranking and issue-level preview behavior.

In this document, “issue navigator” means the left list inside the digest viewer itself, not the app’s middle artifact-navigation column. “Issue canvas” means the lower-right help-view area that now renders all thread cards for the selected issue.

## Plan of Work

First, extend the digest-browser state to compute richer issue rows: rank, priority label, thread count, tweet count, and latest activity. Keep the ranking local to the UI state so the saved report format does not change.

Second, replace thread-level preview state with issue-level preview state that already contains the ordered list of thread cards and their tweets. This lets the renderer show the whole issue at once.

Third, simplify the FLTK layout in `digest_browser.py`: keep the issue navigator on the left, keep a compact summary header on the right, remove the intermediate thread list, and use one help-view canvas for the full expanded issue.

Fourth, verify behavior with focused pytest coverage and one real-run probe against `data/report_runs/20260318T225654Z`.

## Concrete Steps

Work from `/Users/mx/Documents/Progetti/mine/active/xs2n`.

1. Run the digest browser tests first and confirm they fail before implementation.

   `uv run pytest tests/test_digest_browser_state.py -q`

   Expected red phase:

   `ImportError: cannot import name 'render_issue_placeholder_html'`

2. Implement the new issue-level ranking and rendering in:

   - `src/xs2n/ui/digest_browser_state.py`
   - `src/xs2n/ui/digest_browser_preview.py`
   - `src/xs2n/ui/digest_browser.py`

3. Re-run the focused tests.

   `uv run pytest tests/test_digest_browser_state.py -q`

   Observed result:

   `4 passed in 0.08s`

4. Run the viewer/app regression set.

   `uv run pytest tests/test_digest_browser_state.py tests/test_ui_app.py tests/test_ui_app_rendering.py -q`

   Observed result:

   `35 passed, 218 warnings in 0.48s`

5. Probe the real saved run.

   `uv run python - <<'PY'`
   `from pathlib import Path`
   `from xs2n.ui.saved_digest import load_saved_digest_preview`
   `from xs2n.ui.digest_browser_state import DigestBrowserState`
   `from xs2n.ui.digest_browser_preview import render_issue_preview_html`
   `from xs2n.ui.theme import CLASSIC_LIGHT_THEME`
   `preview = load_saved_digest_preview(run_dir=Path('data/report_runs/20260318T225654Z'))`
   `state = DigestBrowserState(preview)`
   `for row in state.issue_rows()[:5]:`
   `    print(row.rank, row.priority_label, row.thread_count, row.tweet_count, row.title)`
   `issue_preview = state.selected_issue_preview()`
   `html = render_issue_preview_html(issue_preview, CLASSIC_LIGHT_THEME)`
   `print('selected_issue', issue_preview.issue_title)`
   `print('thread_cards', len(issue_preview.threads))`
   `print('html_len', len(html))`
   `PY`

   Observed result:

   `1 Lead 17 17 AI Product Launches and Voice Interfaces`
   `2 Lead 8 8 Coding Agent Harnesses and Team Experience`
   `selected_issue AI Product Launches and Voice Interfaces`
   `thread_cards 17`
   `html_len 20704`

## Validation and Acceptance

Acceptance is behavioral:

1. The digest viewer issue navigator is no longer a flat unordered-feeling list; it surfaces rank and density.
2. Selecting an issue immediately shows all its thread cards and posts in the issue canvas without requiring a second click in a thread sublist.
3. The native viewer still loads through the existing `digest.html` routing path in the app shell.
4. The regression set around `ArtifactBrowserWindow` continues to pass.

## Idempotence and Recovery

The change is safe to re-run. The ranking lives only in UI state and is recalculated from saved run artifacts every time. If the new reading surface regresses, the safe rollback is to restore the previous `digest_browser.py` and `digest_browser_state.py` versions while keeping the new tests as the definition of the desired behavior.

## Artifacts and Notes

Primary touch points:

- `/Users/mx/Documents/Progetti/mine/active/xs2n/src/xs2n/ui/digest_browser.py`
- `/Users/mx/Documents/Progetti/mine/active/xs2n/src/xs2n/ui/digest_browser_state.py`
- `/Users/mx/Documents/Progetti/mine/active/xs2n/src/xs2n/ui/digest_browser_preview.py`
- `/Users/mx/Documents/Progetti/mine/active/xs2n/tests/test_digest_browser_state.py`
- `/Users/mx/Documents/Progetti/mine/active/xs2n/docs/codex/autolearning.md`

Plan revision note: created after the user asked for issue selection to feel immediately expanded and for the issue list to communicate priority instead of acting as a long, flat list.

## Interfaces and Dependencies

At the end of this milestone, the digest browser state must expose:

    issue_rows() -> list[DigestIssueRow]
    selected_issue() -> Issue
    selected_issue_row() -> DigestIssueRow
    selected_issue_preview() -> DigestIssuePreview | None
    select_issue(slug: str) -> None

The digest browser preview module must expose:

    render_issue_placeholder_html(*, issue_title: str, theme: UiTheme) -> str
    render_issue_preview_html(preview, theme: UiTheme) -> str

No new external dependencies are required. The work continues to use FLTK widgets already present in the project and the existing saved digest artifacts on disk.
