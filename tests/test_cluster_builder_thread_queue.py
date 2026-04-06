from __future__ import annotations

from xs2n.schemas.clustering import TweetQueueItem
from xs2n.schemas.twitter import Post, Thread
from xs2n.utils.twitter import build_tweet_queue_items


def test_build_tweet_queue_items_uses_primary_post_and_pending_defaults() -> None:
    threads = [
        Thread(
            thread_id="thread-1",
            account_handle="alice",
            posts=[
                Post(
                    post_id="post-1",
                    author_handle="alice",
                    created_at="2026-03-30T10:00:00Z",
                    text="Root tweet text",
                    url="https://x.com/alice/status/post-1",
                ),
                Post(
                    post_id="post-2",
                    author_handle="alice",
                    created_at="2026-03-30T10:05:00Z",
                    text="Reply tweet text",
                    url="https://x.com/alice/status/post-2",
                ),
            ],
        ),
        Thread(
            thread_id="thread-2",
            account_handle="bob",
            posts=[
                Post(
                    post_id="post-3",
                    author_handle="bob",
                    created_at="2026-03-30T11:00:00Z",
                    text="Second root tweet",
                    url="https://x.com/bob/status/post-3",
                )
            ],
        ),
    ]

    queue_items = build_tweet_queue_items(threads=threads)

    assert queue_items == [
        TweetQueueItem(
            tweet_id="thread-1",
            account_handle="alice",
            text="Root tweet text",
            url="https://x.com/alice/status/post-1",
            created_at="2026-03-30T10:00:00Z",
            status="pending",
            cluster_id=None,
            processing_note="",
        ),
        TweetQueueItem(
            tweet_id="thread-2",
            account_handle="bob",
            text="Second root tweet",
            url="https://x.com/bob/status/post-3",
            created_at="2026-03-30T11:00:00Z",
            status="pending",
            cluster_id=None,
            processing_note="",
        ),
    ]
