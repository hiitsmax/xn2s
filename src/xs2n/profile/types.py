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


TimelineEntryKind = Literal["post", "retweet"]


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


@dataclass(slots=True)
class TimelineFetchResult:
    entries: list[TimelineEntry]
    scanned: int
    skipped_old: int


@dataclass(slots=True)
class TimelineMergeResult:
    added: int
    skipped_duplicates: int





