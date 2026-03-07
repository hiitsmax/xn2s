from __future__ import annotations

import math

from ..config import (
    DEFAULT_KEEP_HEAT_STATUSES,
    DEFAULT_MAX_STANDOUT_REPLIES,
    DEFAULT_REPLY_PERCENTILE,
)
from ..models import ConversationCandidate, ThreadState, TimelineRecord


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    bounded = max(0.0, min(100.0, percentile_value))
    sorted_values = sorted(values)
    if bounded == 100.0:
        return sorted_values[-1]
    position = (len(sorted_values) - 1) * (bounded / 100.0)
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))
    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    if lower_index == upper_index:
        return lower_value
    weight = position - lower_index
    return lower_value + (upper_value - lower_value) * weight


def virality_score(record: TimelineRecord) -> float:
    return (
        (1.0 * math.log1p(record.favorite_count or 0))
        + (2.5 * math.log1p(record.retweet_count or 0))
        + (2.0 * math.log1p(record.reply_count or 0))
        + (2.8 * math.log1p(record.quote_count or 0))
        + (0.15 * math.log1p(record.view_count or 0))
    )


def aggregate_engagement(records: list[TimelineRecord]) -> dict[str, int]:
    return {
        "favorite_count": sum(record.favorite_count or 0 for record in records),
        "retweet_count": sum(record.retweet_count or 0 for record in records),
        "reply_count": sum(record.reply_count or 0 for record in records),
        "quote_count": sum(record.quote_count or 0 for record in records),
        "view_count": sum(record.view_count or 0 for record in records),
    }


def select_report_records(
    *,
    records: list[TimelineRecord],
    previous_threads: dict[str, ThreadState],
    fresh_cutoff,
) -> list[TimelineRecord]:
    tracked_conversations = {
        conversation_id
        for conversation_id, state in previous_threads.items()
        if state.heat_status in DEFAULT_KEEP_HEAT_STATUSES
    }
    selected = [
        record
        for record in records
        if record.created_at >= fresh_cutoff or record.conversation_key in tracked_conversations
    ]
    selected.sort(key=lambda record: record.created_at, reverse=True)
    return selected


def build_candidates(records: list[TimelineRecord]) -> list[ConversationCandidate]:
    grouped: dict[str, list[TimelineRecord]] = {}
    for record in records:
        grouped.setdefault(record.conversation_key, []).append(record)

    external_reply_scores = [
        virality_score(record)
        for record in records
        if record.kind == "reply" and not record.authored_by_source
    ]
    standout_threshold = percentile(external_reply_scores, DEFAULT_REPLY_PERCENTILE)

    candidates: list[ConversationCandidate] = []
    for conversation_id, group in grouped.items():
        sorted_group = sorted(group, key=lambda record: record.created_at)
        account_handle = sorted_group[0].account_handle
        included_ids = {
            record.tweet_id
            for record in sorted_group
            if record.authored_by_source
        }
        selection_reasons: set[str] = set()
        if included_ids:
            selection_reasons.add("source_authored")

        records_by_id = {record.tweet_id: record for record in sorted_group}
        for record in sorted_group:
            if not record.authored_by_source:
                continue
            if record.in_reply_to_tweet_id and record.in_reply_to_tweet_id in records_by_id:
                included_ids.add(record.in_reply_to_tweet_id)
                selection_reasons.add("author_reply_context")

        standout_replies = [
            record
            for record in sorted_group
            if record.kind == "reply"
            and not record.authored_by_source
            and virality_score(record) >= standout_threshold
        ]
        if not standout_replies:
            fallback_replies = [
                record
                for record in sorted_group
                if record.kind == "reply" and not record.authored_by_source
            ]
            fallback_replies.sort(key=virality_score, reverse=True)
            standout_replies = fallback_replies[:1]

        standout_replies = sorted(
            standout_replies,
            key=virality_score,
            reverse=True,
        )[:DEFAULT_MAX_STANDOUT_REPLIES]

        for reply in standout_replies:
            included_ids.add(reply.tweet_id)
        if standout_replies:
            selection_reasons.add("standout_replies")

        filtered_group = [
            record for record in sorted_group if record.tweet_id in included_ids
        ]
        if not filtered_group:
            filtered_group = sorted_group[:1]
            selection_reasons.add("fallback_single")

        candidates.append(
            ConversationCandidate(
                unit_id=conversation_id,
                conversation_id=conversation_id,
                account_handle=account_handle,
                tweets=filtered_group,
                standout_reply_ids=[reply.tweet_id for reply in standout_replies],
                standout_reply_threshold=standout_threshold,
                selected_by=sorted(selection_reasons),
            )
        )

    candidates.sort(
        key=lambda candidate: max(tweet.created_at for tweet in candidate.tweets),
        reverse=True,
    )
    return candidates
