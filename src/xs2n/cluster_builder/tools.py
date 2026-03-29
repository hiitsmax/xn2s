from __future__ import annotations

from pathlib import Path

from xs2n.cluster_builder.schemas import ClusterMutation
from xs2n.cluster_builder.store import (
    apply_cluster_mutation as apply_store_cluster_mutation,
    complete_queue_tweet,
    defer_queue_tweet,
    get_queue_items_page,
    load_cluster_list,
    load_tweet_queue,
)


def get_queue_items(
    queue_path: str | Path,
    *,
    status: str = "pending",
    limit: int = 5,
    offset: int = 0,
    overview: bool = True,
) -> dict:
    """Return a paginated queue window plus counts by status."""
    return get_queue_items_page(
        queue_path,
        status=status,
        limit=limit,
        offset=offset,
        overview=overview,
    )


def read_tweet(queue_path: str | Path, *, tweet_id: str) -> dict:
    """Return one full tweet item from the queue by id."""
    queue = load_tweet_queue(queue_path)
    for item in queue:
        if item.tweet_id == tweet_id:
            return item.model_dump(mode="json")
    raise ValueError(f"Tweet `{tweet_id}` was not found in the queue.")


def defer_tweet(queue_path: str | Path, *, tweet_id: str, reason: str) -> dict:
    """Mark one tweet as deferred with a short reason."""
    return defer_queue_tweet(queue_path, tweet_id=tweet_id, reason=reason)


def complete_tweet(
    queue_path: str | Path,
    *,
    tweet_id: str,
    cluster_id: str | None,
    reason: str,
) -> dict:
    """Mark one tweet as done and optionally attach a cluster id."""
    return complete_queue_tweet(
        queue_path,
        tweet_id=tweet_id,
        cluster_id=cluster_id,
        reason=reason,
    )


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


def apply_cluster_mutation(cluster_path: str | Path, *, mutation: ClusterMutation) -> dict:
    """Apply one structured cluster mutation and return the updated cluster."""
    return apply_store_cluster_mutation(cluster_path, mutation)


def build_cluster_builder_tools(*, queue_path: str | Path, cluster_path: str | Path) -> list:
    def get_queue_items_tool(
        *,
        status: str = "pending",
        limit: int = 5,
        offset: int = 0,
        overview: bool = True,
    ) -> dict:
        """Return a paginated queue window plus counts by status."""
        return get_queue_items(
            queue_path,
            status=status,
            limit=limit,
            offset=offset,
            overview=overview,
        )

    def read_tweet_tool(*, tweet_id: str) -> dict:
        """Return one full tweet item from the queue by id."""
        return read_tweet(queue_path, tweet_id=tweet_id)

    def defer_tweet_tool(*, tweet_id: str, reason: str) -> dict:
        """Mark one tweet as deferred with a short reason."""
        return defer_tweet(queue_path, tweet_id=tweet_id, reason=reason)

    def complete_tweet_tool(*, tweet_id: str, cluster_id: str | None = None, reason: str = "") -> dict:
        """Mark one tweet as done and optionally attach a cluster id."""
        if cluster_id is not None:
            apply_cluster_mutation(
                cluster_path,
                mutation=ClusterMutation(
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

    def apply_cluster_mutation_tool(*, mutation: ClusterMutation) -> dict:
        """Apply one structured cluster mutation and return the updated cluster."""
        return apply_cluster_mutation(cluster_path, mutation=mutation)

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
