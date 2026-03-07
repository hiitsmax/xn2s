from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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

    @property
    def source_url(self) -> str:
        return f"https://x.com/{self.author_handle}/status/{self.tweet_id}"

    @property
    def conversation_key(self) -> str:
        return self.conversation_id or self.tweet_id

    @property
    def authored_by_source(self) -> bool:
        return self.author_handle == self.account_handle


class CategorySpec(BaseModel):
    slug: str
    label: str
    description: str


class TaxonomyConfig(BaseModel):
    categories: list[CategorySpec]
    drop_categories: list[str] = Field(default_factory=list)


class ThreadInput(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str] = Field(default_factory=list)
    context_tweet_ids: list[str] = Field(default_factory=list)
    latest_created_at: datetime

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


class CategorizationResult(BaseModel):
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str


class CategorizedThread(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str]
    context_tweet_ids: list[str]
    latest_created_at: datetime
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str

    @property
    def source_urls(self) -> list[str]:
        return ThreadInput(**self.model_dump()).source_urls


class FilterResult(BaseModel):
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
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str
    keep: bool
    filter_reason: str

    @property
    def source_urls(self) -> list[str]:
        return ThreadInput(**self.model_dump()).source_urls


class ThreadProcessResult(BaseModel):
    headline: str
    main_claim: str
    why_it_matters: str
    key_entities: list[str] = Field(default_factory=list)
    disagreement_present: bool
    disagreement_summary: str | None = None
    novelty_label: str
    signal_score: int = Field(ge=0, le=100)


class ProcessedThread(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str]
    context_tweet_ids: list[str]
    latest_created_at: datetime
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str
    keep: bool
    filter_reason: str
    headline: str
    main_claim: str
    why_it_matters: str
    key_entities: list[str]
    disagreement_present: bool
    disagreement_summary: str | None = None
    novelty_label: str
    signal_score: int
    virality_score: float
    source_urls: list[str] = Field(default_factory=list)


class IssueAssignmentResult(BaseModel):
    issue_slug: str
    issue_title: str
    issue_summary: str
    why_this_thread_belongs: str


class IssueThread(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str]
    context_tweet_ids: list[str]
    latest_created_at: datetime
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str
    keep: bool
    filter_reason: str
    headline: str
    main_claim: str
    why_it_matters: str
    key_entities: list[str]
    disagreement_present: bool
    disagreement_summary: str | None = None
    novelty_label: str
    signal_score: int
    virality_score: float
    source_urls: list[str] = Field(default_factory=list)
    issue_slug: str
    issue_title: str
    issue_summary: str
    why_this_thread_belongs: str


class Issue(BaseModel):
    slug: str
    title: str
    summary: str
    thread_ids: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class DigestRunResult:
    run_id: str
    run_dir: Path
    digest_path: Path
    thread_count: int
    kept_count: int
    issue_count: int
