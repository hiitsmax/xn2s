from __future__ import annotations

from dataclasses import dataclass

from xs2n.schemas.digest import Issue, IssueThread, TimelineRecord
from xs2n.ui.saved_digest import SavedDigestPreview, find_saved_issue_thread


@dataclass(slots=True)
class DigestIssueRow:
    slug: str
    title: str
    summary: str
    thread_count: int


@dataclass(slots=True)
class DigestThreadRow:
    thread_id: str
    title: str
    summary: str
    issue_slug: str


@dataclass(slots=True)
class DigestThreadPreview:
    issue_title: str
    title: str
    summary: str
    why_it_matters: str
    tweets: list[TimelineRecord]
    open_url: str


class DigestBrowserState:
    def __init__(self, preview: SavedDigestPreview) -> None:
        self.preview = preview
        self._issues_by_slug = {issue.slug: issue for issue in preview.issues}
        self._threads_by_id = {
            thread.thread_id: thread for thread in preview.issue_threads
        }
        self._selected_issue_slug = preview.issues[0].slug if preview.issues else None
        self._selected_thread_id: str | None = None

    @property
    def digest_title(self) -> str:
        return self.preview.digest_title

    @property
    def run_summary(self) -> str:
        return (
            f"Run {self.preview.run_id} | "
            f"{len(self.preview.issues)} issues | "
            f"{len(self.preview.issue_threads)} threads"
        )

    def issue_rows(self) -> list[DigestIssueRow]:
        return [
            DigestIssueRow(
                slug=issue.slug,
                title=issue.title,
                summary=issue.summary,
                thread_count=issue.thread_count or len(issue.thread_ids),
            )
            for issue in self.preview.issues
        ]

    def select_issue(self, slug: str) -> None:
        if slug in self._issues_by_slug:
            self._selected_issue_slug = slug
            self._selected_thread_id = None

    def selected_issue(self) -> Issue:
        if self._selected_issue_slug is None:
            raise RuntimeError("No issues available.")
        return self._issues_by_slug[self._selected_issue_slug]

    def thread_rows(self) -> list[DigestThreadRow]:
        issue = self.selected_issue()
        rows: list[DigestThreadRow] = []
        for thread_id in issue.thread_ids:
            thread = self._threads_by_id.get(thread_id)
            if thread is None:
                continue
            rows.append(
                DigestThreadRow(
                    thread_id=thread.thread_id,
                    title=thread.thread_title,
                    summary=thread.thread_summary,
                    issue_slug=issue.slug,
                )
            )
        return rows

    def select_thread(self, thread_id: str) -> None:
        issue, thread = find_saved_issue_thread(self.preview, thread_id=thread_id)
        if issue is None or thread is None:
            return
        self._selected_issue_slug = issue.slug
        self._selected_thread_id = thread_id

    def selected_thread(self) -> IssueThread | None:
        if self._selected_thread_id is None:
            return None
        return self._threads_by_id.get(self._selected_thread_id)

    def thread_preview(self) -> DigestThreadPreview | None:
        thread = self.selected_thread()
        if thread is None:
            return None
        issue, resolved_thread = find_saved_issue_thread(
            self.preview,
            thread_id=thread.thread_id,
        )
        if issue is None or resolved_thread is None:
            return None
        return DigestThreadPreview(
            issue_title=issue.title,
            title=resolved_thread.thread_title,
            summary=resolved_thread.thread_summary,
            why_it_matters=resolved_thread.why_this_thread_belongs,
            tweets=resolved_thread.tweets,
            open_url=resolved_thread.primary_tweet.source_url,
        )
