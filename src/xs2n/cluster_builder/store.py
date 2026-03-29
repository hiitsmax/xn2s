from __future__ import annotations

import json
from pathlib import Path

from xs2n.cluster_builder.schemas import (
    Cluster,
    ClusterMutation,
    QueueFilterStatus,
    TweetQueueItem,
)


def load_tweet_queue(path: str | Path) -> list[TweetQueueItem]:
    queue_path = Path(path)
    if not queue_path.exists():
        return []
    with open(queue_path, "r", encoding="utf-8") as f:
        return [TweetQueueItem.model_validate(item) for item in json.load(f)]


def save_tweet_queue(path: str | Path, items: list[TweetQueueItem]) -> None:
    queue_path = Path(path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(
        json.dumps([item.model_dump(mode="json") for item in items], indent=2) + "\n",
        encoding="utf-8",
    )


def load_cluster_list(path: str | Path) -> list[Cluster]:
    cluster_path = Path(path)
    if not cluster_path.exists():
        return []
    with open(cluster_path, "r", encoding="utf-8") as f:
        return [Cluster.model_validate(item) for item in json.load(f)]


def save_cluster_list(path: str | Path, clusters: list[Cluster]) -> None:
    cluster_path = Path(path)
    cluster_path.parent.mkdir(parents=True, exist_ok=True)
    cluster_path.write_text(
        json.dumps([cluster.model_dump(mode="json") for cluster in clusters], indent=2) + "\n",
        encoding="utf-8",
    )


def get_queue_items_page(
    path: str | Path,
    *,
    status: QueueFilterStatus = "pending",
    limit: int = 5,
    offset: int = 0,
    overview: bool = True,
) -> dict:
    queue = load_tweet_queue(path)
    counts = {
        "pending": sum(item.status == "pending" for item in queue),
        "deferred": sum(item.status == "deferred" for item in queue),
        "done": sum(item.status == "done" for item in queue),
    }
    if status == "all":
        matching_items = queue
    else:
        matching_items = [item for item in queue if item.status == status]

    window = matching_items[offset : offset + limit]
    if overview:
        items = [
            {
                "tweet_id": item.tweet_id,
                "account_handle": item.account_handle,
                "created_at": item.created_at,
                "text_preview": item.text[:120],
                "status": item.status,
            }
            for item in window
        ]
    else:
        items = [item.model_dump(mode="json") for item in window]

    return {
        "counts": counts,
        "status": status,
        "limit": limit,
        "offset": offset,
        "total_matching": len(matching_items),
        "items": items,
    }


def defer_queue_tweet(path: str | Path, *, tweet_id: str, reason: str) -> dict:
    queue = load_tweet_queue(path)
    item = _get_queue_item(queue, tweet_id=tweet_id)
    item.status = "done" if item.status == "deferred" else "deferred"
    item.processing_note = reason
    item.cluster_id = None
    save_tweet_queue(path, queue)
    return item.model_dump(mode="json")


def complete_queue_tweet(
    path: str | Path,
    *,
    tweet_id: str,
    cluster_id: str | None,
    reason: str,
) -> dict:
    queue = load_tweet_queue(path)
    item = _get_queue_item(queue, tweet_id=tweet_id)
    item.status = "done"
    item.cluster_id = cluster_id
    item.processing_note = reason
    save_tweet_queue(path, queue)
    return item.model_dump(mode="json")


def apply_cluster_mutation(path: str | Path, mutation: ClusterMutation) -> dict:
    clusters = load_cluster_list(path)

    if mutation.action == "create_cluster":
        cluster_id = mutation.cluster_id or _generate_cluster_id(clusters)
        cluster = Cluster(
            cluster_id=cluster_id,
            title=mutation.title or "",
            description=mutation.description or "",
            tweet_ids=[],
        )
        clusters.append(cluster)
        save_cluster_list(path, clusters)
        return cluster.model_dump(mode="json")

    cluster = _get_cluster(clusters, cluster_id=mutation.cluster_id)

    if mutation.action == "rename_cluster":
        cluster.title = mutation.title or cluster.title
    elif mutation.action == "set_description":
        cluster.description = mutation.description or cluster.description
    elif mutation.action == "add_tweets":
        existing_ids = set(cluster.tweet_ids)
        cluster.tweet_ids.extend(
            tweet_id for tweet_id in mutation.tweet_ids if tweet_id not in existing_ids
        )
    elif mutation.action == "remove_tweets":
        removal_ids = set(mutation.tweet_ids)
        cluster.tweet_ids = [tweet_id for tweet_id in cluster.tweet_ids if tweet_id not in removal_ids]
    else:
        raise ValueError(f"Unsupported cluster mutation: {mutation.action}")

    save_cluster_list(path, clusters)
    return cluster.model_dump(mode="json")


def _get_queue_item(queue: list[TweetQueueItem], *, tweet_id: str) -> TweetQueueItem:
    for item in queue:
        if item.tweet_id == tweet_id:
            return item
    raise ValueError(f"Tweet `{tweet_id}` was not found in the queue.")


def _get_cluster(clusters: list[Cluster], *, cluster_id: str | None) -> Cluster:
    if cluster_id is None:
        raise ValueError("`cluster_id` is required.")
    for cluster in clusters:
        if cluster.cluster_id == cluster_id:
            return cluster
    raise ValueError(f"Cluster `{cluster_id}` was not found.")


def _generate_cluster_id(clusters: list[Cluster]) -> str:
    return f"cluster_{len(clusters) + 1:03d}"
