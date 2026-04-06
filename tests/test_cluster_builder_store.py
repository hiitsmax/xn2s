from __future__ import annotations

import json
from pathlib import Path

from xs2n.schemas.clustering import ClusterMutation, TweetQueueItem
from xs2n.tools.cluster_state import (
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
    assert result["items"] == [{"tweet_id": "tweet-2"}]


def test_get_queue_items_page_returns_requested_fields_only(tmp_path: Path) -> None:
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
        fields=["status", "created_at", "text_preview"],
    )

    assert result["total_matching"] == 1
    assert result["items"] == [
        {
            "tweet_id": "tweet-1",
            "status": "deferred",
            "created_at": "2026-03-28T16:00:00Z",
            "text_preview": "Tweet text for tweet-1",
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

    created_message = apply_cluster_mutation(
        cluster_path,
        ClusterMutation(
            action="create_cluster",
            cluster_id="cluster_001",
            title="Inference cost compression",
            description="Tweets about declining inference costs.",
            tweet_ids=["tweet-1"],
        ),
    )
    updated_message = apply_cluster_mutation(
        cluster_path,
        ClusterMutation(
            action="add_tweets",
            cluster_id="cluster_001",
            tweet_ids=["tweet-1", "tweet-2"],
        ),
    )

    clusters = load_cluster_list(cluster_path)

    assert "cluster_001" in created_message
    assert "1 tweet" in created_message
    assert "cluster_001" in updated_message
    assert "1 tweet" in updated_message
    assert len(clusters) == 1
    assert clusters[0].cluster_id == "cluster_001"
    assert clusters[0].title == "Inference cost compression"
    assert clusters[0].description == "Tweets about declining inference costs."
    assert clusters[0].tweet_ids == ["tweet-1", "tweet-2"]


def test_apply_cluster_mutation_generates_cluster_id_when_missing(tmp_path: Path) -> None:
    cluster_path = tmp_path / "cluster_list.json"
    save_cluster_list(cluster_path, [])

    created_message = apply_cluster_mutation(
        cluster_path,
        ClusterMutation(
            action="create_cluster",
            title="Tool-first orchestration",
            description="Tweets about tool-first workflows.",
            tweet_ids=["tweet-1", "tweet-2"],
        ),
    )
    clusters = load_cluster_list(cluster_path)

    assert "cluster_001" in created_message
    assert "2 tweet" in created_message
    assert len(clusters) == 1
    assert clusters[0].cluster_id == "cluster_001"
    assert clusters[0].tweet_ids == ["tweet-1", "tweet-2"]


def test_save_tweet_queue_writes_json_file(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    save_tweet_queue(queue_path, [build_queue_item(tweet_id="tweet-1")])

    raw_queue = json.loads(queue_path.read_text(encoding="utf-8"))

    assert raw_queue[0]["tweet_id"] == "tweet-1"


def test_load_cluster_list_returns_empty_for_blank_file(tmp_path: Path) -> None:
    cluster_path = tmp_path / "cluster_list.json"
    cluster_path.write_text("", encoding="utf-8")

    assert load_cluster_list(cluster_path) == []


def test_load_tweet_queue_returns_empty_for_blank_file(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    queue_path.write_text("", encoding="utf-8")

    assert load_tweet_queue(queue_path) == []
