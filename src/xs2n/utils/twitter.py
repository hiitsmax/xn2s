from __future__ import annotations

import html as _html
import json
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
import warnings

import feedparser
import requests

from xs2n.schemas.clustering import TweetQueueItem
from xs2n.schemas.twitter import Post, Thread


NITTER_INSTANCES: list[str] = [
    "nitter.net",
    "xcancel.com",
    "nitter.privacyredirect.com",
    "nitter.poast.org",
    "lightbrd.com",
    "nitter.space",
    "nitter.tiekoetter.com",
    "nitter.catsarch.com",
]

_STATUS_ID_RE = re.compile(r"/status/(\d+)")
_STATUS_TARGET_RE = re.compile(r"/([^/]+)/status/(\d+)")
_QUOTE_BLOCK_RE = re.compile(r"<blockquote>(.*?)</blockquote>", re.IGNORECASE | re.DOTALL)
_QUOTE_FOOTER_RE = re.compile(r"<footer>.*?</footer>", re.IGNORECASE | re.DOTALL)
_QUOTE_HEADER_RE = re.compile(r"<b>.*?</b>", re.IGNORECASE | re.DOTALL)
_QUOTE_LINK_RE = re.compile(r'<a href="([^"]+/status/\d+[^"]*)"', re.IGNORECASE)
_QUOTE_HANDLE_RE = re.compile(r"\(@([A-Za-z0-9_]+)\)")
_HR_RE = re.compile(r"<hr\s*/?>", re.IGNORECASE)
_REQUEST_TIMEOUT_S = 10


class _HtmlTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return _html.unescape("".join(self._parts)).strip()


def _report(report_progress: Callable[[str], None] | None, message: str) -> None:
    if report_progress is not None:
        report_progress(message)


def _strip_html(text: str) -> str:
    extractor = _HtmlTextExtractor()
    extractor.feed(text)
    return extractor.get_text()


def _extract_post_id(link: str) -> str | None:
    match = _STATUS_ID_RE.search(link)
    return match.group(1) if match else None


def _extract_status_target(link: str) -> tuple[str, str] | None:
    match = _STATUS_TARGET_RE.search(link)
    if not match:
        return None
    return match.group(1), match.group(2)


def _normalize_handle(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]
    return cleaned or None


def _parse_entry_date(entry: feedparser.FeedParserDict) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            return datetime(*parsed[:6], tzinfo=UTC)

    for key in ("published", "updated"):
        raw: str = entry.get(key, "")
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(UTC)
            except Exception:
                pass

    return None


def _x_status_url(handle: str, post_id: str) -> str:
    return f"https://x.com/{handle}/status/{post_id}"


def _canonical_status_url(link: str, *, fallback_handle: str) -> str | None:
    target = _extract_status_target(link)
    if target is not None:
        return _x_status_url(target[0], target[1])
    post_id = _extract_post_id(link)
    if not post_id:
        return None
    return _x_status_url(fallback_handle, post_id)


def _extract_quote_parts(raw_text: str) -> tuple[str, str | None, str | None, str | None]:
    main_html = _HR_RE.split(raw_text, maxsplit=1)[0]
    main_text = _strip_html(main_html)

    match = _QUOTE_BLOCK_RE.search(raw_text)
    if not match:
        return main_text, None, None, None

    quote_html = match.group(1)
    quote_handle_match = _QUOTE_HANDLE_RE.search(quote_html)
    referenced_author_handle = quote_handle_match.group(1) if quote_handle_match else None

    quote_link_match = _QUOTE_LINK_RE.search(quote_html)
    referenced_url = (
        _canonical_status_url(
            quote_link_match.group(1),
            fallback_handle=referenced_author_handle or "",
        )
        if quote_link_match
        else None
    )

    quote_body_html = _QUOTE_FOOTER_RE.sub("", quote_html)
    quote_body_html = _QUOTE_HEADER_RE.sub("", quote_body_html)
    referenced_text = _strip_html(quote_body_html) or None

    return main_text, referenced_author_handle, referenced_url, referenced_text


def _build_thread_from_entry(
    handle: str,
    entry: feedparser.FeedParserDict,
) -> Thread | None:
    link: str = entry.get("link", "")
    status_target = _extract_status_target(link)
    if status_target is None:
        return None
    link_handle, post_id = status_target

    created_at = _parse_entry_date(entry)
    if created_at is None:
        return None

    title: str = entry.get("title") or ""
    raw_text: str = entry.get("summary") or title or ""

    entry_type = "post"
    referenced_author_handle = None
    referenced_text = None
    referenced_url = None

    if title.lower().startswith(f"rt by @{handle.lower()}:"):
        entry_type = "retweet"
        text = _strip_html(raw_text)
        referenced_author_handle = _normalize_handle(entry.get("author")) or link_handle
        referenced_text = text or None
        referenced_url = _x_status_url(link_handle, post_id)
    elif "<blockquote>" in raw_text.lower():
        entry_type = "quote"
        text, referenced_author_handle, referenced_url, referenced_text = _extract_quote_parts(
            raw_text
        )
    else:
        text = _strip_html(raw_text)

    post = Post(
        post_id=post_id,
        author_handle=handle,
        created_at=created_at,
        text=text,
        url=_x_status_url(link_handle, post_id),
        entry_type=entry_type,
        referenced_author_handle=referenced_author_handle,
        referenced_text=referenced_text,
        referenced_url=referenced_url,
    )
    return Thread(
        thread_id=post_id,
        account_handle=handle,
        posts=[post],
    )


