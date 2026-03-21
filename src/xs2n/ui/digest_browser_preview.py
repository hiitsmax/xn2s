from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IssueSummaryPanel:
    title: str
    meta: str
    blurb: str


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
    if preview is None:
        return render_issue_placeholder_text(issue_title="Selected issue")

    lines = [preview.issue_summary, ""]

    if not preview.threads:
        lines.extend(
            [
                "No expanded threads yet.",
                "",
            ]
        )

    for index, thread_card in enumerate(preview.threads, start=1):
        lines.extend(
            [
                _format_thread_heading(index=index, title=thread_card.title),
                thread_card.summary,
                thread_card.why_it_matters,
                "",
            ]
        )
        for tweet_index, tweet in enumerate(thread_card.tweets, start=1):
            lines.extend(
                [
                    (
                        f"  {tweet_index:02d}. @{tweet.author_handle} | "
                        f"{tweet.kind} | {_format_timestamp(tweet.created_at)}"
                    ),
                    f"      {tweet.text}",
                    "",
                ]
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_thread_heading(*, index: int, title: str) -> str:
    return f"{index:02d}. {title}"


def _format_timestamp(value) -> str:  # noqa: ANN001
    if value is None:
        return "n/a"
    return value.strftime("%Y-%m-%d %H:%M UTC")
