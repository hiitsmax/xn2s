"""
AI-generated: This module was created with the assistance of an AI pair programmer.

Fetch tweets for a list of Twitter handles by consuming the RSS feed exposed by
public Nitter instances.

Purpose:
    Provide a dependency-light, browser-free way to retrieve recent tweets.
    Each Nitter instance exposes ``/{handle}/rss`` as a standard RSS 2.0 feed;
    this module fetches that feed, parses it, filters entries by date, and maps
    them to the internal ``Thread`` / ``Post`` schema.

Strategy:
    A ranked list of known public Nitter instances is tried in order for every
    handle.  The first instance that returns a non-empty feed is used and no
    further instances are tried for that handle.  If every instance fails, the
    handle is silently skipped (an empty list is returned for it).

Constraints / limitations:
    - Nitter RSS feeds typically expose the ~20 most recent tweets; very active
      accounts may therefore miss older posts even within the 24-hour window.
    - Thread reconstruction is not possible from RSS; every entry becomes a
      single-post Thread.  The downstream pipeline is responsible for grouping.
    - Replies are included; the pipeline's filter step should drop noise.
"""

from __future__ import annotations

import html as _html
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

import feedparser
import requests

from xs2n.agents.schemas import Post, Thread


# Public Nitter instances ordered by general reliability.
# The list is tried in order; the first instance that returns a non-empty feed
# wins.  Add or reorder entries here to tune instance preference.
NITTER_INSTANCES: list[str] = [
    "xcancel.com",
    "nitter.privacyredirect.com",
    "nitter.poast.org",
    "lightbrd.com",
    "nitter.space",
    "nitter.tiekoetter.com",
    "nitter.catsarch.com",
    "nitter.net",
]

_STATUS_ID_RE = re.compile(r"/status/(\d+)")
_REQUEST_TIMEOUT_S = 10


class _HtmlTextExtractor(HTMLParser):
    """Minimal HTML-to-text extractor using stdlib html.parser.

    AI-generated: This method was created with the assistance of an AI pair programmer.

    Purpose: Strip HTML markup from Nitter RSS description fields so that only
    plain tweet text is stored in the Post.
    Pre-conditions: feed() must be called with a well-formed or best-effort HTML
    string before get_text().
    Post-conditions: Returns concatenated text nodes, HTML-unescaped.
    """

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return _html.unescape("".join(self._parts)).strip()


def _strip_html(text: str) -> str:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Strip HTML tags from a string and unescape HTML entities.

    :param text: Raw HTML string.
    :returns: Plain text with HTML markup removed.
    """
    extractor = _HtmlTextExtractor()
    extractor.feed(text)
    return extractor.get_text()


def _extract_post_id(link: str) -> str | None:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Extract the numeric tweet status ID from a Nitter or X URL.

    :param link: Full URL such as ``https://nitter.net/user/status/1234``.
    :returns: The numeric ID string, or None if the URL does not match.
    """
    match = _STATUS_ID_RE.search(link)
    return match.group(1) if match else None


def _parse_entry_date(entry: feedparser.FeedParserDict) -> datetime | None:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Parse the publication date of a feedparser entry into a timezone-aware
    UTC datetime.

    feedparser normalises ``published_parsed`` and ``updated_parsed`` to
    ``time.struct_time`` in UTC when the source date is parseable; this helper
    converts those to ``datetime`` objects.  When the struct is absent it falls
    back to the raw ``published`` / ``updated`` string via
    ``email.utils.parsedate_to_datetime``.

    :param entry: A single feedparser entry dict.
    :returns: A UTC-aware datetime, or None if no date could be extracted.
    """
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
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Build the canonical x.com URL for a tweet, regardless of the Nitter
    instance the entry was fetched from.

    :param handle: Twitter handle (without @).
    :param post_id: Numeric tweet ID string.
    :returns: Canonical x.com status URL.
    """
    return f"https://x.com/{handle}/status/{post_id}"


