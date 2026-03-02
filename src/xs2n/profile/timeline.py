from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from twikit import Client
from twikit.errors import NotFound, TweetNotAvailable

from xs2n.profile.auth import LoginPrompt, ensure_authenticated_client
from xs2n.profile.helpers import normalize_handle
from xs2n.profile.types import TimelineEntry, TimelineFetchResult


IMPORT_TIMELINE_PAGE_SIZE = 40
IMPORT_TIMELINE_LIMIT = 5000
DEFAULT_IMPORT_TIMELINE = 500
AUTHENTICATED_ACCOUNT_SENTINEL = "__self__"
TIMELINE_FEEDS = ("Tweets", "Replies")
DEFAULT_THREAD_PARENT_LIMIT = 120
DEFAULT_THREAD_REPLIES_LIMIT = 240
DEFAULT_THREAD_OTHER_REPLIES_LIMIT = 120
THREAD_SOURCE_PARENT = "thread_parent"
THREAD_SOURCE_REPLY = "thread_reply"


def _to_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _tweet_datetime(tweet: Any) -> datetime | None:
    created_at_datetime = getattr(tweet, "created_at_datetime", None)
    if isinstance(created_at_datetime, datetime):
        return _to_utc_datetime(created_at_datetime)

    created_at = getattr(tweet, "created_at", None)
    if isinstance(created_at, str):
        try:
            parsed = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
            return _to_utc_datetime(parsed)
        except ValueError:
            return None
    return None


def _to_text(tweet: Any) -> str:
    full_text = getattr(tweet, "full_text", None)
    if isinstance(full_text, str) and full_text.strip():
        return full_text

    text = getattr(tweet, "text", "")
    return text if isinstance(text, str) else ""


def _safe_handle(raw: str | None, fallback: str) -> str:
    if raw:
        normalized = normalize_handle(raw)
        if normalized is not None:
            return normalized
    return fallback


def _tweet_id(tweet: Any) -> str | None:
    raw_id = str(getattr(tweet, "id", "")).strip()
    return raw_id or None


def _tweet_author_handle(tweet: Any, account_handle: str) -> str:
    author = getattr(getattr(tweet, "user", None), "screen_name", None)
    return _safe_handle(author, account_handle)


def _tweet_in_reply_to(tweet: Any) -> str | None:
    raw_reply_to = getattr(tweet, "in_reply_to", None)
    if raw_reply_to is None:
        return None

    reply_to = str(raw_reply_to).strip()
    return reply_to or None


def _tweet_conversation_id(tweet: Any) -> str | None:
    direct_conversation_id = getattr(tweet, "conversation_id", None)
    if isinstance(direct_conversation_id, str):
        normalized_direct_id = direct_conversation_id.strip()
        if normalized_direct_id:
            return normalized_direct_id

    legacy = getattr(tweet, "_legacy", None)
    if isinstance(legacy, dict):
        raw_legacy_id = legacy.get("conversation_id_str")
        if isinstance(raw_legacy_id, str):
            normalized_legacy_id = raw_legacy_id.strip()
            if normalized_legacy_id:
                return normalized_legacy_id

    return None


def _timeline_source_for_feed(tweet_type: str) -> str:
    if tweet_type == "Replies":
        return "replies"
    return "tweets"


def _to_timeline_entry(
    tweet: Any,
    account_handle: str,
    created_at: datetime,
    timeline_source: str,
) -> TimelineEntry | None:
    retweeted_tweet = getattr(tweet, "retweeted_tweet", None)

    tweet_id = _tweet_id(tweet)
    if tweet_id is None:
        return None

    author_handle = _tweet_author_handle(tweet, account_handle)
    in_reply_to_tweet_id = _tweet_in_reply_to(tweet)
    conversation_id = _tweet_conversation_id(tweet)

    retweeted_tweet_id: str | None = None
    retweeted_author_handle: str | None = None
    retweeted_created_at: str | None = None
    kind = "post"

    if retweeted_tweet is not None:
        kind = "retweet"
        retweeted_tweet_id = _tweet_id(retweeted_tweet)
        retweeted_author = getattr(getattr(retweeted_tweet, "user", None), "screen_name", None)
        if isinstance(retweeted_author, str):
            retweeted_author_handle = normalize_handle(retweeted_author) or retweeted_author.lower()
        retweeted_datetime = _tweet_datetime(retweeted_tweet)
        if retweeted_datetime is not None:
            retweeted_created_at = retweeted_datetime.isoformat()
    elif in_reply_to_tweet_id is not None:
        kind = "reply"

    return TimelineEntry(
        tweet_id=tweet_id,
        account_handle=account_handle,
        author_handle=author_handle,
        kind=kind,
        created_at=created_at.isoformat(),
        text=_to_text(tweet),
        retweeted_tweet_id=retweeted_tweet_id,
        retweeted_author_handle=retweeted_author_handle,
        retweeted_created_at=retweeted_created_at,
        in_reply_to_tweet_id=in_reply_to_tweet_id,
        conversation_id=conversation_id,
        timeline_source=timeline_source,
    )


