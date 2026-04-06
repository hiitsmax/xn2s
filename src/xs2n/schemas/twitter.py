from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Post(BaseModel):
    model_config = ConfigDict(extra="ignore")

    post_id: str
    author_handle: str
    created_at: datetime
    text: str
    url: str
    entry_type: Literal["post", "retweet", "quote"] = "post"
    referenced_author_handle: str | None = None
    referenced_text: str | None = None
    referenced_url: str | None = None


class Thread(BaseModel):
    model_config = ConfigDict(extra="ignore")

    thread_id: str
    account_handle: str
    posts: list[Post] = Field(default_factory=list)

    @property
    def primary_post(self) -> Post:
        if not self.posts:
            raise ValueError(f"Thread `{self.thread_id}` has no posts.")
        return self.posts[0]

    @property
    def source_urls(self) -> list[str]:
        return [post.url for post in self.posts if post.url][:3]