def _build_thread_from_entry(
    handle: str,
    entry: feedparser.FeedParserDict,
) -> Thread | None:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Map a single feedparser RSS entry to a single-post Thread.

    The link field is used to extract the tweet ID; the summary field (which
    contains the HTML description) is preferred for tweet text, falling back to
    the title.  The canonical x.com URL is used instead of the Nitter URL so
    that downstream consumers are not coupled to the scraping infrastructure.

    :param handle: The Twitter account handle being processed.
    :param entry: A single feedparser entry dict from the handle's RSS feed.
    :returns: A Thread with one Post, or None if the entry is missing required
              fields (post ID or date).
    """
    link: str = entry.get("link", "")
    post_id = _extract_post_id(link)
    if not post_id:
        return None

    created_at = _parse_entry_date(entry)
    if created_at is None:
        return None

    # Prefer the HTML summary (full tweet content) over the title which may be
    # truncated and prefixed with "@handle: ".
    raw_text: str = entry.get("summary") or entry.get("title") or ""
    text = _strip_html(raw_text)

    post = Post(
        post_id=post_id,
        author_handle=handle,
        created_at=created_at,
        text=text,
        url=_x_status_url(handle, post_id),
    )
    return Thread(
        thread_id=post_id,
        account_handle=handle,
        posts=[post],
    )


def _fetch_feed(handle: str, instance: str) -> feedparser.FeedParserDict | None:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Fetch and parse the Nitter RSS feed for a handle from a specific instance.

    Returns None (instead of raising) on any network error or non-200 HTTP
    status so that the caller can silently try the next instance.

    :param handle: Twitter handle (without @).
    :param instance: Nitter instance hostname, e.g. ``xcancel.com``.
    :returns: A feedparser FeedParserDict on success, or None on failure.
    """
    url = f"https://{instance}/{handle}/rss"
    try:
        response = requests.get(
            url,
            timeout=_REQUEST_TIMEOUT_S,
            headers={"User-Agent": "xs2n/1.0 (digest-bot)"},
        )
        if response.status_code != 200:
            return None
        return feedparser.parse(response.text)
    except requests.RequestException:
        return None


def _get_threads_for_handle(handle: str, since_date: datetime) -> list[Thread]:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Fetch all tweets for a single handle that are newer than ``since_date``.

    Tries each instance in NITTER_INSTANCES order and uses the first one that
    returns at least one RSS entry.  If no instance succeeds, returns an empty
    list without raising.

    :param handle: Twitter handle (without @).
    :param since_date: Only tweets created at or after this UTC datetime are
                       included.
    :returns: List of Thread objects (one per tweet), possibly empty.
    """
    feed: feedparser.FeedParserDict | None = None
    for instance in NITTER_INSTANCES:
        candidate = _fetch_feed(handle, instance)
        if candidate and candidate.get("entries"):
            feed = candidate
            break

    if feed is None:
        return []

    threads: list[Thread] = []
    for entry in feed["entries"]:
        thread = _build_thread_from_entry(handle, entry)
        if thread is None:
            continue
        # Drop tweets older than the requested window
        if thread.primary_post.created_at < since_date:
            continue
        threads.append(thread)

    return threads


def get_nitter_rss_threads(*, handles: list[str], since_date: datetime) -> list[Thread]:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Fetch recent tweets for all handles via Nitter RSS feeds.

    Entry point for the twitter retrieval layer.  Iterates over every handle,
    collects threads newer than ``since_date``, and returns them as a flat list.

    :param handles: List of Twitter handles to fetch (without @).
    :param since_date: Timezone-aware UTC datetime; only tweets at or after
                       this time are returned.
    :returns: Flat list of Thread objects across all handles, unsorted.
    :raises: Does not raise; handles that fail all instances are silently
             skipped.

    Pre-conditions: ``since_date`` must be timezone-aware (UTC).
    Post-conditions: All returned Thread objects have at least one Post.
    """
    threads: list[Thread] = []
    for handle in handles:
        threads.extend(_get_threads_for_handle(handle, since_date))
    return threads
