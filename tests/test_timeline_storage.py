from __future__ import annotations

from pathlib import Path

from xs2n.profile.types import TimelineEntry
from xs2n.storage import load_timeline, merge_timeline_entries


def _entry(
    tweet_id: str,
    account: str = "mx",
    *,
    favorite_count: int | None = None,
    retweet_count: int | None = None,
    reply_count: int | None = None,
    quote_count: int | None = None,
    view_count: int | None = None,
    media: list[dict[str, object]] | None = None,
) -> TimelineEntry:
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
        favorite_count=favorite_count,
        retweet_count=retweet_count,
        reply_count=reply_count,
        quote_count=quote_count,
        view_count=view_count,
        media=media or [],
    )


def test_merge_timeline_entries_adds_and_skips_duplicates(tmp_path: Path) -> None:
    timeline_file = tmp_path / "timeline.json"

    first_result = merge_timeline_entries([_entry("1"), _entry("2")], path=timeline_file)
    assert first_result.added == 2
    assert first_result.skipped_duplicates == 0

    second_result = merge_timeline_entries([_entry("2"), _entry("3")], path=timeline_file)
    assert second_result.added == 1
    assert second_result.skipped_duplicates == 1

    doc = load_timeline(timeline_file)
    stored_ids = [item["tweet_id"] for item in doc["entries"]]
    assert stored_ids == ["1", "2", "3"]


def test_merge_timeline_entries_persists_thread_metadata(tmp_path: Path) -> None:
    timeline_file = tmp_path / "timeline.json"
    entry = TimelineEntry(
        tweet_id="reply-1",
        account_handle="mx",
        author_handle="mx",
        kind="reply",
        created_at="2026-03-01T01:00:00+00:00",
        text="reply",
        retweeted_tweet_id=None,
        retweeted_author_handle=None,
        retweeted_created_at=None,
        in_reply_to_tweet_id="tweet-1",
        conversation_id="conv-1",
        timeline_source="replies",
    )

    merge_timeline_entries([entry], path=timeline_file)

    doc = load_timeline(timeline_file)
    stored = doc["entries"][0]
    assert stored["in_reply_to_tweet_id"] == "tweet-1"
    assert stored["conversation_id"] == "conv-1"
    assert stored["timeline_source"] == "replies"


def test_merge_timeline_entries_persists_engagement_metrics(tmp_path: Path) -> None:
    timeline_file = tmp_path / "timeline.json"

    merge_timeline_entries(
        [
            _entry(
                "metric-1",
                favorite_count=101,
                retweet_count=22,
                reply_count=13,
                quote_count=4,
                view_count=9000,
            )
        ],
        path=timeline_file,
    )

    doc = load_timeline(timeline_file)
    stored = doc["entries"][0]
    assert stored["favorite_count"] == 101
    assert stored["retweet_count"] == 22
    assert stored["reply_count"] == 13
    assert stored["quote_count"] == 4
    assert stored["view_count"] == 9000


def test_merge_timeline_entries_refreshes_existing_metrics(tmp_path: Path) -> None:
    timeline_file = tmp_path / "timeline.json"

    merge_timeline_entries(
        [_entry("1", favorite_count=10, retweet_count=2)],
        path=timeline_file,
    )
    merge_result = merge_timeline_entries(
        [_entry("1", favorite_count=25, retweet_count=5)],
        path=timeline_file,
    )

    assert merge_result.added == 0
    assert merge_result.skipped_duplicates == 1

    doc = load_timeline(timeline_file)
    stored = doc["entries"][0]
    assert stored["favorite_count"] == 25
    assert stored["retweet_count"] == 5


def test_merge_timeline_entries_persists_media_metadata(tmp_path: Path) -> None:
    timeline_file = tmp_path / "timeline.json"

    merge_timeline_entries(
        [
            _entry(
                "media-1",
                media=[
                    {
                        "media_url": "https://img.test/post.png",
                        "media_type": "photo",
                        "width": 1200,
                        "height": 800,
                    }
                ],
            )
        ],
        path=timeline_file,
    )

    doc = load_timeline(timeline_file)
    stored = doc["entries"][0]
    assert stored["media"] == [
        {
            "media_url": "https://img.test/post.png",
            "media_type": "photo",
            "width": 1200,
            "height": 800,
        }
    ]
