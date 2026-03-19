from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xs2n.profile.types import TimelineEntry, TimelineMergeResult


DEFAULT_TIMELINE_PATH = Path("data/timeline.json")


def _empty_doc() -> dict[str, Any]:
    return {"entries": []}


def load_timeline(path: Path | None = None) -> dict[str, Any]:
    storage_path = path or DEFAULT_TIMELINE_PATH
    if not storage_path.exists():
        return _empty_doc()

    try:
        data = json.loads(storage_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _empty_doc()

    if not isinstance(data, dict):
        return _empty_doc()
    entries = data.get("entries")
    if not isinstance(entries, list):
        data["entries"] = []
    return data


def save_timeline(doc: dict[str, Any], path: Path | None = None) -> None:
    storage_path = path or DEFAULT_TIMELINE_PATH
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    storage_path.write_text(
        f"{json.dumps(doc, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


def merge_timeline_entries(
    new_entries: list[TimelineEntry],
    path: Path | None = None,
) -> TimelineMergeResult:
    doc = load_timeline(path)
    entries = doc.setdefault("entries", [])

    existing_indexes = {
        str(item.get("tweet_id", "")): index
        for index, item in enumerate(entries)
        if isinstance(item, dict)
    }

    added = 0
    skipped = 0
    for entry in new_entries:
        serialized_entry = {
            "tweet_id": entry.tweet_id,
            "account_handle": entry.account_handle,
            "author_handle": entry.author_handle,
            "kind": entry.kind,
            "created_at": entry.created_at,
            "text": entry.text,
            "retweeted_tweet_id": entry.retweeted_tweet_id,
            "retweeted_author_handle": entry.retweeted_author_handle,
            "retweeted_created_at": entry.retweeted_created_at,
            "in_reply_to_tweet_id": entry.in_reply_to_tweet_id,
            "conversation_id": entry.conversation_id,
            "timeline_source": entry.timeline_source,
            "favorite_count": entry.favorite_count,
            "retweet_count": entry.retweet_count,
            "reply_count": entry.reply_count,
            "quote_count": entry.quote_count,
            "view_count": entry.view_count,
            "media": entry.media or [],
        }

        existing_index = existing_indexes.get(entry.tweet_id)
        if existing_index is not None:
            entries[existing_index] = serialized_entry
            skipped += 1
            continue
        entries.append(serialized_entry)
        existing_indexes[entry.tweet_id] = len(entries) - 1
        added += 1

    save_timeline(doc, path)
    return TimelineMergeResult(added=added, skipped_duplicates=skipped)
