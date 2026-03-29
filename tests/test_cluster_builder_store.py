from __future__ import annotations

import json
from pathlib import Path

from xs2n.cluster_builder.schemas import ClusterMutation, TweetQueueItem
from xs2n.cluster_builder.store import (
    apply_cluster_mutation,
    complete_queue_tweet,
    defer_queue_tweet,
    get_queue_items_page,
    load_cluster_list,
    load_tweet_queue,
    save_cluster_list,
    save_tweet_queue,
)


def build_queue_item(
    *,
    tweet_id: str,
    status: str = "pending",
    cluster_id: str | None = None,
    processing_note: str = "",
) -> TweetQueueItem:
    return TweetQueueItem(
        tweet_id=tweet_id,
        account_handle="alice",
        text=f"Tweet text for {tweet_id}",
        url=f"https://x.com/alice/status/{tweet_id}",
        created_at="2026-03-28T16:00:00Z",
        status=status,
        cluster_id=cluster_id,
        processing_note=processing_note,
    )


def test_get_queue_items_page_returns_counts_and_preview_window(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    save_tweet_queue(
        queue_path,
        [
            build_queue_item(tweet_id="tweet-1", status="pending"),
            build_queue_item(tweet_id="tweet-2", status="pending"),
            build_queue_item(tweet_id="tweet-3", status="deferred"),
            build_queue_item(tweet_id="tweet-4", status="done"),
        ],
    )

    result = get_queue_items_page(
        queue_path,
        status="pending",
        limit=1,
        offset=1,
        overview=True,
    )

    assert result["counts"] == {
        "pending": 2,
        "deferred": 1,
        "done": 1,
    }
    assert result["status"] == "pending"
    assert result["limit"] == 1
    assert result["offset"] == 1
    assert result["total_matching"] == 2
    assert result["items"] == [
        {
            "tweet_id": "tweet-2",
            "account_handle": "alice",
            "created_at": "2026-03-28T16:00:00Z",
            "text_preview": "Tweet text for tweet-2",
            "status": "pending",
        }
    ]


def test_get_queue_items_page_returns_full_items_when_overview_is_false(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    save_tweet_queue(
        queue_path,
        [
            build_queue_item(tweet_id="tweet-1", status="deferred"),
        ],
    )

    result = get_queue_items_page(
        queue_path,
        status="deferred",
        limit=5,
        offset=0,
        overview=False,
    )

    assert result["total_matching"] == 1
    assert result["items"] == [
        {
            "tweet_id": "tweet-1",
            "account_handle": "alice",
            "text": "Tweet text for tweet-1",
            "url": "https://x.com/alice/status/tweet-1",
            "created_at": "2026-03-28T16:00:00Z",
            "status": "deferred",
            "cluster_id": None,
            "processing_note": "",
        }
    ]


def test_defer_queue_tweet_persists_status_and_note(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    save_tweet_queue(queue_path, [build_queue_item(tweet_id="tweet-1")])

    result = defer_queue_tweet(
        queue_path,
        tweet_id="tweet-1",
        reason="Need more evidence.",
    )

    queue = load_tweet_queue(queue_path)

    assert result["tweet_id"] == "tweet-1"
    assert result["status"] == "deferred"
    assert queue[0].status == "deferred"
    assert queue[0].processing_note == "Need more evidence."
    assert queue[0].cluster_id is None


def test_complete_queue_tweet_persists_status_cluster_and_note(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    save_tweet_queue(queue_path, [build_queue_item(tweet_id="tweet-1")])

    result = complete_queue_tweet(
        queue_path,
        tweet_id="tweet-1",
        cluster_id="cluster_001",
        reason="Clear match.",
    )

    queue = load_tweet_queue(queue_path)

    assert result["tweet_id"] == "tweet-1"
    assert result["status"] == "done"
    assert result["cluster_id"] == "cluster_001"
    assert queue[0].status == "done"
    assert queue[0].cluster_id == "cluster_001"
    assert queue[0].processing_note == "Clear match."


def test_defer_queue_tweet_completes_item_when_it_is_already_deferred(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    save_tweet_queue(
        queue_path,
        [
            build_queue_item(
                tweet_id="tweet-1",
                status="deferred",
                processing_note="Need more evidence.",
            )
        ],
    )

    result = defer_queue_tweet(
        queue_path,
        tweet_id="tweet-1",
        reason="Still too ambiguous.",
    )
    queue = load_tweet_queue(queue_path)

    assert result["status"] == "done"
    assert result["cluster_id"] is None
    assert queue[0].status == "done"
    assert queue[0].processing_note == "Still too ambiguous."


def test_apply_cluster_mutation_creates_and_updates_cluster(tmp_path: Path) -> None:
    cluster_path = tmp_path / "cluster_list.json"
    save_cluster_list(cluster_path, [])

    created = apply_cluster_mutation(
        cluster_path,
        ClusterMutation(
            action="create_cluster",
            cluster_id="cluster_001",
            title="Inference cost compression",
            description="Tweets about declining inference costs.",
        ),
    )
    updated = apply_cluster_mutation(
        cluster_path,
        ClusterMutation(
            action="add_tweets",
            cluster_id="cluster_001",
            tweet_ids=["tweet-1", "tweet-2"],
        ),
    )

    clusters = load_cluster_list(cluster_path)

    assert created["cluster_id"] == "cluster_001"
    assert updated["tweet_ids"] == ["tweet-1", "tweet-2"]
    assert len(clusters) == 1
    assert clusters[0].cluster_id == "cluster_001"
    assert clusters[0].title == "Inference cost compression"
    assert clusters[0].description == "Tweets about declining inference costs."
    assert clusters[0].tweet_ids == ["tweet-1", "tweet-2"]


def test_apply_cluster_mutation_generates_cluster_id_when_missing(tmp_path: Path) -> None:
    cluster_path = tmp_path / "cluster_list.json"
    save_cluster_list(cluster_path, [])

    created = apply_cluster_mutation(
        cluster_path,
        ClusterMutation(
            action="create_cluster",
            title="Tool-first orchestration",
            description="Tweets about tool-first workflows.",
        ),
    )
    clusters = load_cluster_list(cluster_path)

    assert created["cluster_id"] == "cluster_001"
    assert len(clusters) == 1
    assert clusters[0].cluster_id == "cluster_001"


def test_save_tweet_queue_writes_json_file(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    save_tweet_queue(queue_path, [build_queue_item(tweet_id="tweet-1")])

    raw_queue = json.loads(queue_path.read_text(encoding="utf-8"))

    assert raw_queue[0]["tweet_id"] == "tweet-1"