def _result_len(result: Any) -> int:
    try:
        return len(result)
    except TypeError:
        return 0


def _result_items(result: Any) -> list[Any]:
    try:
        return list(result)
    except TypeError:
        return []


async def _iter_result_items(result: Any, page_delay_seconds: float):
    current = result
    while current is not None:
        batch_items = _result_items(current)
        if not batch_items:
            break

        for item in batch_items:
            yield item

        next_method = getattr(current, "next", None)
        if not callable(next_method):
            break

        if page_delay_seconds > 0:
            await asyncio.sleep(page_delay_seconds)

        next_result = await next_method()
        if _result_len(next_result) == 0:
            break
        current = next_result


async def _get_tweet_detail(
    *,
    client: Client,
    tweet_id: str,
    detail_cache: dict[str, Any | None],
) -> Any | None:
    if tweet_id in detail_cache:
        return detail_cache[tweet_id]

    try:
        tweet = await client.get_tweet_by_id(tweet_id)
    except (TweetNotAvailable, NotFound):
        detail_cache[tweet_id] = None
        return None

    detail_cache[tweet_id] = tweet
    return tweet


async def _collect_timeline_feed_entries(
    *,
    user: Any,
    tweet_type: str,
    account_handle: str,
    since_utc: datetime,
    limit: int,
    seen_ids: set[str],
    page_delay_seconds: float,
) -> TimelineFetchResult:
    batch = await user.get_tweets(
        tweet_type,
        count=min(IMPORT_TIMELINE_PAGE_SIZE, max(1, limit)),
    )
    entries: list[TimelineEntry] = []
    scanned = 0
    skipped_old = 0
    no_progress_pages = 0

    while True:
        if len(batch) == 0:
            break

        page_progress = False
        oldest_in_page: datetime | None = None

        for tweet in batch:
            scanned += 1
            created_at = _tweet_datetime(tweet)
            if created_at is None:
                continue

            if oldest_in_page is None or created_at < oldest_in_page:
                oldest_in_page = created_at

            if created_at < since_utc:
                skipped_old += 1
                continue

            tweet_id = _tweet_id(tweet)
            if tweet_id is None or tweet_id in seen_ids:
                continue

            entry = _to_timeline_entry(
                tweet,
                account_handle=account_handle,
                created_at=created_at,
                timeline_source=_timeline_source_for_feed(tweet_type),
            )
            if entry is None:
                continue

            seen_ids.add(tweet_id)
            entries.append(entry)
            page_progress = True

            if len(entries) >= limit:
                return TimelineFetchResult(entries=entries, scanned=scanned, skipped_old=skipped_old)

        if oldest_in_page is not None and oldest_in_page < since_utc:
            break

        if page_progress:
            no_progress_pages = 0
        else:
            no_progress_pages += 1
            if no_progress_pages >= 2:
                break

        if page_delay_seconds > 0:
            await asyncio.sleep(page_delay_seconds)

        next_batch = await batch.next()
        if len(next_batch) == 0:
            break
        batch = next_batch

    return TimelineFetchResult(entries=entries, scanned=scanned, skipped_old=skipped_old)


