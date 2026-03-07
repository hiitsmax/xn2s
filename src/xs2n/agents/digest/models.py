from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

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

    @property
    def total_raw_engagement(self) -> int:
        return (
            (self.favorite_count or 0)
            + (self.retweet_count or 0)
            + (self.reply_count or 0)
            + (self.quote_count or 0)
            + (self.view_count or 0)
        )


class CategorySpec(BaseModel):
    slug: str
    label: str
    description: str


class TaxonomyConfig(BaseModel):
    categories: list[CategorySpec]
    drop_categories: list[str] = Field(default_factory=list)


class ConversationCandidate(BaseModel):
    unit_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    standout_reply_ids: list[str] = Field(default_factory=list)
    standout_reply_threshold: float
    selected_by: list[str] = Field(default_factory=list)


class AssemblyResult(BaseModel):
    title: str
    summary: str
    include_tweet_ids: list[str]
    highlight_tweet_ids: list[str] = Field(default_factory=list)
    why_this_is_one_unit: str


class AssembledUnit(BaseModel):
    unit_id: str
    conversation_id: str
    account_handle: str
    title: str
    summary: str
    why_this_is_one_unit: str
    tweets: list[TimelineRecord]
    included_tweet_ids: list[str]
    highlight_tweet_ids: list[str]
    standout_reply_ids: list[str] = Field(default_factory=list)


class CategorizationResult(BaseModel):
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str


class CategorizedUnit(BaseModel):
    unit_id: str
    conversation_id: str
    account_handle: str
    title: str
    summary: str
    why_this_is_one_unit: str
    tweets: list[TimelineRecord]
    included_tweet_ids: list[str]
    highlight_tweet_ids: list[str]
    standout_reply_ids: list[str]
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str


class FilteredUnit(BaseModel):
    unit_id: str
    conversation_id: str
    account_handle: str
    title: str
    summary: str
    why_this_is_one_unit: str
    tweets: list[TimelineRecord]
    included_tweet_ids: list[str]
    highlight_tweet_ids: list[str]
    standout_reply_ids: list[str]
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str
    keep: bool
    filter_reason: str


class SignalResult(BaseModel):
    headline: str
    main_claim: str
    why_it_matters: str
    key_entities: list[str] = Field(default_factory=list)
    disagreement_present: bool
    disagreement_summary: str | None = None
    novelty_label: str
    signal_score: int = Field(ge=0, le=100)


class SignalUnit(BaseModel):
    unit_id: str
    conversation_id: str
    account_handle: str
    title: str
    summary: str
    category: str
    subcategory: str | None = None
    editorial_angle: str
    tweets: list[TimelineRecord]
    included_tweet_ids: list[str]
    highlight_tweet_ids: list[str]
    standout_reply_ids: list[str]
    headline: str
    main_claim: str
    why_it_matters: str
    key_entities: list[str]
    disagreement_present: bool
    disagreement_summary: str | None = None
    novelty_label: str
    signal_score: int
    virality_score: float
    engagement_totals: dict[str, int]
    heat_status: Literal["heated", "still_active", "cooling_off", "watch"]
    momentum: Literal["rising", "steady", "cooling"]
    source_urls: list[str]


class IssueCluster(BaseModel):
    title: str
    summary: str
    unit_ids: list[str]


class IssueClusterResult(BaseModel):
    issues: list[IssueCluster] = Field(default_factory=list)


class ThreadState(BaseModel):
    title: str
    heat_status: Literal["heated", "still_active", "cooling_off", "watch"]
    momentum: Literal["rising", "steady", "cooling"]
    virality_score: float
    disagreement_present: bool
    last_seen_at: datetime
    source_urls: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class DigestRunResult:
    run_id: str
    run_dir: Path
    digest_path: Path
    selected_count: int
    kept_count: int
    issue_count: int
    heated_count: int


class DigestBackend(Protocol):
    def assemble_conversation(
        self,
        *,
        taxonomy: TaxonomyConfig,
        candidate: ConversationCandidate,
    ) -> AssemblyResult: ...

    def categorize_conversation(
        self,
        *,
        taxonomy: TaxonomyConfig,
        unit: AssembledUnit,
    ) -> CategorizationResult: ...

    def extract_signal(
        self,
        *,
        taxonomy: TaxonomyConfig,
        unit: FilteredUnit,
    ) -> SignalResult: ...

    def cluster_issues(
        self,
        *,
        taxonomy: TaxonomyConfig,
        units: list[SignalUnit],
    ) -> IssueClusterResult: ...
