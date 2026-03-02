from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from twikit import Client

from xs2n.profile.auth import LoginPrompt, ensure_authenticated_client
from xs2n.profile.helpers import normalize_handle
from xs2n.profile.types import TimelineEntry, TimelineFetchResult


IMPORT_TIMELINE_PAGE_SIZE = 40
IMPORT_TIMELINE_LIMIT = 5000
DEFAULT_IMPORT_TIMELINE = 500
AUTHENTICATED_ACCOUNT_SENTINEL = "__self__"
TIMELINE_FEEDS = ("Tweets", "Replies")


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


def _timeline_source(tweet_type: str) -> str:
    if tweet_type == "Replies":
        return "replies"
    return "tweets"


def _to_timeline_entry(
    tweet: Any,
    account_handle: str,
    created_at: datetime,
    tweet_type: str,
) -> TimelineEntry | None:
    retweeted_tweet = getattr(tweet, "retweeted_tweet", None)

    tweet_id = str(getattr(tweet, "id", "")).strip()
    if not tweet_id:
        return None

    author = getattr(getattr(tweet, "user", None), "screen_name", None)
    author_handle = _safe_handle(author, account_handle)
    in_reply_to_tweet_id = _tweet_in_reply_to(tweet)
    conversation_id = _tweet_conversation_id(tweet)

    retweeted_tweet_id: str | None = None
    retweeted_author_handle: str | None = None
    retweeted_created_at: str | None = None
    kind = "post"

    if retweeted_tweet is not None:
        kind = "retweet"
        raw_retweeted_id = str(getattr(retweeted_tweet, "id", "")).strip()
        retweeted_tweet_id = raw_retweeted_id or None
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
        timeline_source=_timeline_source(tweet_type),
    )


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

            tweet_id = str(getattr(tweet, "id", "")).strip()
            if not tweet_id or tweet_id in seen_ids:
                continue

            entry = _to_timeline_entry(
                tweet,
                account_handle=account_handle,
                created_at=created_at,
                tweet_type=tweet_type,
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


async def import_timeline_entries(
    account_screen_name: str,
    cookies_file: Path,
    since_datetime: datetime,
    limit: int,
    prompt_login: LoginPrompt,
    page_delay_seconds: float = 0.0,
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

    return TimelineFetchResult(entries=entries, scanned=scanned, skipped_old=skipped_old)


def run_import_timeline_entries(
    account_screen_name: str,
    cookies_file: Path,
    since_datetime: datetime,
    limit: int,
    prompt_login: LoginPrompt,
    page_delay_seconds: float = 0.0,
) -> TimelineFetchResult:
    return asyncio.run(
        import_timeline_entries(
            account_screen_name=account_screen_name,
            cookies_file=cookies_file,
            since_datetime=since_datetime,
            limit=limit,
            prompt_login=prompt_login,
            page_delay_seconds=page_delay_seconds,
        )
    )
