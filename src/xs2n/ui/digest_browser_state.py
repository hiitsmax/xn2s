from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from xs2n.schemas.digest import Issue, IssueThread, TimelineRecord
from xs2n.ui.saved_digest import SavedDigestPreview


DigestIssueSortKey = Literal["title", "thread_count"]


@dataclass(frozen=True, slots=True)
class DigestIssueSort:
    key: DigestIssueSortKey
    ascending: bool


@dataclass(slots=True)
class DigestIssueRow:
    slug: str
    title: str
    summary: str
    rank: int
    priority_label: str
    thread_count: int
    tweet_count: int
    latest_created_at: datetime | None

    def render_label(self) -> str:
        title = _truncate_text(self.title, limit=40)
        return f"{title}\t{self.thread_count}"


@dataclass(slots=True)
class DigestIssueThreadCard:
    thread_id: str
    title: str
    summary: str
    why_it_matters: str
    tweets: list[TimelineRecord]
    tweet_count: int
    latest_created_at: datetime
    open_url: str


@dataclass(slots=True)
class DigestIssuePreview:
    issue_title: str
    issue_summary: str
    priority_rank: int
    priority_label: str
    thread_count: int
    tweet_count: int
    latest_created_at: datetime | None
    threads: list[DigestIssueThreadCard]
    lead_open_url: str

    def summary_meta(self) -> str:
        return (
            f"#{self.priority_rank:02d} {self.priority_label} | "
            f"{self.thread_count} threads | "
            f"{self.tweet_count} posts"
        )


