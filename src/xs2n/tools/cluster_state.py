from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Annotated

from pydantic import Field
from xs2n.schemas.clustering import (
    Cluster,
    ClusterMutation,
    QueueFilterStatus,
    TweetQueueField,
    TweetQueueItem,
)


_STORE_LOCKS: dict[str, threading.Lock] = {}
_STORE_LOCKS_GUARD = threading.Lock()
DEFAULT_READ_TWEET_FIELDS: tuple[TweetQueueField, ...] = (
    "account_handle",
    "text",
    "url",
    "created_at",
    "status",
    "cluster_id",
    "processing_note",
)


def _get_store_lock(path: str | Path) -> threading.Lock:
    resolved = str(Path(path).resolve())
    with _STORE_LOCKS_GUARD:
        lock = _STORE_LOCKS.get(resolved)
        if lock is None:
            lock = threading.Lock()
            _STORE_LOCKS[resolved] = lock
        return lock


def _load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    raw_text = path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []
    payload = json.loads(raw_text)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in `{path}`.")
    return payload


def _atomic_write_json_list(path: Path, payload: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def load_tweet_queue(path: str | Path) -> list[TweetQueueItem]:
    queue_path = Path(path)
    with _get_store_lock(queue_path):
        return [TweetQueueItem.model_validate(item) for item in _load_json_list(queue_path)]


def save_tweet_queue(path: str | Path, items: list[TweetQueueItem]) -> None:
    queue_path = Path(path)
    with _get_store_lock(queue_path):
        _atomic_write_json_list(
            queue_path,
            [item.model_dump(mode="json") for item in items],
        )


def load_cluster_list(path: str | Path) -> list[Cluster]:
    cluster_path = Path(path)
    with _get_store_lock(cluster_path):
        return [Cluster.model_validate(item) for item in _load_json_list(cluster_path)]


def save_cluster_list(path: str | Path, clusters: list[Cluster]) -> None:
    cluster_path = Path(path)
    with _get_store_lock(cluster_path):
        _atomic_write_json_list(
            cluster_path,
            [cluster.model_dump(mode="json") for cluster in clusters],
        )


def _dedupe_tweet_ids(tweet_ids: list[str]) -> list[str]:
    deduped_ids: list[str] = []
    seen_ids: set[str] = set()
    for tweet_id in tweet_ids:
        if tweet_id in seen_ids:
            continue
        deduped_ids.append(tweet_id)
        seen_ids.add(tweet_id)
    return deduped_ids


def _tweet_count_label(count: int) -> str:
    suffix = "tweet" if count == 1 else "tweets"
    return f"{count} {suffix}"


def _queue_item_field_value(item: TweetQueueItem, *, field: TweetQueueField) -> object:
    if field == "text_preview":
        return item.text[:120]
    return getattr(item, field)


def _queue_item_payload(
    item: TweetQueueItem,
    *,
    fields: list[TweetQueueField] | None,
    full_by_default: bool,
) -> dict[str, object]:
    selected_fields = list(DEFAULT_READ_TWEET_FIELDS if fields is None and full_by_default else fields or [])
    payload: dict[str, object] = {"tweet_id": item.tweet_id}
    for field in selected_fields:
        payload[field] = _queue_item_field_value(item, field=field)
    return payload


def get_queue_items_page(
    path: str | Path,
    *,
    status: QueueFilterStatus = "pending",
    limit: int = 5,
    offset: int = 0,
    fields: list[TweetQueueField] | None = None,
) -> dict:
    queue = load_tweet_queue(path)
    counts = {
        "pending": sum(item.status == "pending" for item in queue),
        "deferred": sum(item.status == "deferred" for item in queue),
        "done": sum(item.status == "done" for item in queue),
    }
    matching_items = queue if status == "all" else [item for item in queue if item.status == status]
    window = matching_items[offset : offset + limit]
    items = [
        _queue_item_payload(
            item,
            fields=fields,
            full_by_default=False,
        )
        for item in window
    ]

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


def apply_cluster_mutation(path: str | Path, mutation: ClusterMutation) -> str:
    clusters = load_cluster_list(path)

    if mutation.action == "create_cluster":
        cluster_id = mutation.cluster_id or _generate_cluster_id(clusters)
        cluster = Cluster(
            cluster_id=cluster_id,
            title=mutation.title or "",
            description=mutation.description or "",
            tweet_ids=_dedupe_tweet_ids(mutation.tweet_ids),
        )
        clusters.append(cluster)
        save_cluster_list(path, clusters)
        return f"Created cluster {cluster.cluster_id} with {_tweet_count_label(len(cluster.tweet_ids))}."

    cluster = _get_cluster(clusters, cluster_id=mutation.cluster_id)

    if mutation.action == "rename_cluster":
        cluster.title = mutation.title or cluster.title
        message = f'Cluster {cluster.cluster_id} renamed to "{cluster.title}".'
    elif mutation.action == "set_description":
        cluster.description = mutation.description or cluster.description
        message = f"Updated description for cluster {cluster.cluster_id}."
    elif mutation.action == "add_tweets":
        existing_ids = set(cluster.tweet_ids)
        added_tweet_ids = [
            tweet_id
            for tweet_id in _dedupe_tweet_ids(mutation.tweet_ids)
            if tweet_id not in existing_ids
        ]
        cluster.tweet_ids.extend(added_tweet_ids)
        message = f"Added {_tweet_count_label(len(added_tweet_ids))} to cluster {cluster.cluster_id}."
    elif mutation.action == "remove_tweets":
        removal_ids = set(mutation.tweet_ids)
        original_count = len(cluster.tweet_ids)
        cluster.tweet_ids = [tweet_id for tweet_id in cluster.tweet_ids if tweet_id not in removal_ids]
        removed_count = original_count - len(cluster.tweet_ids)
        message = f"Removed {_tweet_count_label(removed_count)} from cluster {cluster.cluster_id}."
    else:
        raise ValueError(f"Unsupported cluster mutation: {mutation.action}")

    save_cluster_list(path, clusters)
    return message


def get_queue_items(
    queue_path: str | Path,
    *,
    status: QueueFilterStatus = "pending",
    limit: int = 5,
    offset: int = 0,
    fields: list[TweetQueueField] | None = None,
) -> dict:
    """Return a paginated queue window plus counts by status."""
    return get_queue_items_page(
        queue_path,
        status=status,
        limit=limit,
        offset=offset,
        fields=fields,
    )


def read_tweet(
    queue_path: str | Path,
    *,
    tweet_ids: list[str],
    fields: list[TweetQueueField] | None = None,
) -> list[dict[str, object]]:
    """Return one or more tweet items from the queue, preserving the requested order."""
    if not tweet_ids:
        raise ValueError("`tweet_ids` must include at least one tweet id.")

    queue_by_id = {
        item.tweet_id: item
        for item in load_tweet_queue(queue_path)
    }
    missing_ids = [tweet_id for tweet_id in tweet_ids if tweet_id not in queue_by_id]
    if missing_ids:
        raise ValueError(f"Tweet `{missing_ids[0]}` was not found in the queue.")

    return [
        _queue_item_payload(
            queue_by_id[tweet_id],
            fields=fields,
            full_by_default=True,
        )
        for tweet_id in tweet_ids
    ]


def defer_tweet(queue_path: str | Path, *, tweet_id: str, reason: str) -> str:
    """Mark one tweet as deferred with a short reason."""
    defer_queue_tweet(queue_path, tweet_id=tweet_id, reason=reason)
    return f"Tweet with id {tweet_id} is marked as deferred, go to the next one."


def complete_tweet(
    queue_path: str | Path,
    *,
    tweet_id: str,
    cluster_id: str | None,
    reason: str,
) -> str:
    """Mark one tweet as done and optionally attach a cluster id."""
    complete_queue_tweet(
        queue_path,
        tweet_id=tweet_id,
        cluster_id=cluster_id,
        reason=reason,
    )
    return f"Tweet with id {tweet_id} is marked as done, go to the next one."


def list_clusters(cluster_path: str | Path) -> list[dict]:
    """Return the full current cluster list."""
    return [cluster.model_dump(mode="json") for cluster in load_cluster_list(cluster_path)]


def read_cluster(cluster_path: str | Path, *, cluster_id: str) -> dict:
    """Return one cluster by id."""
    clusters = load_cluster_list(cluster_path)
    for cluster in clusters:
        if cluster.cluster_id == cluster_id:
            return cluster.model_dump(mode="json")
    raise ValueError(f"Cluster `{cluster_id}` was not found.")


def build_cluster_builder_tools(*, queue_path: str | Path, cluster_path: str | Path) -> list:
    def get_queue_items_tool(
        *,
        status: QueueFilterStatus = "pending",
        limit: int = 5,
        offset: int = 0,
        fields: Annotated[
            list[TweetQueueField] | None,
            Field(
                description=(
                    "Optional extra per-item fields to include. `tweet_id` is always "
                    "returned. Leave empty to get only tweet ids."
                )
            ),
        ] = None,
    ) -> dict:
        """Return a paginated queue window plus counts by status."""
        return get_queue_items(
            queue_path,
            status=status,
            limit=limit,
            offset=offset,
            fields=fields,
        )

    def read_tweet_tool(
        *,
        tweet_ids: Annotated[
            list[str],
            Field(description="One or more tweet ids to read from the queue."),
        ],
        fields: Annotated[
            list[TweetQueueField] | None,
            Field(
                description=(
                    "Optional per-tweet fields to include. `tweet_id` is always "
                    "returned. Omit this to get the full tweet info."
                )
            ),
        ] = None,
    ) -> list[dict[str, object]]:
        """Return one or more tweets from the queue, preserving the requested order."""
        return read_tweet(
            queue_path,
            tweet_ids=tweet_ids,
            fields=fields,
        )

    def defer_tweet_tool(*, tweet_id: str, reason: str) -> str:
        """Mark one tweet as deferred with a short reason."""
        return defer_tweet(queue_path, tweet_id=tweet_id, reason=reason)

    def complete_tweet_tool(*, tweet_id: str, cluster_id: str | None = None, reason: str = "") -> str:
        """Mark one tweet as done and optionally attach a cluster id."""
        if cluster_id is not None:
            apply_cluster_mutation(
                cluster_path,
                ClusterMutation(
                    action="add_tweets",
                    cluster_id=cluster_id,
                    tweet_ids=[tweet_id],
                ),
            )
        return complete_tweet(
            queue_path,
            tweet_id=tweet_id,
            cluster_id=cluster_id,
            reason=reason,
        )

    def list_clusters_tool() -> list[dict]:
        """Return the full current cluster list."""
        return list_clusters(cluster_path)

    def read_cluster_tool(*, cluster_id: str) -> dict:
        """Return one cluster by id."""
        return read_cluster(cluster_path, cluster_id=cluster_id)

    def apply_cluster_mutation_tool(*, mutation: ClusterMutation) -> str:
        """Apply one structured cluster mutation and return a short completion message."""
        return apply_cluster_mutation(cluster_path, mutation)

    get_queue_items_tool.__name__ = "get_queue_items"
    read_tweet_tool.__name__ = "read_tweet"
    defer_tweet_tool.__name__ = "defer_tweet"
    complete_tweet_tool.__name__ = "complete_tweet"
    list_clusters_tool.__name__ = "list_clusters"
    read_cluster_tool.__name__ = "read_cluster"
    apply_cluster_mutation_tool.__name__ = "apply_cluster_mutation"

    return [
        get_queue_items_tool,
        read_tweet_tool,
        defer_tweet_tool,
        complete_tweet_tool,
        list_clusters_tool,
        read_cluster_tool,
        apply_cluster_mutation_tool,
    ]


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