async def _hydrate_parent_context(
    *,
    client: Client,
    seed_entries: list[TimelineEntry],
    account_handle: str,
    seen_ids: set[str],
    detail_cache: dict[str, Any | None],
    parent_limit: int,
) -> list[TimelineEntry]:
    if parent_limit <= 0:
        return []

    hydrated_count = 0
    parent_entries: list[TimelineEntry] = []

    for seed_entry in seed_entries:
        parent_id = seed_entry.in_reply_to_tweet_id
        chain_seen: set[str] = set()

        while parent_id is not None and hydrated_count < parent_limit:
            if parent_id in chain_seen:
                break
            chain_seen.add(parent_id)

            parent_tweet = await _get_tweet_detail(
                client=client,
                tweet_id=parent_id,
                detail_cache=detail_cache,
            )
            if parent_tweet is None:
                break

            parent_created_at = _tweet_datetime(parent_tweet)
            if parent_created_at is not None and parent_id not in seen_ids:
                parent_entry = _to_timeline_entry(
                    parent_tweet,
                    account_handle=account_handle,
                    created_at=parent_created_at,
                    timeline_source=THREAD_SOURCE_PARENT,
                )
                if parent_entry is not None:
                    seen_ids.add(parent_entry.tweet_id)
                    parent_entries.append(parent_entry)
                    hydrated_count += 1
                    if hydrated_count >= parent_limit:
                        break

            parent_id = _tweet_in_reply_to(parent_tweet)

    return parent_entries


async def _collect_thread_reply_context(
    *,
    client: Client,
    seed_entries: list[TimelineEntry],
    account_handle: str,
    seen_ids: set[str],
    detail_cache: dict[str, Any | None],
    replies_limit: int,
    other_replies_limit: int,
    page_delay_seconds: float,
) -> list[TimelineEntry]:
    if replies_limit <= 0:
        return []

    other_cap = max(0, min(other_replies_limit, replies_limit))
    queued: set[str] = set()
    queue: deque[str] = deque()

    for entry in seed_entries:
        seed_id = entry.conversation_id or entry.tweet_id
        if seed_id and seed_id not in queued:
            queued.add(seed_id)
            queue.append(seed_id)

    processed: set[str] = set()
    reply_entries: list[TimelineEntry] = []
    added_replies = 0
    added_other_replies = 0

    while queue and added_replies < replies_limit:
        current_id = queue.popleft()
        processed.add(current_id)

        detail_tweet = await _get_tweet_detail(
            client=client,
            tweet_id=current_id,
            detail_cache=detail_cache,
        )
        if detail_tweet is None:
            continue

        replies_result = getattr(detail_tweet, "replies", None)
        if replies_result is None:
            continue

        async for reply_tweet in _iter_result_items(replies_result, page_delay_seconds):
            reply_id = _tweet_id(reply_tweet)
            if reply_id is None:
                continue

            reply_author_handle = _tweet_author_handle(reply_tweet, account_handle)
            is_other_author = reply_author_handle != account_handle
            if is_other_author and added_other_replies >= other_cap:
                continue

            if reply_id not in queued and reply_id not in processed:
                queued.add(reply_id)
                queue.append(reply_id)

            if reply_id in seen_ids:
                continue

            reply_created_at = _tweet_datetime(reply_tweet)
            if reply_created_at is None:
                continue

            reply_entry = _to_timeline_entry(
                reply_tweet,
                account_handle=account_handle,
                created_at=reply_created_at,
                timeline_source=THREAD_SOURCE_REPLY,
            )
            if reply_entry is None:
                continue

            seen_ids.add(reply_entry.tweet_id)
            reply_entries.append(reply_entry)
            added_replies += 1
            if is_other_author:
                added_other_replies += 1

            if added_replies >= replies_limit:
                break

    return reply_entries