class DigestBrowserState:
    def __init__(self, preview: SavedDigestPreview) -> None:
        self.preview = preview
        self._issues_by_slug = {issue.slug: issue for issue in preview.issues}
        self._threads_by_id = {
            thread.thread_id: thread for thread in preview.issue_threads
        }
        self._issue_threads_by_slug = {
            issue.slug: self._ordered_issue_threads(issue)
            for issue in preview.issues
        }
        self._issue_sort = DigestIssueSort(key="thread_count", ascending=False)
        self._issue_rows: list[DigestIssueRow] = []
        self._issue_rows_by_slug: dict[str, DigestIssueRow] = {}
        self._selected_issue_slug: str | None = None
        self._refresh_issue_rows()

    @property
    def digest_title(self) -> str:
        if self.preview.digest_title:
            return self.preview.digest_title
        if self.preview.issues:
            return self.preview.issues[0].title
        return "No issue digest produced"

    @property
    def run_summary(self) -> str:
        return (
            f"Run {self.preview.run_id} | "
            f"{len(self.preview.issues)} issues ranked by signal density | "
            f"{len(self.preview.issue_threads)} threads"
        )

    def issue_rows(self) -> list[DigestIssueRow]:
        return list(self._issue_rows)

    def issue_sort(self) -> DigestIssueSort:
        return self._issue_sort

    def select_issue(self, slug: str) -> None:
        if slug in self._issues_by_slug:
            self._selected_issue_slug = slug

    def toggle_issue_sort(self, key: DigestIssueSortKey) -> None:
        if self._issue_sort.key == key:
            self._issue_sort = DigestIssueSort(
                key=key,
                ascending=not self._issue_sort.ascending,
            )
        else:
            self._issue_sort = DigestIssueSort(
                key=key,
                ascending=_default_issue_sort_ascending(key),
            )
        self._refresh_issue_rows()

    def selected_issue(self) -> Issue:
        if self._selected_issue_slug is None:
            raise RuntimeError("No issues available.")
        return self._issues_by_slug[self._selected_issue_slug]

    def selected_issue_row(self) -> DigestIssueRow:
        issue = self.selected_issue()
        return self._issue_rows_by_slug[issue.slug]

    def selected_issue_preview(self) -> DigestIssuePreview | None:
        if self._selected_issue_slug is None:
            return None

        issue = self.selected_issue()
        row = self.selected_issue_row()
        threads = self._issue_threads_by_slug.get(issue.slug, [])
        thread_cards = [
            DigestIssueThreadCard(
                thread_id=thread.thread_id,
                title=thread.thread_title,
                summary=thread.thread_summary,
                why_it_matters=thread.why_this_thread_belongs,
                tweets=thread.tweets,
                tweet_count=len(thread.tweets),
                latest_created_at=thread.latest_created_at,
                open_url=thread.primary_tweet.source_url,
            )
            for thread in threads
        ]
        lead_open_url = thread_cards[0].open_url if thread_cards else ""
        return DigestIssuePreview(
            issue_title=issue.title,
            issue_summary=issue.summary,
            priority_rank=row.rank,
            priority_label=row.priority_label,
            thread_count=row.thread_count,
            tweet_count=row.tweet_count,
            latest_created_at=row.latest_created_at,
            threads=thread_cards,
            lead_open_url=lead_open_url,
        )

    def _build_issue_rows(self) -> list[DigestIssueRow]:
        issue_rows: list[DigestIssueRow] = []
        for issue in self.preview.issues:
            issue_threads = self._issue_threads_by_slug.get(issue.slug, [])
            thread_count = issue.thread_count or len(issue.thread_ids) or len(issue_threads)
            tweet_count = sum(len(thread.tweets) for thread in issue_threads)
            latest_created_at = (
                max((thread.latest_created_at for thread in issue_threads), default=None)
            )
            issue_rows.append(
                DigestIssueRow(
                    slug=issue.slug,
                    title=issue.title,
                    summary=issue.summary,
                    rank=0,
                    priority_label="Brief",
                    thread_count=thread_count,
                    tweet_count=tweet_count,
                    latest_created_at=latest_created_at,
                )
            )

        ranked_rows = sorted(
            issue_rows,
            key=lambda row: (
                -row.thread_count,
                -row.tweet_count,
                row.title.casefold(),
            ),
        )
        for rank, row in enumerate(
            ranked_rows,
            start=1,
        ):
            row.rank = rank
            row.priority_label = _priority_label(
                thread_count=row.thread_count,
                tweet_count=row.tweet_count,
            )
        return _sort_issue_rows_for_display(
            ranked_rows,
            sort_state=self._issue_sort,
        )

    def _refresh_issue_rows(self) -> None:
        self._issue_rows = self._build_issue_rows()
        self._issue_rows_by_slug = {row.slug: row for row in self._issue_rows}
        if self._selected_issue_slug is None and self._issue_rows:
            self._selected_issue_slug = self._issue_rows[0].slug

    def _ordered_issue_threads(self, issue: Issue) -> list[IssueThread]:
        ordered_threads: list[IssueThread] = []
        for thread_id in issue.thread_ids:
            thread = self._threads_by_id.get(thread_id)
            if thread is not None:
                ordered_threads.append(thread)
        return ordered_threads


def _priority_label(*, thread_count: int, tweet_count: int) -> str:
    if thread_count >= 8 or tweet_count >= 12:
        return "Lead"
    if thread_count >= 4 or tweet_count >= 6:
        return "Watch"
    if thread_count >= 2 or tweet_count >= 2:
        return "Track"
    return "Brief"


def _default_issue_sort_ascending(key: DigestIssueSortKey) -> bool:
    if key == "title":
        return True
    return False


def _sort_issue_rows_for_display(
    issue_rows: list[DigestIssueRow],
    *,
    sort_state: DigestIssueSort,
) -> list[DigestIssueRow]:
    if sort_state.key == "title":
        return sorted(
            issue_rows,
            key=lambda row: row.title.casefold(),
            reverse=not sort_state.ascending,
        )
    if sort_state.ascending:
        return sorted(
            issue_rows,
            key=lambda row: (row.thread_count, row.title.casefold()),
        )
    return sorted(
        issue_rows,
        key=lambda row: (-row.thread_count, row.title.casefold()),
    )


def _truncate_text(value: str, *, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: max(0, limit - 3)].rstrip()}..."
