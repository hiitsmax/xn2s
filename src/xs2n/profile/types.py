from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class OnboardResult:
    added: int
    skipped_duplicates: int
    invalid: list[str]


@dataclass(slots=True)
class ProfileEntry:
    handle: str
    added_via: str
    added_at: str


TimelineEntryKind = Literal["post", "reply", "retweet"]
TimelineEntrySource = Literal[
    "tweets",
    "replies",
    "thread_parent",
    "thread_reply",
    "home_latest",
]


@dataclass(slots=True)
class TimelineEntry:
    tweet_id: str
    account_handle: str
    author_handle: str
    kind: TimelineEntryKind
    created_at: str
    text: str
    retweeted_tweet_id: str | None
    retweeted_author_handle: str | None
    retweeted_created_at: str | None
    in_reply_to_tweet_id: str | None = None
    conversation_id: str | None = None
    timeline_source: TimelineEntrySource | None = None
    favorite_count: int | None = None
    retweet_count: int | None = None
    reply_count: int | None = None
    quote_count: int | None = None
    view_count: int | None = None
    media: list[dict[str, object]] | None = None


@dataclass(slots=True)
class TimelineFetchResult:
    entries: list[TimelineEntry]
    scanned: int
    skipped_old: int


@dataclass(slots=True)
class TimelineMergeResult:
    added: int
    skipped_duplicates: int

