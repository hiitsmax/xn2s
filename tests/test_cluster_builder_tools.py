from __future__ import annotations

from pathlib import Path

from xs2n.cluster_builder.schemas import Cluster, ClusterMutation, TweetQueueItem
from xs2n.cluster_builder.store import save_cluster_list, save_tweet_queue
from xs2n.cluster_builder.tools import (
    apply_cluster_mutation,
    build_cluster_builder_tools,
    complete_tweet,
    defer_tweet,
    get_queue_items,
    list_clusters,
    read_cluster,
    read_tweet,
)


def build_queue_item(*, tweet_id: str, status: str = "pending") -> TweetQueueItem:
    return TweetQueueItem(
        tweet_id=tweet_id,
        account_handle="alice",
        text=f"Full text for {tweet_id}",
        url=f"https://x.com/alice/status/{tweet_id}",
        created_at="2026-03-28T16:00:00Z",
        status=status,
    )


def test_get_queue_items_returns_counts_and_paginated_items(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    save_tweet_queue(
        queue_path,
        [
            build_queue_item(tweet_id="tweet-1", status="pending"),
            build_queue_item(tweet_id="tweet-2", status="pending"),
            build_queue_item(tweet_id="tweet-3", status="done"),
        ],
    )

    result = get_queue_items(
        queue_path,
        status="pending",
        limit=1,
        offset=1,
        overview=True,
    )

    assert result["counts"]["pending"] == 2
    assert result["items"][0]["tweet_id"] == "tweet-2"


def test_read_tweet_returns_full_queue_item(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    save_tweet_queue(queue_path, [build_queue_item(tweet_id="tweet-1")])

    result = read_tweet(queue_path, tweet_id="tweet-1")

    assert result["tweet_id"] == "tweet-1"
    assert result["text"] == "Full text for tweet-1"


def test_defer_tweet_updates_queue_state(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    save_tweet_queue(queue_path, [build_queue_item(tweet_id="tweet-1")])

    result = defer_tweet(
        queue_path,
        tweet_id="tweet-1",
        reason="Weak evidence.",
    )

    assert result["status"] == "deferred"
    assert result["processing_note"] == "Weak evidence."


def test_complete_tweet_updates_queue_state(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    save_tweet_queue(queue_path, [build_queue_item(tweet_id="tweet-1")])

    result = complete_tweet(
        queue_path,
        tweet_id="tweet-1",
        cluster_id="cluster_001",
        reason="Confident match.",
    )

    assert result["status"] == "done"
    assert result["cluster_id"] == "cluster_001"


def test_list_clusters_and_read_cluster_return_cluster_state(tmp_path: Path) -> None:
    cluster_path = tmp_path / "cluster_list.json"
    save_cluster_list(
        cluster_path,
        [
            Cluster(
                cluster_id="cluster_001",
                title="Inference costs",
                description="Serving cost cluster.",
                tweet_ids=["tweet-1"],
            )
        ],
    )

    clusters = list_clusters(cluster_path)
    cluster = read_cluster(cluster_path, cluster_id="cluster_001")

    assert clusters[0]["cluster_id"] == "cluster_001"
    assert cluster["title"] == "Inference costs"


def test_apply_cluster_mutation_forwards_validated_mutation(tmp_path: Path) -> None:
    cluster_path = tmp_path / "cluster_list.json"
    save_cluster_list(cluster_path, [])

    result = apply_cluster_mutation(
        cluster_path,
        mutation=ClusterMutation(
            action="create_cluster",
            cluster_id="cluster_001",
            title="Inference costs",
            description="Serving cost cluster.",
        ),
    )

    assert result["cluster_id"] == "cluster_001"


def test_bound_complete_tweet_adds_tweet_to_cluster_membership(tmp_path: Path) -> None:
    queue_path = tmp_path / "tweet_queue.json"
    cluster_path = tmp_path / "cluster_list.json"
    save_tweet_queue(queue_path, [build_queue_item(tweet_id="tweet-1")])
    save_cluster_list(
        cluster_path,
        [
            Cluster(
                cluster_id="cluster_001",
                title="Inference costs",
                description="Serving cost cluster.",
                tweet_ids=[],
            )
        ],
    )
    tools = {
        tool.__name__: tool
        for tool in build_cluster_builder_tools(
            queue_path=queue_path,
            cluster_path=cluster_path,
        )
    }

    result = tools["complete_tweet"](
        tweet_id="tweet-1",
        cluster_id="cluster_001",
        reason="Confident match.",
    )
    cluster = read_cluster(cluster_path, cluster_id="cluster_001")

    assert result["status"] == "done"
    assert cluster["tweet_ids"] == ["tweet-1"]
