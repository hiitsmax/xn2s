from __future__ import annotations

from datetime import timezone
import html
from pathlib import Path

from xs2n.schemas.digest import TimelineRecord
from xs2n.ui.fonts import DEFAULT_UI_HTML_FONT_FAMILY
from xs2n.ui.saved_digest import find_saved_issue_thread, load_saved_digest_preview
from xs2n.ui.theme import CLASSIC_LIGHT_THEME, UiTheme


INTERNAL_DIGEST_URI = "xs2n://digest"
_INTERNAL_THREAD_URI_PREFIX = "xs2n://thread/"


def build_thread_source_uri(thread_id: str) -> str:
    return f"{_INTERNAL_THREAD_URI_PREFIX}{thread_id}"


def parse_thread_source_uri(uri: str) -> str | None:
    if not uri.startswith(_INTERNAL_THREAD_URI_PREFIX):
        return None
    thread_id = uri.removeprefix(_INTERNAL_THREAD_URI_PREFIX).strip()
    if not thread_id:
        return None
    return thread_id


def render_saved_thread_source_html(
    *,
    artifact_path: Path,
    thread_id: str,
    theme: UiTheme = CLASSIC_LIGHT_THEME,
) -> str | None:
    preview = load_saved_digest_preview(run_dir=artifact_path.parent)
    if preview is None:
        return None

    issue, thread = find_saved_issue_thread(preview, thread_id=thread_id)
    if thread is None:
        return None

    tweet_rows = "".join(
        _render_tweet_row_html(
            tweet,
            index=index,
            total=len(thread.tweets),
            theme=theme,
        )
        for index, tweet in enumerate(thread.tweets)
    )
    if not tweet_rows:
        tweet_rows = _render_empty_thread_state(theme=theme)

    metadata_rows = "".join(
        (
            _metadata_row_html("run", preview.run_id, theme=theme),
            _metadata_row_html(
                "issue",
                issue.title if issue is not None else "Unassigned",
                theme=theme,
            ),
            _metadata_row_html("account", f"@{thread.account_handle}", theme=theme),
            _metadata_row_html("tweets", str(len(thread.tweets)), theme=theme),
        )
    )
    breadcrumb_text = " / ".join(
        (
            "Digest",
            issue.title if issue is not None else "Unassigned issue",
            thread.thread_title,
        )
    )

    return (
        "<html>"
        f'<body bgcolor="{theme.viewer_bg}" text="{theme.text}">'
        f"<font face=\"{DEFAULT_UI_HTML_FONT_FAMILY}\" size=\"3\">"
        f"{_title_bar_html(thread.thread_title, theme=theme)}"
        "<p></p>"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\">"
        "<tr>"
        f"<td bgcolor=\"{theme.header_bg}\">"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"6\" border=\"0\">"
        "<tr>"
        f"<td>{_wrap_default_ui_face(_link_html(INTERNAL_DIGEST_URI, breadcrumb_text, theme=theme))}</td>"
        "</tr>"
        "</table>"
        "</td>"
        "</tr>"
        "</table>"
        "<p></p>"
        f"{_panel_html(
            'Snapshot',
            ''.join(
                (
                    '<p>',
                    _wrap_default_ui_face(html.escape(thread.thread_summary)),
                    '<br>',
                    f'<font color=\"{theme.muted_text}\">',
                    _wrap_default_ui_face(
                        'This snapshot keeps the X chrome hidden. Use Open on X to inspect the original post.'
                    ),
                    '</font>',
                    '</p>',
                    '<p>',
                    _wrap_default_ui_face(
                        _link_html(
                            thread.primary_tweet.source_url,
                            'Open on X',
                            theme=theme,
                        )
                    ),
                    '</p>',
                )
            ),
            theme=theme,
        )}"
        f"{_panel_html(
            'Context',
            ''.join(
                (
                    '<p>',
                    _wrap_default_ui_face(html.escape(breadcrumb_text)),
                    '</p>',
                    '<table width=\"100%\" cellspacing=\"0\" cellpadding=\"4\" border=\"0\">',
                    metadata_rows,
                    '</table>',
                )
            ),
            theme=theme,
        )}"
        f"{_panel_html('Thread Outline', tweet_rows, theme=theme)}"
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


def _render_tweet_row_html(
    tweet: TimelineRecord,
    *,
    index: int,
    total: int,
    theme: UiTheme,
) -> str:
    row_label = f"{index + 1} / {total}"
    subtitle = " | ".join(
        part
        for part in (
            f"@{tweet.author_handle}",
            _tweet_kind_label(tweet.kind),
            _format_timestamp(tweet),
        )
        if part
    )
    return (
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\">"
        "<tr>"
        f"<td bgcolor=\"{theme.panel_bg}\">"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"6\" border=\"0\">"
        "<tr>"
        f"<td width=\"54\"><b>{_wrap_default_ui_face(html.escape(row_label))}</b></td>"
        f"<td>{_wrap_default_ui_face(html.escape(subtitle))}</td>"
        f"<td align=\"right\">{_wrap_default_ui_face(_link_html(tweet.source_url, 'Open on X', theme=theme))}</td>"
        "</tr>"
        "</table>"
        "</td>"
        "</tr>"
        "<tr>"
        f"<td bgcolor=\"{theme.panel_bg2}\">"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"6\" border=\"0\">"
        "<tr>"
        f"<td>{_wrap_default_ui_face(html.escape(_teaser(tweet.text)))}</td>"
        "</tr>"
        "</table>"
        "</td>"
        "</tr>"
        "</table>"
        "<p></p>"
    )


def _render_empty_thread_state(*, theme: UiTheme) -> str:
    return (
        "<p>"
        f'<font color="{theme.muted_text}">'
        f"{_wrap_default_ui_face('No tweet rows were captured for this thread.')}"
        "</font>"
        "</p>"
    )


def _metadata_row_html(label: str, value: str, *, theme: UiTheme) -> str:
    return (
        "<tr>"
        f"<td width=\"72\"><b>{_wrap_default_ui_face(html.escape(label))}</b></td>"
        f"<td>{_wrap_default_ui_face(html.escape(value))}</td>"
        "</tr>"
    )


def _tweet_kind_label(kind: str) -> str:
    if kind == "reply":
        return "Reply"
    if kind == "retweet":
        return "Retweet"
    return "Post"


def _format_timestamp(tweet: TimelineRecord) -> str:
    created_at = tweet.created_at
    if created_at.tzinfo is None:
        return created_at.strftime("%Y-%m-%d %H:%M")
    return created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _teaser(text: str, *, limit: int = 160) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."


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
