from __future__ import annotations

from datetime import UTC, datetime

import xs2n.twitter_nitter_net as twitter_nitter_net


def test_build_threads_from_nitter_profile_items_maps_single_posts() -> None:
    threads = twitter_nitter_net.build_threads_from_nitter_profile_items(
        "alice",
        [
            {
                "post_id": "123",
                "author_handle": "alice",
                "created_at": "Mar 29, 2026 10:15 AM UTC",
                "text": "Hello",
            }
        ],
    )

    assert len(threads) == 1
    assert threads[0].thread_id == "123"
    assert threads[0].account_handle == "alice"
    assert threads[0].posts[0].url == "https://x.com/alice/status/123"


def test_build_threads_from_nitter_profile_items_keeps_tracked_handle_for_retweets() -> None:
    threads = twitter_nitter_net.build_threads_from_nitter_profile_items(
        "tracked",
        [
            {
                "post_id": "123",
                "author_handle": "other",
                "created_at": "Mar 29, 2026 10:15 AM UTC",
                "text": "Hello",
            }
        ],
    )

    assert len(threads) == 1
    assert threads[0].account_handle == "tracked"
    assert threads[0].posts[0].author_handle == "other"


def test_get_nitter_net_threads_filters_out_older_profile_items(monkeypatch) -> None:  # noqa: ANN001
    def fake_scrape_profile_items(handle: str) -> list[dict[str, str]]:
        assert handle == "alice"
        return [
            {
                "post_id": "old",
                "author_handle": "alice",
                "created_at": "Mar 28, 2026 10:15 AM UTC",
                "text": "Old",
            },
            {
                "post_id": "new",
                "author_handle": "alice",
                "created_at": "Mar 29, 2026 10:15 AM UTC",
                "text": "New",
            },
        ]

    monkeypatch.setattr(twitter_nitter_net, "scrape_nitter_profile_items", fake_scrape_profile_items)

    threads = twitter_nitter_net.get_nitter_net_threads(
        handles=["alice"],
        since_date=datetime(2026, 3, 29, 0, 0, tzinfo=UTC),
    )

    assert [thread.thread_id for thread in threads] == ["new"]
