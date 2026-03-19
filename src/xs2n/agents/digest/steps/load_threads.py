from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from xs2n.schemas.digest import ThreadInput, TimelineRecord
from xs2n.storage import load_timeline


def run(*, timeline_file: Path) -> list[ThreadInput]:
    doc = load_timeline(timeline_file)
    raw_entries = doc.get("entries", [])
    if not isinstance(raw_entries, list):
        return []

    grouped: dict[str, list[TimelineRecord]] = {}
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        try:
            record = TimelineRecord.model_validate(item)
        except ValidationError:
            continue
        grouped.setdefault(record.conversation_key, []).append(record)

    threads: list[ThreadInput] = []
    for conversation_id, group in grouped.items():
        ordered_group = sorted(group, key=lambda record: record.created_at)
        source_tweets = [
            record
            for record in ordered_group
            if record.authored_by_source
        ]
        if not source_tweets:
            continue
        primary_tweet = source_tweets[0]

        threads.append(
            ThreadInput(
                thread_id=conversation_id,
                conversation_id=conversation_id,
                account_handle=ordered_group[0].account_handle,
                tweets=ordered_group,
                source_tweet_ids=[record.tweet_id for record in source_tweets],
                context_tweet_ids=[
                    record.tweet_id
                    for record in ordered_group
                    if not record.authored_by_source
                ],
                latest_created_at=max(
                    record.created_at for record in ordered_group
                ),
                primary_tweet_id=primary_tweet.tweet_id,
                primary_tweet=primary_tweet,
            )
        )

    threads.sort(key=lambda thread: thread.latest_created_at, reverse=True)
    return threads
