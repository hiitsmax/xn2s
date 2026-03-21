from __future__ import annotations

from datetime import date, datetime
import json
import math
from pathlib import Path
import re
from typing import Any

from pydantic import BaseModel

from xs2n.schemas.digest import (
    FilteredThread,
    Issue,
    TimelineRecord,
)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


def virality_score(record: TimelineRecord) -> float:
    return (
        (1.0 * math.log1p(record.favorite_count or 0))
        + (2.5 * math.log1p(record.retweet_count or 0))
        + (2.0 * math.log1p(record.reply_count or 0))
        + (2.8 * math.log1p(record.quote_count or 0))
        + (0.15 * math.log1p(record.view_count or 0))
    )


def slugify_issue(value: str, *, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or fallback


def compact_issue_summaries(issues: list[Issue]) -> list[dict[str, Any]]:
    return [
        {
            "slug": issue.slug,
            "title": issue.title,
            "summary": issue.summary,
            "thread_count": issue.thread_count,
        }
        for issue in issues
    ]


def filtered_thread_payload(thread: FilteredThread) -> dict[str, Any]:
    return {
        "thread": thread,
        "source_urls": thread.source_urls,
        "primary_tweet_media_urls": thread.primary_tweet_media_urls,
        "virality_score": sum(virality_score(tweet) for tweet in thread.tweets),
    }

