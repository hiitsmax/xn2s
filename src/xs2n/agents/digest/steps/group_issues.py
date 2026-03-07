from __future__ import annotations

from collections import OrderedDict
from typing import Any

from xs2n.schemas.digest import (
    Issue,
    IssueAssignmentResult,
    IssueThread,
    ProcessedThread,
)

from ..helpers import slugify_issue


DEFAULT_MAX_ISSUES = 6


def run(
    *,
    llm: Any,
    threads: list[ProcessedThread],
) -> tuple[list[IssueThread], list[Issue]]:
    issue_threads: list[IssueThread] = []
    grouped_threads: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for thread in threads:
        result = llm.run(
            prompt=(
                "You assign one high-signal X/Twitter thread to the live issue or argument "
                "it belongs to. Reuse a stable issue_slug when multiple threads are clearly "
                "part of the same ongoing argument. Keep the issue title newsroom-friendly."
            ),
            payload=thread,
            schema=IssueAssignmentResult,
        )
        issue_slug = slugify_issue(
            result.issue_slug or result.issue_title,
            fallback=thread.thread_id,
        )
        issue_title = result.issue_title.strip() or issue_slug.replace("_", " ").title()
        issue_summary = result.issue_summary.strip() or thread.why_it_matters
        issue_thread = IssueThread(
            **thread.model_dump(),
            issue_slug=issue_slug,
            issue_title=issue_title,
            issue_summary=issue_summary,
            why_this_thread_belongs=result.why_this_thread_belongs,
        )
        issue_threads.append(issue_thread)

        bucket = grouped_threads.setdefault(
            issue_slug,
            {
                "slug": issue_slug,
                "title": issue_title,
                "summary": issue_summary,
                "threads": [],
            },
        )
        bucket["threads"].append(issue_thread)
        if not bucket["summary"] and issue_summary:
            bucket["summary"] = issue_summary

    ordered_groups = sorted(
        grouped_threads.values(),
        key=lambda bucket: (
            max(thread.signal_score for thread in bucket["threads"]),
            max(thread.virality_score for thread in bucket["threads"]),
        ),
        reverse=True,
    )

    issues: list[Issue] = []
    for bucket in ordered_groups[:DEFAULT_MAX_ISSUES]:
        issues.append(
            Issue(
                slug=bucket["slug"],
                title=bucket["title"],
                summary=bucket["summary"],
                thread_ids=[thread.thread_id for thread in bucket["threads"]],
            )
        )

    return issue_threads, issues
