from __future__ import annotations

import html
from pathlib import Path

from xs2n.schemas.digest import Issue, IssueThread
from xs2n.ui.fonts import DEFAULT_UI_HTML_FONT_FAMILY
from xs2n.ui.saved_digest import load_saved_digest_preview
from xs2n.ui.source_preview import build_thread_source_uri
from xs2n.ui.theme import CLASSIC_LIGHT_THEME, UiTheme


def render_saved_digest_preview_html(
    *,
    artifact_path: Path,
    theme: UiTheme = CLASSIC_LIGHT_THEME,
) -> str | None:
    preview = load_saved_digest_preview(run_dir=artifact_path.parent)
    if preview is None:
        return None

    issue_threads_by_id = {
        thread.thread_id: thread for thread in preview.issue_threads
    }
    issue_panels = "".join(
        _render_issue_panel_html(
            issue,
            issue_threads_by_id=issue_threads_by_id,
            theme=theme,
        )
        for issue in preview.issues
    )
    if not issue_panels:
        issue_panels = _render_empty_state_html(theme=theme)

    metadata_html = _panel_html(
        title="Digest Overview",
        body_html=(
            "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"4\" border=\"0\">"
            f"{_metadata_row_html('path', str(artifact_path), theme=theme)}"
            f"{_metadata_row_html('kind', 'html', theme=theme)}"
            f"{_metadata_row_html('run', preview.run_id, theme=theme)}"
            f"{_metadata_row_html('issues', str(len(preview.issues)), theme=theme)}"
            f"{_metadata_row_html('threads', str(len(preview.issue_threads)), theme=theme)}"
            "</table>"
        ),
        theme=theme,
    )

    return (
        "<html>"
        f'<body bgcolor="{theme.viewer_bg}" text="{theme.text}">'
        f"<font face=\"{DEFAULT_UI_HTML_FONT_FAMILY}\" size=\"3\">"
        f"{_title_bar_html(preview.digest_title, theme=theme)}"
        "<p></p>"
        f"{metadata_html}"
        f"{issue_panels}"
        "</font>"
        "</body>"
        "</html>"
    )


def _title_bar_html(title: str, *, theme: UiTheme) -> str:
    return (
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\">"
        "<tr>"
        f"<td bgcolor=\"{theme.viewer_panel_bg}\">"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"8\" border=\"0\">"
        "<tr>"
        f"<td><b>{_wrap_default_ui_face(html.escape(title))}</b></td>"
        "</tr>"
        "</table>"
        "</td>"
        "</tr>"
        "</table>"
    )


def _render_issue_panel_html(
    issue: Issue,
    *,
    issue_threads_by_id: dict[str, IssueThread],
    theme: UiTheme,
) -> str:
    thread_cards = "".join(
        _render_thread_card_html(issue_threads_by_id[thread_id], theme=theme)
        for thread_id in issue.thread_ids
        if thread_id in issue_threads_by_id
    )
    if not thread_cards:
        thread_cards = (
            "<p>"
            f'<font color="{theme.muted_text}">'
            f"{_wrap_default_ui_face('No saved thread assignments matched this issue.')}"
            "</font>"
            "</p>"
        )

    body_html = (
        "<p>"
        f"{_wrap_default_ui_face(html.escape(issue.summary))}"
        "</p>"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"4\" border=\"0\">"
        f"{_metadata_row_html('threads', str(issue.thread_count or len(issue.thread_ids)), theme=theme)}"
        f"{_metadata_row_html('slug', issue.slug, theme=theme)}"
        "</table>"
        "<p></p>"
        f"{thread_cards}"
    )
    return _panel_html(issue.title, body_html, theme=theme)


def _render_thread_card_html(thread: IssueThread, *, theme: UiTheme) -> str:
    source_uri = build_thread_source_uri(thread.thread_id)
    lead_line = f"@{thread.primary_tweet.author_handle} | {thread.primary_tweet.kind}"
    body_html = (
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"4\" border=\"0\">"
        f"{_metadata_row_html('Thread summary', thread.thread_summary, theme=theme)}"
        f"{_metadata_row_html('Why it matters', thread.why_this_thread_belongs, theme=theme)}"
        f"{_metadata_row_html('Lead', lead_line, theme=theme)}"
        f"{_metadata_row_html('Source', _link_html(source_uri, 'source', theme=theme), theme=theme, is_html=True)}"
        "</table>"
    )
    return _panel_html(thread.thread_title, body_html, theme=theme)


def _render_empty_state_html(*, theme: UiTheme) -> str:
    return _panel_html(
        "No issue digest produced",
        (
            "<p>"
            f"{_wrap_default_ui_face('No threads survived the loose filter in this run.')}"
            "</p>"
        ),
        theme=theme,
    )


def _panel_html(title: str, body_html: str, *, theme: UiTheme) -> str:
    return (
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\">"
        "<tr>"
        f"<td bgcolor=\"{theme.header_bg}\">"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"6\" border=\"0\">"
        "<tr>"
        f"<td><b>{_wrap_default_ui_face(html.escape(title))}</b></td>"
        "</tr>"
        "</table>"
        "</td>"
        "</tr>"
        "<tr>"
        f"<td bgcolor=\"{theme.viewer_plain_bg}\">"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"8\" border=\"0\">"
        "<tr>"
        f"<td>{body_html}</td>"
        "</tr>"
        "</table>"
        "</td>"
        "</tr>"
        "</table>"
        "<p></p>"
    )


def _metadata_row_html(
    label: str,
    value: str,
    *,
    theme: UiTheme,
    is_html: bool = False,
) -> str:
    rendered_value = value if is_html else html.escape(value)
    return (
        "<tr>"
        f"<td width=\"112\"><b>{_wrap_default_ui_face(html.escape(label))}</b></td>"
        f"<td>{_wrap_default_ui_face(rendered_value) if not is_html else rendered_value}</td>"
        "</tr>"
    )


def _link_html(url: str, label: str, *, theme: UiTheme) -> str:
    return (
        f'<a href="{html.escape(url)}">'
        f'<font color="{theme.selection_bg}">{html.escape(label)}</font>'
        "</a>"
    )


def _default_ui_face_tag() -> str:
    return f'<font face="{DEFAULT_UI_HTML_FONT_FAMILY}">'


def _wrap_default_ui_face(text: str) -> str:
    return f"{_default_ui_face_tag()}{text}</font>"
