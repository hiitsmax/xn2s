from __future__ import annotations

from datetime import datetime, timezone

from xs2n.agents.digest.steps.group_issues import run as group_issues
from xs2n.schemas.digest import (
    FilteredThread,
    IssueSelectionResult,
    IssueWriteResult,
    TimelineRecord,
)


def _record(*, tweet_id: str, text: str, created_at: datetime) -> TimelineRecord:
    return TimelineRecord.model_validate(
        {
            "tweet_id": tweet_id,
            "account_handle": "mx",
            "author_handle": "mx",
            "kind": "post",
            "created_at": created_at.isoformat(),
            "text": text,
            "conversation_id": tweet_id,
        }
    )


def _thread(*, tweet_id: str, text: str, created_at: datetime) -> FilteredThread:
    record = _record(tweet_id=tweet_id, text=text, created_at=created_at)
    return FilteredThread.model_validate(
        {
            "thread_id": tweet_id,
            "conversation_id": tweet_id,
            "account_handle": "mx",
            "tweets": [record.model_dump(mode="json")],
            "source_tweet_ids": [tweet_id],
            "context_tweet_ids": [],
            "latest_created_at": created_at.isoformat(),
            "primary_tweet_id": tweet_id,
            "primary_tweet": record.model_dump(mode="json"),
            "keep": True,
            "filter_reason": "keep_real_signal",
        }
    )


class _FakeLLM:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        *,
        prompt: str,
        payload,
        schema,
        image_urls=None,
        phase_name: str = "llm",
        item_id: str | None = None,
    ):  # noqa: ANN001, ANN201
        self.calls.append(
            {
                "schema_name": schema.__name__,
                "phase_name": phase_name,
                "item_id": item_id,
                "payload": payload,
                "image_urls": image_urls or [],
            }
        )
        thread_payload = payload["thread"]["thread"]
        thread_id = (
            thread_payload.thread_id
            if hasattr(thread_payload, "thread_id")
            else thread_payload["thread_id"]
        )

        if schema is IssueSelectionResult:
            if payload["issues"]:
                return IssueSelectionResult(
                    action="update_existing_issue",
                    issue_slug="missing-story",
                    reasoning="same story",
                )
            return IssueSelectionResult(
                action="create_new_issue",
                issue_slug="chip_race",
                reasoning="first thread starts the issue",
            )

        if schema is IssueWriteResult:
            selection = payload["selection"]
            issue_slug = selection.issue_slug or thread_id
            return IssueWriteResult(
                issue_slug=issue_slug,
                issue_title=f"Title {thread_id}",
                issue_summary=f"Summary {thread_id}",
                thread_title=f"Thread {thread_id}",
                thread_summary=f"Thread summary {thread_id}",
                why_this_thread_belongs="Same story.",
            )

        raise AssertionError(f"Unexpected schema: {schema.__name__}")


def test_group_issues_passes_explicit_trace_metadata() -> None:
    started_at = datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)
    llm = _FakeLLM()

    issue_threads, issues = group_issues(
        llm=llm,
        threads=[_thread(tweet_id="conv-1", text="Chip race starts here", created_at=started_at)],
    )

    assert len(issue_threads) == 1
    assert issues[0].slug == "chip_race"
    assert [call["phase_name"] for call in llm.calls] == ["group_issues", "group_issues"]
    assert [call["item_id"] for call in llm.calls] == ["conv-1", "conv-1"]


def test_group_issues_rejects_invalid_update_existing_issue_slug() -> None:
    first_started_at = datetime(2026, 3, 21, 12, 0, tzinfo=timezone.utc)
    second_started_at = datetime(2026, 3, 21, 12, 5, tzinfo=timezone.utc)
    llm = _FakeLLM()

    issue_threads, issues = group_issues(
        llm=llm,
        threads=[
            _thread(tweet_id="conv-1", text="Chip race starts here", created_at=first_started_at),
            _thread(
                tweet_id="conv-2",
                text="A new twist in the chip race",
                created_at=second_started_at,
            ),
        ],
    )

    write_calls = [
        call for call in llm.calls if call["schema_name"] == "IssueWriteResult"
    ]
    second_write_call = write_calls[1]
    second_selection = second_write_call["payload"]["selection"]

    assert [thread.issue_slug for thread in issue_threads] == ["chip_race", "conv_2"]
    assert [issue.slug for issue in issues] == ["chip_race", "conv_2"]
    assert second_selection.action == "create_new_issue"
    assert second_selection.issue_slug == "conv_2"
