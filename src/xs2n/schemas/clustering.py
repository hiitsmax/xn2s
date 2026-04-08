from typing import Literal

from pydantic import BaseModel, Field


TweetQueueStatus = Literal["pending", "deferred", "done"]
QueueFilterStatus = Literal["pending", "deferred", "done", "all"]
TweetQueueField = Literal[
    "account_handle",
    "text",
    "text_preview",
    "quote_text",
    "image_description",
    "url_hint",
    "url",
    "created_at",
    "status",
    "cluster_id",
    "processing_note",
]
ClusterMutationAction = Literal[
    "create_cluster",
    "rename_cluster",
    "set_description",
    "add_tweets",
    "remove_tweets",
]


class TweetQueueItem(BaseModel):
    tweet_id: str
    account_handle: str
    text: str
    quote_text: str = ""
    image_description: str = ""
    url_hint: str = ""
    url: str
    created_at: str
    status: TweetQueueStatus = "pending"
    cluster_id: str | None = None
    processing_note: str = ""


class Cluster(BaseModel):
    cluster_id: str
    title: str = ""
    description: str = ""
    tweet_ids: list[str] = Field(default_factory=list)


class ClusterMutation(BaseModel):
    action: ClusterMutationAction
    cluster_id: str | None = None
    title: str | None = None
    description: str | None = None
    tweet_ids: list[str] = Field(default_factory=list)
