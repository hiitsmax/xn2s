from __future__ import annotations

from dataclasses import dataclass


CANVAS_STYLE_BODY = "A"
CANVAS_STYLE_THREAD_TITLE = "B"
CANVAS_STYLE_THREAD_SUMMARY = "C"
CANVAS_STYLE_THREAD_CONTEXT = "D"
CANVAS_STYLE_TWEET_META = "E"
CANVAS_STYLE_TWEET_TEXT = "F"


@dataclass(frozen=True, slots=True)
class IssueSummaryPanel:
    title: str
    meta: str
    blurb: str


@dataclass(frozen=True, slots=True)
class IssueCanvasDocument:
    text: str
    styles: str


def build_issue_summary_panel(preview) -> IssueSummaryPanel:  # noqa: ANN001
    if preview is None:
        return IssueSummaryPanel(
            title="Selected issue",
            meta="",
            blurb="",
        )

    return IssueSummaryPanel(
        title=preview.issue_title,
        meta=preview.summary_meta(),
        blurb=preview.issue_summary,
    )


def render_issue_placeholder_text(*, issue_title: str) -> str:
    return (
        f"{issue_title}\n"
        "\n"
        "Issue overview will appear here as soon as the selected issue has thread data.\n"
    )


def render_issue_canvas_text(preview) -> str:  # noqa: ANN001
    return build_issue_canvas_document(preview).text


def render_issue_canvas_styles(preview) -> str:  # noqa: ANN001
    return build_issue_canvas_document(preview).styles


def build_issue_canvas_document(preview) -> IssueCanvasDocument:  # noqa: ANN001
    if preview is None:
        placeholder = render_issue_placeholder_text(issue_title="Selected issue")
        return IssueCanvasDocument(
            text=placeholder,
            styles=CANVAS_STYLE_BODY * len(placeholder),
        )

    segments: list[tuple[str, str]] = [("\n", CANVAS_STYLE_BODY)]

    if not preview.threads:
        _append_segment(
            segments,
            "No expanded threads yet.\n",
            CANVAS_STYLE_BODY,
        )
    else:
        for index, thread_card in enumerate(preview.threads, start=1):
            if index > 1:
                _append_segment(segments, "\n", CANVAS_STYLE_BODY)
            _append_segment(
                segments,
                _format_thread_heading(index=index, title=thread_card.title),
                CANVAS_STYLE_THREAD_TITLE,
            )
            _append_segment(segments, "\n\n", CANVAS_STYLE_BODY)
            _append_segment(
                segments,
                thread_card.summary,
                CANVAS_STYLE_THREAD_SUMMARY,
            )
            _append_segment(segments, "\n\n", CANVAS_STYLE_BODY)
            for tweet_index, tweet in enumerate(thread_card.tweets, start=1):
                _append_segment(
                    segments,
                    (
                        f"Source post {tweet_index:02d}. @{tweet.author_handle} | "
                        f"{tweet.kind} | {_format_timestamp(tweet.created_at)}"
                    ),
                    CANVAS_STYLE_TWEET_META,
                )
                _append_segment(segments, "\n", CANVAS_STYLE_BODY)
                _append_segment(
                    segments,
                    f"      {tweet.text}",
                    CANVAS_STYLE_TWEET_TEXT,
                )
                _append_segment(segments, "\n\n", CANVAS_STYLE_BODY)
            if thread_card.why_it_matters:
                _append_segment(
                    segments,
                    "Why here: ",
                    CANVAS_STYLE_TWEET_META,
                )
                _append_segment(
                    segments,
                    thread_card.why_it_matters,
                    CANVAS_STYLE_THREAD_CONTEXT,
                )
                _append_segment(segments, "\n\n", CANVAS_STYLE_BODY)

    text = "".join(part for part, _style in segments)
    styles = "".join(style * len(part) for part, style in segments)
    if not text.endswith("\n"):
        text = f"{text}\n"
        styles = f"{styles}{CANVAS_STYLE_BODY}"
    return IssueCanvasDocument(text=text, styles=styles)


def _format_thread_heading(*, index: int, title: str) -> str:
    return f"{index:02d}. {title}"


def _append_segment(
    segments: list[tuple[str, str]],
    text: str,
    style: str,
) -> None:
    if text:
        segments.append((text, style))


def _format_timestamp(value) -> str:  # noqa: ANN001
    if value is None:
        return "n/a"
    return value.strftime("%Y-%m-%d %H:%M UTC")
