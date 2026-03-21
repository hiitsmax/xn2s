from __future__ import annotations

from collections import OrderedDict
from typing import Any

from xs2n.schemas import (
    DigestIssue,
    DigestOutput,
    DigestThread,
    FilteredThread,
    IssueSelectionResult,
    IssueWriteResult,
)


SELECT_ISSUE_PROMPT = (
    "You receive one kept X/Twitter thread and the current issue list for a "
    "magazine-style digest. Decide whether this thread should create a new issue "
    "or update an existing one. Reuse an issue only when it is clearly the same running story."
)

WRITE_ISSUE_PROMPT = (
    "You write the issue copy for one kept X/Twitter thread in a simple magazine digest. "
    "Return the final issue slug, issue title, issue summary, a short thread title, "
    "a short thread summary, and why this thread belongs in the issue."
)


def _slugify_issue(value: str, *, fallback: str) -> str:
    cleaned = "".join(
        character.lower() if character.isalnum() else "_"
        for character in value.strip()
    ).strip("_")
    collapsed = "_".join(part for part in cleaned.split("_") if part)
    return collapsed or fallback


def _compact_issue_summaries(issues: list[DigestIssue]) -> list[dict[str, str]]:
    return [
        {
            "slug": issue.slug,
            "title": issue.title,
            "summary": issue.summary,
        }
        for issue in issues
    ]


def _resolve_selection(
    *,
    selection: IssueSelectionResult,
    thread: FilteredThread,
    current_issues: list[DigestIssue],
) -> IssueSelectionResult:
    resolved_issue_slug = _slugify_issue(
        selection.issue_slug or thread.thread_id,
        fallback=thread.thread_id,
    )
    current_issue_slugs = {issue.slug for issue in current_issues}
    if selection.action == "update_existing_issue" and resolved_issue_slug not in current_issue_slugs:
        return IssueSelectionResult(
            action="create_new_issue",
            issue_slug=_slugify_issue(thread.thread_id, fallback=thread.thread_id),
            reasoning=selection.reasoning,
        )
    return IssueSelectionResult(
        action=selection.action,
        issue_slug=resolved_issue_slug,
        reasoning=selection.reasoning,
    )


def run(*, llm: Any, threads: list[FilteredThread]) -> list[DigestIssue]:
    kept_threads = [thread for thread in threads if thread.keep]
    grouped_threads: OrderedDict[str, list[DigestThread]] = OrderedDict()
    issue_titles: dict[str, str] = {}
    issue_summaries: dict[str, str] = {}
    current_issues: list[DigestIssue] = []

    for thread in kept_threads:
        selection = llm.run(
            prompt=SELECT_ISSUE_PROMPT,
            payload={
                "thread": thread.model_dump(mode="json"),
                "issues": _compact_issue_summaries(current_issues),
            },
            schema=IssueSelectionResult,
        )
        selection = _resolve_selection(
            selection=selection,
            thread=thread,
            current_issues=current_issues,
        )

        issue_write = llm.run(
            prompt=WRITE_ISSUE_PROMPT,
            payload={
                "thread": thread.model_dump(mode="json"),
                "issues": _compact_issue_summaries(current_issues),
                "selection": selection.model_dump(mode="json"),
            },
            schema=IssueWriteResult,
        )

        issue_slug = _slugify_issue(
            issue_write.issue_slug,
            fallback=selection.issue_slug or thread.thread_id,
        )
        digest_thread = DigestThread(
            thread_id=thread.thread_id,
            account_handle=thread.account_handle,
            thread_title=issue_write.thread_title.strip() or thread.primary_post.text[:80],
            thread_summary=issue_write.thread_summary.strip() or thread.primary_post.text,
            why_this_thread_belongs=(
                issue_write.why_this_thread_belongs.strip() or "Part of the same issue."
            ),
            filter_reason=thread.filter_reason,
            source_urls=thread.source_urls,
        )

        grouped_threads.setdefault(issue_slug, []).append(digest_thread)
        issue_titles[issue_slug] = (
            issue_write.issue_title.strip() or issue_slug.replace("_", " ").title()
        )
        issue_summaries[issue_slug] = (
            issue_write.issue_summary.strip() or thread.primary_post.text
        )

        current_issues = [
            DigestIssue(
                slug=slug,
                title=issue_titles[slug],
                summary=issue_summaries[slug],
                threads=grouped_threads[slug],
            )
            for slug in grouped_threads
        ]

    return current_issues
