from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TimelineMedia(BaseModel):
    model_config = ConfigDict(extra="ignore")

    media_url: str
    media_type: str
    width: int | None = None
    height: int | None = None
    expanded_url: str | None = None


class TimelineRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tweet_id: str
    account_handle: str
    author_handle: str
    kind: Literal["post", "reply", "retweet"]
    created_at: datetime
    text: str
    retweeted_tweet_id: str | None = None
    retweeted_author_handle: str | None = None
    retweeted_created_at: str | None = None
    in_reply_to_tweet_id: str | None = None
    conversation_id: str | None = None
    timeline_source: str | None = None
    favorite_count: int | None = None
    retweet_count: int | None = None
    reply_count: int | None = None
    quote_count: int | None = None
    view_count: int | None = None
    media: list[TimelineMedia] = Field(default_factory=list)

    @property
    def source_url(self) -> str:
        return f"https://x.com/{self.author_handle}/status/{self.tweet_id}"

    @property
    def conversation_key(self) -> str:
        return self.conversation_id or self.tweet_id

    @property
    def authored_by_source(self) -> bool:
        return self.author_handle == self.account_handle


class ThreadInput(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str] = Field(default_factory=list)
    context_tweet_ids: list[str] = Field(default_factory=list)
    latest_created_at: datetime
    primary_tweet_id: str
    primary_tweet: TimelineRecord

    @property
    def source_urls(self) -> list[str]:
        urls = [
            tweet.source_url
            for tweet in self.tweets
            if tweet.tweet_id in self.source_tweet_ids
        ]
        if urls:
            return urls[:3]
        if self.tweets:
            return [self.tweets[0].source_url]
        return []

    @property
    def primary_tweet_media_urls(self) -> list[str]:
        return [media.media_url for media in self.primary_tweet.media if media.media_url]


class ThreadFilterResult(BaseModel):
    keep: bool
    filter_reason: str


class FilteredThread(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str]
    context_tweet_ids: list[str]
    latest_created_at: datetime
    primary_tweet_id: str
    primary_tweet: TimelineRecord
    keep: bool
    filter_reason: str

    @property
    def source_urls(self) -> list[str]:
        return ThreadInput(**self.model_dump()).source_urls

    @property
    def primary_tweet_media_urls(self) -> list[str]:
        return ThreadInput(**self.model_dump()).primary_tweet_media_urls


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


class IssueThread(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str]
    context_tweet_ids: list[str]
    latest_created_at: datetime
    primary_tweet_id: str
    primary_tweet: TimelineRecord
    keep: bool
    filter_reason: str
    issue_slug: str
    issue_title: str
    issue_summary: str
    thread_title: str
    thread_summary: str
    why_this_thread_belongs: str

    @property
    def source_urls(self) -> list[str]:
        return ThreadInput(**self.model_dump(exclude={"keep", "filter_reason", "issue_slug", "issue_title", "issue_summary", "thread_title", "thread_summary", "why_this_thread_belongs"})).source_urls


class Issue(BaseModel):
    slug: str
    title: str
    summary: str
    thread_ids: list[str] = Field(default_factory=list)
    thread_count: int = 0


class PhaseTrace(BaseModel):
    name: str
    status: Literal["completed", "failed"]
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    input_count: int = 0
    output_count: int = 0
    artifact_paths: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None


class LLMCallTrace(BaseModel):
    call_id: int
    phase: str
    item_id: str | None = None
    schema_name: str
    model: str
    credential_source: str | None = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    prompt: str
    payload: Any
    image_urls: list[str] = Field(default_factory=list)
    output_text: str | None = None
    result: Any | None = None
    response_id: str | None = None
    request_id: str | None = None
    usage: Any | None = None
    error_type: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class IssueReportRunResult:
    run_id: str
    run_dir: Path
    thread_count: int
    kept_count: int
    issue_count: int
