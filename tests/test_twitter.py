from __future__ import annotations

from datetime import UTC, datetime

import pytest
import requests

from xs2n.agents.schemas import Post, Thread
import xs2n.twitter as twitter
import xs2n.twitter_nitter as twitter_nitter


def test_get_nitter_threads_returns_domain_threads(monkeypatch) -> None:  # noqa: ANN001
    calls: list[dict[str, object]] = []

    class FakeScraper:
        def get_tweets(self, handle, mode, since):  # noqa: ANN001, ANN204
            calls.append(
                {
                    "handle": handle,
                    "mode": mode,
                    "since": since,
                }
            )
            return {
                "tweets": [
                    {
                        "id": "post-1",
                        "link": "https://x.com/alice/status/post-1",
                        "text": "Standalone post",
                        "date": "2026-03-21T10:00:00Z",
                        "user": {"username": "alice"},
                    }
                ],
                "threads": [
                    [
                        {
                            "id": "post-2",
                            "link": "https://x.com/alice/status/post-2",
                            "text": "Thread opener",
                            "date": "2026-03-21T11:00:00Z",
                            "user": {"username": "alice"},
                        },
                        {
                            "id": "post-3",
                            "link": "https://x.com/alice/status/post-3",
                            "text": "Thread reply",
                            "date": "2026-03-21T11:05:00Z",
                            "user": {"username": "alice"},
                        },
                    ]
                ],
            }

    monkeypatch.setattr(twitter_nitter, "scraper", FakeScraper())

    threads = twitter_nitter.get_nitter_threads(
        handles=["alice"],
        since_date=datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
    )

    assert calls == [
        {
            "handle": "alice",
            "mode": "user",
            "since": "2026-03-21",
        }
    ]
    assert len(threads) == 2
    assert all(isinstance(thread, Thread) for thread in threads)
    assert threads[0].thread_id == "post-1"
    assert threads[0].account_handle == "alice"
    assert [post.post_id for post in threads[1].posts] == ["post-2", "post-3"]


def test_get_nitter_threads_raises_nitter_unavailable_for_instance_lookup_network_errors(
    monkeypatch,
) -> None:  # noqa: ANN001
    class FakeNitter:
        def __init__(self, **kwargs):  # noqa: ANN003
            raise requests.RequestException(f"catalog lookup failed: {kwargs}")

    monkeypatch.setattr(twitter_nitter, "scraper", None)
    monkeypatch.setattr(twitter_nitter, "Nitter", FakeNitter)

    with pytest.raises(twitter_nitter.NitterUnavailable, match="catalog lookup failed"):
        twitter_nitter.get_nitter_threads(
            handles=["alice"],
            since_date=datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
        )


def test_get_twitter_threads_from_handles_falls_back_to_twscrape_when_nitter_has_no_instances(
    monkeypatch,
) -> None:  # noqa: ANN001
    class FakeNitterUnavailable(RuntimeError):
        pass

    expected_threads = [
        Thread(
            thread_id="thread-1",
            account_handle="alice",
            posts=[
                Post(
                    post_id="thread-1",
                    author_handle="alice",
                    created_at="2026-03-21T12:00:00Z",
                    text="Recovered from twscrape",
                    url="https://x.com/alice/status/thread-1",
                )
            ],
        )
    ]
    calls: list[tuple[str, list[str], datetime]] = []
    since_date = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)

    def fake_get_nitter_threads(*, handles, since_date):  # noqa: ANN001, ANN202
        calls.append(("nitter", handles, since_date))
        raise FakeNitterUnavailable("Could not fetch instances")

    def fake_get_twscrape_threads(*, handles, since_date):  # noqa: ANN001, ANN202
        calls.append(("twscrape", handles, since_date))
        return expected_threads

    monkeypatch.setattr(twitter, "NitterUnavailable", FakeNitterUnavailable, raising=False)
    monkeypatch.setattr(twitter, "get_nitter_threads", fake_get_nitter_threads, raising=False)
    monkeypatch.setattr(twitter, "get_twscrape_threads", fake_get_twscrape_threads, raising=False)

    threads = twitter.get_twitter_threads_from_handles(["alice"], since_date)

    assert threads == expected_threads
    assert calls == [
        ("nitter", ["alice"], since_date),
        ("twscrape", ["alice"], since_date),
    ]


def test_get_twitter_threads_from_handles_does_not_fallback_for_other_nitter_errors(
    monkeypatch,
) -> None:  # noqa: ANN001
    class FakeNitterUnavailable(RuntimeError):
        pass

    fallback_calls: list[tuple[list[str], datetime]] = []
    since_date = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)

    def fake_get_nitter_threads(*, handles, since_date):  # noqa: ANN001, ANN202
        raise RuntimeError(f"Unexpected Nitter error for {handles} at {since_date.isoformat()}")

    def fake_get_twscrape_threads(*, handles, since_date):  # noqa: ANN001, ANN202
        fallback_calls.append((handles, since_date))
        return []

    monkeypatch.setattr(twitter, "NitterUnavailable", FakeNitterUnavailable, raising=False)
    monkeypatch.setattr(twitter, "get_nitter_threads", fake_get_nitter_threads, raising=False)
    monkeypatch.setattr(twitter, "get_twscrape_threads", fake_get_twscrape_threads, raising=False)

    with pytest.raises(RuntimeError, match="Unexpected Nitter error"):
        twitter.get_twitter_threads_from_handles(["alice"], since_date)

    assert fallback_calls == []
