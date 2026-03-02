from __future__ import annotations

from pathlib import Path

from xs2n.profile.types import TimelineEntry
from xs2n.timeline_storage import load_timeline, merge_timeline_entries


def _entry(tweet_id: str, account: str = "mx") -> TimelineEntry:
    return TimelineEntry(
        tweet_id=tweet_id,
        account_handle=account,
        author_handle=account,
        kind="post",
        created_at="2026-03-01T00:00:00+00:00",
        text=f"tweet {tweet_id}",
        retweeted_tweet_id=None,
        retweeted_author_handle=None,
        retweeted_created_at=None,
    )


def test_merge_timeline_entries_adds_and_skips_duplicates(tmp_path: Path) -> None:
    timeline_file = tmp_path / "timeline.yaml"

    first_result = merge_timeline_entries([_entry("1"), _entry("2")], path=timeline_file)
    assert first_result.added == 2
    assert first_result.skipped_duplicates == 0

    second_result = merge_timeline_entries([_entry("2"), _entry("3")], path=timeline_file)
    assert second_result.added == 1
    assert second_result.skipped_duplicates == 1

    doc = load_timeline(timeline_file)
    stored_ids = [item["tweet_id"] for item in doc["entries"]]
    assert stored_ids == ["1", "2", "3"]
