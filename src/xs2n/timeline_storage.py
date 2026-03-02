from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from xs2n.profile.types import TimelineEntry, TimelineMergeResult


DEFAULT_TIMELINE_PATH = Path("data/timeline.yaml")


def _empty_doc() -> dict[str, Any]:
    return {"entries": []}


def load_timeline(path: Path = DEFAULT_TIMELINE_PATH) -> dict[str, Any]:
    if not path.exists():
        return _empty_doc()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return _empty_doc()
    entries = data.get("entries")
    if not isinstance(entries, list):
        data["entries"] = []
    return data


def save_timeline(doc: dict[str, Any], path: Path = DEFAULT_TIMELINE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def merge_timeline_entries(
    new_entries: list[TimelineEntry],
    path: Path = DEFAULT_TIMELINE_PATH,
) -> TimelineMergeResult:
    doc = load_timeline(path)
    entries = doc.setdefault("entries", [])

    existing = {
        str(item.get("tweet_id", ""))
        for item in entries
        if isinstance(item, dict)
    }

    added = 0
    skipped = 0
    for entry in new_entries:
        if entry.tweet_id in existing:
            skipped += 1
            continue
        entries.append(
            {
                "tweet_id": entry.tweet_id,
                "account_handle": entry.account_handle,
                "author_handle": entry.author_handle,
                "kind": entry.kind,
                "created_at": entry.created_at,
                "text": entry.text,
                "retweeted_tweet_id": entry.retweeted_tweet_id,
                "retweeted_author_handle": entry.retweeted_author_handle,
                "retweeted_created_at": entry.retweeted_created_at,
            }
        )
        existing.add(entry.tweet_id)
        added += 1

    save_timeline(doc, path)
    return TimelineMergeResult(added=added, skipped_duplicates=skipped)
