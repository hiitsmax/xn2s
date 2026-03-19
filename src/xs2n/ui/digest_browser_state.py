from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from xs2n.schemas.digest import Issue, IssueThread
from xs2n.ui.saved_digest import SavedDigestPreview, find_saved_issue_thread


ScreenMode = Literal["overview", "thread"]
RowKind = Literal["issue", "thread", "tweet"]


@dataclass(slots=True)
class DigestBrowserRow:
    kind: RowKind
    label: str
    detail: str
    thread_id: str | None = None


@dataclass(slots=True)
class DigestBrowserScreen:
    mode: ScreenMode
    title: str
    subtitle: str
    summary: str
    rows: list[DigestBrowserRow]
    can_go_back: bool
    open_url: str | None = None


class DigestBrowserState:
    def __init__(self, preview: SavedDigestPreview) -> None:
        self.preview = preview
        self._selected_thread_id: str | None = None
        self._thread_by_id = {
            thread.thread_id: thread for thread in preview.issue_threads
        }
        self._issue_by_thread_id: dict[str, Issue] = {}
        for issue in preview.issues:
            for thread_id in issue.thread_ids:
                self._issue_by_thread_id[thread_id] = issue

    def show_overview(self) -> None:
        self._selected_thread_id = None

    def show_thread(self, thread_id: str) -> None:
        if thread_id in self._thread_by_id:
            self._selected_thread_id = thread_id

    def go_back(self) -> None:
        self.show_overview()

    def current_screen(self) -> DigestBrowserScreen:
        if self._selected_thread_id is None:
            return self._overview_screen()
        return self._thread_screen(self._selected_thread_id)

    def _overview_screen(self) -> DigestBrowserScreen:
        rows: list[DigestBrowserRow] = []
        for issue in self.preview.issues:
            rows.append(
                DigestBrowserRow(
                    kind="issue",
                    label=issue.title,
                    detail=issue.summary,
                )
            )
            for thread_id in issue.thread_ids:
                thread = self._thread_by_id.get(thread_id)
                if thread is None:
                    continue
                rows.append(
                    DigestBrowserRow(
                        kind="thread",
                        label=f"  {thread.thread_title}",
                        detail=thread.thread_summary,
                        thread_id=thread.thread_id,
                    )
                )

        return DigestBrowserScreen(
            mode="overview",
            title=self.preview.digest_title,
            subtitle=(
                f"Run {self.preview.run_id} | "
                f"{len(self.preview.issues)} issues | "
                f"{len(self.preview.issue_threads)} threads"
            ),
            summary=(
                "Select a thread to inspect the saved source snapshot inside the viewer."
            ),
            rows=rows,
            can_go_back=False,
            open_url=None,
        )

    def _thread_screen(self, thread_id: str) -> DigestBrowserScreen:
        issue, thread = find_saved_issue_thread(self.preview, thread_id=thread_id)
        if thread is None:
            self.show_overview()
            return self._overview_screen()

        breadcrumb_parts = [
            "Digest",
            issue.title if issue is not None else "Unassigned issue",
            thread.thread_title,
        ]
        rows = [
            DigestBrowserRow(
                kind="tweet",
                label=f"{index + 1}/{len(thread.tweets)} {tweet.author_handle}",
                detail=tweet.text,
                thread_id=thread.thread_id,
            )
            for index, tweet in enumerate(thread.tweets)
        ]
        return DigestBrowserScreen(
            mode="thread",
            title=thread.thread_title,
            subtitle=" / ".join(breadcrumb_parts),
            summary=(
                f"{thread.thread_summary}\n\n"
                f"{thread.why_this_thread_belongs}"
            ),
            rows=rows,
            can_go_back=True,
            open_url=thread.primary_tweet.source_url,
        )
