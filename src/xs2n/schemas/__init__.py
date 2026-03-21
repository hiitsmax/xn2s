from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PostInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    post_id: str
    author_handle: str
    created_at: datetime
    text: str
    url: str


class ThreadInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    thread_id: str
    account_handle: str
    posts: list[PostInput] = Field(default_factory=list)

    @property
    def primary_post(self) -> PostInput:
        if not self.posts:
            raise ValueError(f"Thread `{self.thread_id}` has no posts.")
        return self.posts[0]

    @property
    def source_urls(self) -> list[str]:
        return [post.url for post in self.posts if post.url][:3]


class PipelineInput(BaseModel):
    threads: list[ThreadInput] = Field(default_factory=list)


class ThreadFilterResult(BaseModel):
    keep: bool
    filter_reason: str


class FilteredThread(BaseModel):
    thread_id: str
    account_handle: str
    posts: list[PostInput] = Field(default_factory=list)
    keep: bool
    filter_reason: str

    @property
    def primary_post(self) -> PostInput:
        return ThreadInput(
            thread_id=self.thread_id,
            account_handle=self.account_handle,
            posts=self.posts,
        ).primary_post

    @property
    def source_urls(self) -> list[str]:
        return ThreadInput(
            thread_id=self.thread_id,
            account_handle=self.account_handle,
            posts=self.posts,
        ).source_urls


class IssueSelectionResult(BaseModel):
    action: Literal["create_new_issue", "update_existing_issue"]
    issue_slug: str | None = None
    reasoning: str


class IssueWriteResult(BaseModel):
    issue_slug: str
    issue_title: str
    issue_summary: str
    thread_title: str
    thread_summary: str
    why_this_thread_belongs: str


class DigestThread(BaseModel):
    thread_id: str
    account_handle: str
    thread_title: str
    thread_summary: str
    why_this_thread_belongs: str
    filter_reason: str
    source_urls: list[str] = Field(default_factory=list)


class DigestIssue(BaseModel):
    slug: str
    title: str
    summary: str
    threads: list[DigestThread] = Field(default_factory=list)


class DigestOutput(BaseModel):
    generated_at: datetime
    issue_count: int
    issues: list[DigestIssue] = Field(default_factory=list)
