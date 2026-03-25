from __future__ import annotations

from datetime import UTC, datetime

from xs2n.agents.schemas import Thread
import xs2n.twitter as twitter


def test_get_twitter_threads_from_handles_returns_domain_threads(monkeypatch) -> None:  # noqa: ANN001
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

    monkeypatch.setattr(twitter, "scraper", FakeScraper())

    threads = twitter.get_twitter_threads_from_handles(
        ["alice"],
        datetime(2026, 3, 21, 12, 0, tzinfo=UTC),
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

