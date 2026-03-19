from __future__ import annotations


def render_issue_placeholder_text(*, issue_title: str) -> str:
    return (
        f"ISSUE: {issue_title}\n"
        "\n"
        "Issue overview will appear here as soon as the selected issue has thread data.\n"
    )


def render_issue_canvas_text(preview) -> str:  # noqa: ANN001
    if preview is None:
        return render_issue_placeholder_text(issue_title="Selected issue")

    lines = [
        f"ISSUE: {preview.issue_title}",
        (
            f"Priority #{preview.priority_rank:02d} | {preview.priority_label} | "
            f"{preview.thread_count} threads | {preview.tweet_count} posts | "
            f"latest {_format_timestamp(preview.latest_created_at)}"
        ),
        "",
        preview.issue_summary,
        "",
    ]

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
                f"THREAD {index:02d}: {thread_card.title}",
                f"Summary: {thread_card.summary}",
                f"Why this matters: {thread_card.why_it_matters}",
                (
                    f"Posts: {thread_card.tweet_count} | "
                    f"latest {_format_timestamp(thread_card.latest_created_at)}"
                ),
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
        lines.append("-" * 72)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _format_timestamp(value) -> str:  # noqa: ANN001
    if value is None:
        return "n/a"
    return value.strftime("%Y-%m-%d %H:%M UTC")