def _fetch_feed(handle: str, instance: str) -> feedparser.FeedParserDict | None:
    url = f"https://{instance}/{handle}/rss"
    try:
        response = requests.get(
            url,
            timeout=_REQUEST_TIMEOUT_S,
            headers={"User-Agent": "xs2n/1.0"},
        )
        if response.status_code != 200:
            return None
        return feedparser.parse(response.text)
    except requests.RequestException:
        return None


def _get_threads_for_handle(
    handle: str,
    since_date: datetime,
    report_progress: Callable[[str], None] | None = None,
) -> list[Thread]:
    for instance in NITTER_INSTANCES:
        _report(report_progress, f"{handle}: trying {instance}")
        candidate = _fetch_feed(handle, instance)
        if candidate is None:
            _report(report_progress, f"{handle}: {instance} returned no feed data.")
            continue
        entries = candidate.get("entries") or []
        if not entries:
            _report(report_progress, f"{handle}: {instance} returned an empty RSS feed.")
            continue
        threads: list[Thread] = []
        valid_tweet_items = 0
        for entry in entries:
            thread = _build_thread_from_entry(handle, entry)
            if thread is None:
                continue
            valid_tweet_items += 1
            if thread.primary_post.created_at < since_date:
                continue
            threads.append(thread)
        if valid_tweet_items == 0:
            _report(
                report_progress,
                f"{handle}: {instance} returned {len(entries)} RSS entr"
                f"{'y' if len(entries) == 1 else 'ies'} but 0 valid tweet items; "
                "skipping placeholder or unsupported RSS feed.",
            )
            continue
        _report(
            report_progress,
            f"{handle}: using {instance} ({len(entries)} feed entr"
            f"{'y' if len(entries) == 1 else 'ies'}, "
            f"{valid_tweet_items} valid tweet item(s), {len(threads)} recent thread(s)).",
        )
        return threads

    _report(report_progress, f"{handle}: no usable RSS feed found on any configured instance.")
    return []


def get_nitter_rss_threads(
    *,
    handles: list[str],
    since_date: datetime,
    report_progress: Callable[[str], None] | None = None,
) -> list[Thread]:
    threads: list[Thread] = []
    for handle in handles:
        threads.extend(
            _get_threads_for_handle(
                handle,
                since_date,
                report_progress=report_progress,
            )
        )
    return threads


def get_twitter_handles(path: str | Path) -> list[str]:
    with open(path, "r", encoding="utf-8") as handle_file:
        return json.load(handle_file)["handles"]


def get_twitter_threads_from_handles(
    handles: list[str],
    since_date: datetime,
    report_progress: Callable[[str], None] | None = None,
) -> list[Thread]:
    threads: list[Thread] = []
    empty_handles: list[str] = []
    _report(
        report_progress,
        "Fetching recent tweets from Nitter RSS for "
        f"{len(handles)} handle(s) since {since_date.isoformat()}.",
    )

    for index, handle in enumerate(handles, start=1):
        _report(report_progress, f"[{index}/{len(handles)}] {handle}: starting RSS fetch.")
        handle_threads = get_nitter_rss_threads(
            handles=[handle],
            since_date=since_date,
            report_progress=report_progress,
        )
        if handle_threads:
            _report(
                report_progress,
                f"[{index}/{len(handles)}] {handle}: collected {len(handle_threads)} recent thread(s).",
            )
            threads.extend(handle_threads)
            continue
        empty_handles.append(handle)
        _report(
            report_progress,
            f"[{index}/{len(handles)}] {handle}: no recent RSS entries from the configured instances.",
        )

    if empty_handles:
        warnings.warn(
            "No recent Nitter RSS entries for handles: " + ", ".join(empty_handles),
            UserWarning,
            stacklevel=2,
        )

    _report(report_progress, f"Finished RSS fetch with {len(threads)} total recent thread(s).")
    return threads


def get_twitter_threads(
    handles_path: str | Path,
    since_date: datetime,
    report_progress: Callable[[str], None] | None = None,
) -> list[Thread]:
    handles = get_twitter_handles(handles_path)
    _report(report_progress, f"Loaded {len(handles)} handles from {handles_path}.")
    return get_twitter_threads_from_handles(
        handles,
        since_date,
        report_progress=report_progress,
    )


def build_tweet_queue_items(*, threads: list[Thread]) -> list[TweetQueueItem]:
    queue_items: list[TweetQueueItem] = []
    for thread in threads:
        primary_post = thread.primary_post
        primary_post_payload = primary_post.model_dump(mode="json")
        queue_items.append(
            TweetQueueItem(
                tweet_id=thread.thread_id,
                account_handle=thread.account_handle,
                text=primary_post.text,
                quote_text=primary_post.referenced_text or "",
                image_description="",
                url_hint=_build_url_hint(primary_post.referenced_url),
                url=primary_post.url,
                created_at=primary_post_payload["created_at"],
                status="pending",
                cluster_id=None,
                processing_note="",
            )
        )
    return queue_items


def _build_url_hint(url: str | None) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").strip().lower()
    if hostname in {"", "x.com", "www.x.com"}:
        return ""
    return hostname
