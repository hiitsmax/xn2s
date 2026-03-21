from __future__ import annotations

from collections import OrderedDict
from typing import Any

from xs2n.schemas.digest import (
    FilteredThread,
    Issue,
    IssueSelectionResult,
    IssueThread,
    IssueWriteResult,
)

from ..helpers import compact_issue_summaries, filtered_thread_payload, slugify_issue


def _resolve_selection(
    *,
    selection: IssueSelectionResult,
    thread: FilteredThread,
    current_issues: list[Issue],
) -> IssueSelectionResult:
    resolved_issue_slug = slugify_issue(
        selection.issue_slug or thread.thread_id,
        fallback=thread.thread_id,
    )
    current_issue_slugs = {issue.slug for issue in current_issues}
    if selection.action == "update_existing_issue":
        if resolved_issue_slug not in current_issue_slugs:
            return IssueSelectionResult(
                action="create_new_issue",
                issue_slug=slugify_issue(thread.thread_id, fallback=thread.thread_id),
                reasoning=selection.reasoning,
            )
        return IssueSelectionResult(
            action=selection.action,
            issue_slug=resolved_issue_slug,
            reasoning=selection.reasoning,
        )
    return IssueSelectionResult(
        action=selection.action,
        issue_slug=resolved_issue_slug,
        reasoning=selection.reasoning,
    )


def run(
    *,
    llm: Any,
    threads: list[FilteredThread],
) -> tuple[list[IssueThread], list[Issue]]:
    kept_threads = [thread for thread in threads if thread.keep]
    issue_threads: list[IssueThread] = []
    grouped_threads: OrderedDict[str, list[IssueThread]] = OrderedDict()
    current_issues: list[Issue] = []

    for thread in kept_threads:
        selection = llm.run(
            prompt=(
                "You receive one kept X/Twitter thread and the current issue list for a "
                "magazine-style digest. Decide whether this thread should create a new issue "
                "or update an existing one. Reuse an issue only when it is clearly the same "
                "running story."
            ),
            payload={
                "thread": filtered_thread_payload(thread),
                "issues": compact_issue_summaries(current_issues),
            },
            schema=IssueSelectionResult,
            image_urls=thread.primary_tweet_media_urls,
            phase_name="group_issues",
            item_id=thread.thread_id,
        )
        selection = _resolve_selection(
            selection=selection,
            thread=thread,
            current_issues=current_issues,
        )

        written_issue = llm.run(
            prompt=(
                "You write the issue copy for one kept X/Twitter thread in a simple magazine "
                "digest. Return the final issue slug, issue title, issue summary, a short "
                "thread title, a short thread summary, and why this thread belongs in the issue."
            ),
            payload={
                "thread": filtered_thread_payload(thread),
                "issues": compact_issue_summaries(current_issues),
                "selection": selection,
            },
            schema=IssueWriteResult,
            image_urls=thread.primary_tweet_media_urls,
            phase_name="group_issues",
            item_id=thread.thread_id,
        )

        issue_slug = slugify_issue(
            written_issue.issue_slug,
            fallback=selection.issue_slug or thread.thread_id,
        )
        issue_thread = IssueThread(
            **thread.model_dump(),
            issue_slug=issue_slug,
            issue_title=written_issue.issue_title.strip() or issue_slug.replace("_", " ").title(),
            issue_summary=written_issue.issue_summary.strip() or thread.primary_tweet.text,
            thread_title=written_issue.thread_title.strip() or thread.primary_tweet.text[:80],
            thread_summary=written_issue.thread_summary.strip() or thread.primary_tweet.text,
            why_this_thread_belongs=(
                written_issue.why_this_thread_belongs.strip() or "Part of the same issue."
            ),
        )
        issue_threads.append(issue_thread)
        grouped_threads.setdefault(issue_slug, []).append(issue_thread)

        current_issues = [
            Issue(
                slug=slug,
                title=grouped_issue_threads[0].issue_title,
                summary=grouped_issue_threads[-1].issue_summary,
                thread_ids=[grouped_thread.thread_id for grouped_thread in grouped_issue_threads],
                thread_count=len(grouped_issue_threads),
            )
            for slug, grouped_issue_threads in grouped_threads.items()
        ]

    return issue_threads, current_issues