async def _expand_thread_context(
    *,
    client: Client,
    base_entries: list[TimelineEntry],
    account_handle: str,
    seen_ids: set[str],
    thread_parent_limit: int,
    thread_replies_limit: int,
    thread_other_replies_limit: int,
    page_delay_seconds: float,
) -> list[TimelineEntry]:
    if thread_parent_limit <= 0 and thread_replies_limit <= 0:
        return []

    detail_cache: dict[str, Any | None] = {}

    parent_entries = await _hydrate_parent_context(
        client=client,
        seed_entries=base_entries,
        account_handle=account_handle,
        seen_ids=seen_ids,
        detail_cache=detail_cache,
        parent_limit=thread_parent_limit,
    )

    reply_entries = await _collect_thread_reply_context(
        client=client,
        seed_entries=[*base_entries, *parent_entries],
        account_handle=account_handle,
        seen_ids=seen_ids,
        detail_cache=detail_cache,
        replies_limit=thread_replies_limit,
        other_replies_limit=thread_other_replies_limit,
        page_delay_seconds=page_delay_seconds,
    )

    expanded_entries = [*parent_entries, *reply_entries]
    expanded_entries.sort(key=lambda entry: entry.created_at, reverse=True)
    return expanded_entries


async def import_timeline_entries(
    account_screen_name: str,
    cookies_file: Path,
    since_datetime: datetime,
    limit: int,
    prompt_login: LoginPrompt,
    page_delay_seconds: float = 0.0,
    thread_parent_limit: int = DEFAULT_THREAD_PARENT_LIMIT,
    thread_replies_limit: int = DEFAULT_THREAD_REPLIES_LIMIT,
    thread_other_replies_limit: int = DEFAULT_THREAD_OTHER_REPLIES_LIMIT,
) -> TimelineFetchResult:
    client = Client("en-US")
    inferred_username = (
        None if account_screen_name == AUTHENTICATED_ACCOUNT_SENTINEL else account_screen_name
    )
    await ensure_authenticated_client(
        client=client,
        cookies_file=cookies_file,
        prompt=prompt_login,
        inferred_username=inferred_username,
    )

    if account_screen_name == AUTHENTICATED_ACCOUNT_SENTINEL:
        user = await client.user()
    else:
        user = await client.get_user_by_screen_name(account_screen_name)

    resolved_account = _safe_handle(getattr(user, "screen_name", None), account_screen_name)
    since_utc = _to_utc_datetime(since_datetime)
    entries: list[TimelineEntry] = []
    seen_ids: set[str] = set()
    scanned = 0
    skipped_old = 0

    for tweet_type in TIMELINE_FEEDS:
        feed_result = await _collect_timeline_feed_entries(
            user=user,
            tweet_type=tweet_type,
            account_handle=resolved_account,
            since_utc=since_utc,
            limit=limit,
            seen_ids=seen_ids,
            page_delay_seconds=page_delay_seconds,
        )
        entries.extend(feed_result.entries)
        scanned += feed_result.scanned
        skipped_old += feed_result.skipped_old

    entries.sort(key=lambda entry: entry.created_at, reverse=True)
    if len(entries) > limit:
        entries = entries[:limit]

    expanded_entries = await _expand_thread_context(
        client=client,
        base_entries=entries,
        account_handle=resolved_account,
        seen_ids={entry.tweet_id for entry in entries},
        thread_parent_limit=thread_parent_limit,
        thread_replies_limit=thread_replies_limit,
        thread_other_replies_limit=thread_other_replies_limit,
        page_delay_seconds=page_delay_seconds,
    )

    all_entries = [*entries, *expanded_entries]
    all_entries.sort(key=lambda entry: entry.created_at, reverse=True)

    return TimelineFetchResult(entries=all_entries, scanned=scanned, skipped_old=skipped_old)


def run_import_timeline_entries(
    account_screen_name: str,
    cookies_file: Path,
    since_datetime: datetime,
    limit: int,
    prompt_login: LoginPrompt,
    page_delay_seconds: float = 0.0,
    thread_parent_limit: int = DEFAULT_THREAD_PARENT_LIMIT,
    thread_replies_limit: int = DEFAULT_THREAD_REPLIES_LIMIT,
    thread_other_replies_limit: int = DEFAULT_THREAD_OTHER_REPLIES_LIMIT,
) -> TimelineFetchResult:
    return asyncio.run(
        import_timeline_entries(
            account_screen_name=account_screen_name,
            cookies_file=cookies_file,
            since_datetime=since_datetime,
            limit=limit,
            prompt_login=prompt_login,
            page_delay_seconds=page_delay_seconds,
            thread_parent_limit=thread_parent_limit,
            thread_replies_limit=thread_replies_limit,
            thread_other_replies_limit=thread_other_replies_limit,
        )
    )
