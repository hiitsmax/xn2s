from __future__ import annotations

import html

from xs2n.ui.theme import UiTheme


def render_thread_placeholder_html(*, issue_title: str, theme: UiTheme) -> str:
    return (
        "<html><body "
        f'bgcolor="{theme.viewer_plain_bg}" text="{theme.text}">'
        f"<p><b>{html.escape(issue_title)}</b></p>"
        "<p>Select a thread to preview it below.</p>"
        "</body></html>"
    )


def render_thread_preview_html(preview, theme: UiTheme) -> str:  # noqa: ANN001
    tweet_sections = "".join(
        (
            f"<p><b>{index + 1}. @{html.escape(tweet.author_handle)}</b><br>"
            f"{html.escape(tweet.text)}</p>"
        )
        for index, tweet in enumerate(preview.tweets)
    )
    return (
        "<html><body "
        f'bgcolor="{theme.viewer_plain_bg}" text="{theme.text}">'
        f"<p><b>{html.escape(preview.title)}</b></p>"
        f"<p>{html.escape(preview.summary)}</p>"
        f"<p><i>{html.escape(preview.why_it_matters)}</i></p>"
        f"{tweet_sections}"
        "</body></html>"
    )
