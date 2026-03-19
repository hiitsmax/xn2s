from __future__ import annotations

import html

from xs2n.ui.fonts import DEFAULT_UI_HTML_FONT_FAMILY
from xs2n.ui.theme import UiTheme


def render_issue_placeholder_html(*, issue_title: str, theme: UiTheme) -> str:
    return (
        "<html><body "
        f'bgcolor="{theme.viewer_plain_bg}" text="{theme.text}">'
        f'<font face="{DEFAULT_UI_HTML_FONT_FAMILY}" size="3">'
        f"<p><b>{html.escape(issue_title)}</b></p>"
        "<p>Issue overview will appear here as soon as the selected issue has thread data.</p>"
        "</font></body></html>"
    )


def render_issue_preview_html(preview, theme: UiTheme) -> str:  # noqa: ANN001
    if preview is None:
        return render_issue_placeholder_html(
            issue_title="Selected issue",
            theme=theme,
        )

    thread_sections = "".join(
        _render_thread_card(
            card=thread_card,
            index=index,
            theme=theme,
        )
        for index, thread_card in enumerate(preview.threads, start=1)
    )
    if not thread_sections:
        thread_sections = (
            "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"10\" "
            f'bgcolor="{theme.viewer_plain_bg}">'
            "<tr><td>"
            "<b>No expanded threads yet.</b><br>"
            "This issue has metadata, but the saved run does not expose thread details."
            "</td></tr></table>"
        )

    latest_label = _format_timestamp(preview.latest_created_at)
    header_html = (
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"10\" "
        f'bgcolor="{theme.viewer_panel_bg}">'
        "<tr><td>"
        f"<b>{html.escape(preview.issue_title)}</b><br>"
        f'<font color="{theme.muted_text}">'
        f"Priority #{preview.priority_rank:02d} | {html.escape(preview.priority_label)} | "
        f"{preview.thread_count} threads | {preview.tweet_count} posts | "
        f"latest {html.escape(latest_label)}"
        "</font>"
        "</td></tr></table>"
        "<p></p>"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"10\" "
        f'bgcolor="{theme.viewer_plain_bg}">'
        "<tr><td>"
        f"{html.escape(preview.issue_summary)}"
        "</td></tr></table>"
    )

    return (
        "<html><body "
        f'bgcolor="{theme.viewer_bg}" text="{theme.text}">'
        f'<font face="{DEFAULT_UI_HTML_FONT_FAMILY}" size="3">'
        f"{header_html}"
        "<p></p>"
        f"{thread_sections}"
        "</font></body></html>"
    )


def _render_thread_card(*, card, index: int, theme: UiTheme) -> str:  # noqa: ANN001
    tweets_html = "".join(
        _render_tweet_row(
            tweet=tweet,
            index=tweet_index,
            theme=theme,
        )
        for tweet_index, tweet in enumerate(card.tweets, start=1)
    )
    latest_label = _format_timestamp(card.latest_created_at)

    return (
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"0\">"
        "<tr><td>"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"10\" "
        f'bgcolor="{theme.viewer_plain_bg}">'
        "<tr><td>"
        f"<b>Thread {index:02d}</b><br>"
        f'<font color="{theme.muted_text}">'
        f"{card.tweet_count} posts | latest {html.escape(latest_label)}"
        "</font>"
        "<p></p>"
        f"<b>{html.escape(card.title)}</b><br>"
        f"{html.escape(card.summary)}"
        "<p></p>"
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"8\" "
        f'bgcolor="{theme.header_bg}">'
        "<tr><td>"
        "<b>Why this matters</b><br>"
        f"{html.escape(card.why_it_matters)}"
        "</td></tr></table>"
        "<p></p>"
        f"{tweets_html}"
        "</td></tr></table>"
        "<p></p>"
        "</td></tr></table>"
    )


def _render_tweet_row(*, tweet, index: int, theme: UiTheme) -> str:  # noqa: ANN001
    created_label = _format_timestamp(tweet.created_at)
    return (
        "<table width=\"100%\" cellspacing=\"0\" cellpadding=\"8\" "
        f'bgcolor="{theme.viewer_bg}">'
        "<tr><td>"
        f"<b>{index:02d}. @{html.escape(tweet.author_handle)}</b><br>"
        f'<font color="{theme.muted_text}">'
        f"{html.escape(tweet.kind)} | {html.escape(created_label)}"
        "</font>"
        "<p></p>"
        f"{html.escape(tweet.text)}"
        "</td></tr></table>"
        "<p></p>"
    )


def _format_timestamp(value) -> str:  # noqa: ANN001
    if value is None:
        return "n/a"
    return value.strftime("%Y-%m-%d %H:%M UTC")
