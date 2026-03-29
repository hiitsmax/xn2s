"""
AI-generated: This module was created with the assistance of an AI pair programmer.

Fetch tweets and reconstruct threads via X's internal GraphQL API, using the
session cookies from the user's Chrome browser for authentication.

Purpose:
    Provide reliable, full-fidelity tweet retrieval with native thread
    reconstruction.  Unlike Nitter RSS (which surfaces only the first tweet of
    a thread), the UserTweets GraphQL endpoint returns every tweet with
    ``in_reply_to_status_id_str`` set, allowing the full self-reply chain to be
    assembled locally without any additional requests.

GraphQL endpoints used:
    - ``UserByScreenName``  — resolve a Twitter handle to its numeric user ID.
    - ``UserTweets``        — fetch the recent timeline for a user ID.

Query IDs:
    X embeds GraphQL query IDs in its deployed JS bundle.  They change on
    every X frontend deploy (roughly monthly).  This module stores the last
    known values as defaults and fetches fresh IDs from the live bundle
    whenever a request fails with a 400/404, transparently retrying once.

Bearer token:
    The web app bearer token is embedded in X's main JS bundle.  The module
    caches the token in-process and refreshes it from the bundle the first time
    it is needed, so it stays current across X deploys.

Authentication:
    Every request carries:
    - ``Authorization: Bearer {bearer}``  — fetched from the x.com JS bundle.
    - ``x-csrf-token: {ct0}``             — the CSRF cookie value as a header.
    - ``Cookie: auth_token=...; ct0=...`` — session cookies from Chrome.

Constraints / limitations:
    - Rate limits apply per authenticated session; the UserTweets endpoint
      allows approximately 500 requests per 15-minute window per user token.
    - Only the most recent ~40 tweets are returned per request (``count=40``).
      Very active accounts posting more than 40 tweets per day may miss the
      oldest entries in the 24-hour window.
    - Retweets are included in the raw response; they appear with ``full_text``
      starting with ``RT @`` and are passed through to the pipeline unchanged.
    - Thread reconstruction uses the tweets present in the single fetched page.
      If a continuation tweet was posted more than ~40 tweets ago it will not
      appear in the batch and the chain will be truncated.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import requests


# ---------------------------------------------------------------------------
# Bundle-fetched values — refreshed automatically on query-ID errors
# ---------------------------------------------------------------------------

# Known-good defaults as of 2026-03-29.  Used until the bundle is fetched.
_DEFAULT_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)
_DEFAULT_QID_USER_BY_SCREEN_NAME = "IGgvgiOx4QZndDHuD3x9TQ"
_DEFAULT_QID_USER_TWEETS = "FOlovQsiHGDls3c0Q_HaSQ"

# In-process cache; populated lazily on first use
_cached_bearer: str | None = None
_cached_qids: dict[str, str] = {}

_BEARER_RE = re.compile(r"AAAAAAAAAAAAAAAAAAAAAAA[A-Za-z0-9%]+")
_QID_RE = re.compile(r'\{queryId:"([^"]+)",operationName:"([^"]+)"')
_BUNDLE_URL_RE = re.compile(
    r'"(https://abs\.twimg\.com/responsive-web/client-web/main\.[^"]+\.js)"'
)

_GRAPHQL_BASE = "https://x.com/i/api/graphql"
_REQUEST_TIMEOUT_S = 12

# Features required by UserByScreenName
_USER_FEATURES = {
    "hidden_profile_subscriptions_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "highlights_tweets_tab_ui_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
}

# Features required by UserTweets
_TWEET_FEATURES = {
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": True,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}


# ---------------------------------------------------------------------------
# Bundle refresh helpers
# ---------------------------------------------------------------------------

def _fetch_bundle_js() -> str:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Fetch the x.com main JS bundle text.

    Loads the x.com homepage to locate the bundle URL, then fetches the
    bundle itself.  Used to refresh the bearer token and query IDs.

    :returns: Full JS bundle text.
    :raises RuntimeError: If the bundle URL cannot be found or the fetch fails.
    """
    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    homepage = session.get("https://x.com", timeout=_REQUEST_TIMEOUT_S).text
    matches = _BUNDLE_URL_RE.findall(homepage)
    if not matches:
        raise RuntimeError("Could not locate the x.com JS bundle URL.")
    return session.get(matches[0], timeout=30).text


def _refresh_from_bundle() -> None:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Re-fetch the bearer token and GraphQL query IDs from the x.com JS bundle
    and update the in-process cache.

    Called automatically when a request returns 400/404 (indicating stale IDs)
    or on first use when the cache is empty.

    :raises RuntimeError: If the bundle cannot be fetched or parsed.
    """
    global _cached_bearer, _cached_qids
    js = _fetch_bundle_js()

    # Bearer token
    bearer_hits = _BEARER_RE.findall(js)
    if bearer_hits:
        _cached_bearer = bearer_hits[0]

    # Query IDs
    for qid, name in _QID_RE.findall(js):
        _cached_qids[name] = qid


def _get_bearer() -> str:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Return the current bearer token, fetching it from the bundle if not cached.

    :returns: Bearer token string.
    """
    global _cached_bearer
    if _cached_bearer is None:
        try:
            _refresh_from_bundle()
        except Exception:
            pass
    return _cached_bearer or _DEFAULT_BEARER


def _get_qid(operation: str, default: str) -> str:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Return the GraphQL query ID for an operation name, using the cached value
    or the provided default.

    :param operation: GraphQL operation name, e.g. ``"UserTweets"``.
    :param default: Fallback query ID to use if the operation is not cached.
    :returns: Query ID string.
    """
    return _cached_qids.get(operation, default)


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

def _make_session(cookies: dict[str, str]) -> requests.Session:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Build an authenticated requests.Session for the X internal GraphQL API.

    :param cookies: Dict with at least ``auth_token`` and ``ct0`` from Chrome.
    :returns: Configured requests.Session.
    """
    bearer = _get_bearer()
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {bearer}",
        "x-csrf-token": cookies["ct0"],
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://x.com/",
        "Origin": "https://x.com",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
    })
    for name, value in cookies.items():
        session.cookies.set(name, value, domain=".x.com")
    return session


# ---------------------------------------------------------------------------
# GraphQL helpers
# ---------------------------------------------------------------------------

def _graphql_get(
    session: requests.Session,
    operation: str,
    qid_default: str,
    variables: dict[str, Any],
    features: dict[str, Any],
    *,
    retry_on_stale: bool = True,
) -> dict[str, Any]:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Execute a GET GraphQL request, refreshing stale query IDs on 400/404.

    If the first attempt returns 400 or 404 (stale query ID), the bundle is
    re-fetched, the query ID is updated, and the request is retried once.

    :param session: Authenticated requests.Session.
    :param operation: GraphQL operation name used to look up the query ID.
    :param qid_default: Fallback query ID if the operation is not in cache.
    :param variables: GraphQL variables dict (serialised to JSON).
    :param features: GraphQL features dict (serialised to JSON).
    :param retry_on_stale: If True, retry once after refreshing the bundle
        when the first response is 400/404.
    :returns: Parsed JSON response body.
    :raises requests.HTTPError: On persistent non-2xx responses.
    """
    import json as _json

    qid = _get_qid(operation, qid_default)
    url = f"{_GRAPHQL_BASE}/{qid}/{operation}"
    params = {
        "variables": _json.dumps(variables, separators=(",", ":")),
        "features": _json.dumps(features, separators=(",", ":")),
    }

    resp = session.get(url, params=params, timeout=_REQUEST_TIMEOUT_S)

    if resp.status_code in (400, 404) and retry_on_stale:
        # Stale query ID — refresh the bundle and retry once
        try:
            _refresh_from_bundle()
        except Exception:
            pass
        qid = _get_qid(operation, qid_default)
        url = f"{_GRAPHQL_BASE}/{qid}/{operation}"
        resp = session.get(url, params=params, timeout=_REQUEST_TIMEOUT_S)

    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Domain logic
# ---------------------------------------------------------------------------

def _resolve_user_id(session: requests.Session, handle: str) -> str:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Resolve a Twitter handle to its numeric user ID via UserByScreenName.

    :param session: Authenticated requests.Session.
    :param handle: Twitter handle (without @).
    :returns: Numeric user ID string.
    :raises KeyError: If the API response does not contain the expected path.
    """
    data = _graphql_get(
        session,
        "UserByScreenName",
        _DEFAULT_QID_USER_BY_SCREEN_NAME,
        variables={"screen_name": handle, "withSafetyModeUserFields": True},
        features=_USER_FEATURES,
    )
    return data["data"]["user"]["result"]["rest_id"]


def _fetch_raw_tweets(session: requests.Session, user_id: str) -> list[dict[str, Any]]:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Fetch up to 40 recent tweets for a user ID via UserTweets GraphQL.

    Parses the nested timeline instructions to extract legacy tweet dicts.
    Handles both regular ``Tweet`` and ``TweetWithVisibilityResults`` wrappers.

    :param session: Authenticated requests.Session.
    :param user_id: Numeric user ID string.
    :returns: List of raw legacy tweet dicts.
    """
    data = _graphql_get(
        session,
        "UserTweets",
        _DEFAULT_QID_USER_TWEETS,
        variables={
            "userId": user_id,
            "count": 40,
            "includePromotedContent": False,
            "withVoice": True,
        },
        features=_TWEET_FEATURES,
    )

    instructions = (
        data["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
    )
    entries = next(
        (i["entries"] for i in instructions if i.get("type") == "TimelineAddEntries"),
        [],
    )

    raw: list[dict[str, Any]] = []
    for entry in entries:
        item = entry.get("content", {}).get("itemContent", {})
        if item.get("itemType") != "TimelineTweet":
            continue
        result = item.get("tweet_results", {}).get("result", {})
        # Unwrap TweetWithVisibilityResults if present
        if result.get("__typename") == "TweetWithVisibilityResults":
            result = result.get("tweet", {})
        legacy = result.get("legacy", {})
        if legacy:
            raw.append(legacy)

    return raw


def _parse_tweet_date(created_at: str) -> datetime:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Parse the ``created_at`` string from the GraphQL legacy tweet dict.

    X uses the format ``"Wed Mar 29 12:00:00 +0000 2026"``.

    :param created_at: Raw date string from the tweet dict.
    :returns: UTC-aware datetime.
    """
    return datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").astimezone(UTC)


def _build_threads(
    handle: str,
    raw_tweets: list[dict[str, Any]],
    since_date: datetime,
) -> list[Any]:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Group raw tweet dicts into Thread objects by reconstructing self-reply chains.

    Algorithm:
        1. Build a ``child_of`` index: ``parent_tweet_id → child_tweet`` for
           same-author consecutive self-replies within the fetched batch.
        2. Identify *continuation* tweet IDs (those that appear as children).
        3. Walk forward from every non-continuation tweet whose date is within
           the requested window, collecting the full chain in order.

    :param handle: The account handle being processed.
    :param raw_tweets: Raw legacy tweet dicts from the GraphQL response.
    :param since_date: UTC datetime; threads whose root is older are dropped.
    :returns: List of Thread objects with posts in ascending chronological order.

    Pre-conditions: All tweets in raw_tweets belong to the same author.
    Post-conditions: Every returned Thread has at least one Post dated >=
        since_date.
    """
    from xs2n.agents.schemas import Post, Thread

    by_id: dict[str, dict[str, Any]] = {t["id_str"]: t for t in raw_tweets}

    # Build parent → child map for same-author self-replies
    child_of: dict[str, dict[str, Any]] = {}
    for tweet in raw_tweets:
        pid: str | None = tweet.get("in_reply_to_status_id_str")
        puser: str = (tweet.get("in_reply_to_screen_name") or "").lower()
        if pid and puser == handle.lower() and pid in by_id:
            child_of[pid] = tweet

    continuation_ids = {t["id_str"] for t in child_of.values()}

    threads: list[Thread] = []
    for tweet in raw_tweets:
        if tweet["id_str"] in continuation_ids:
            continue
        if _parse_tweet_date(tweet["created_at"]) < since_date:
            continue

        # Walk forward to collect the full self-reply chain
        chain: list[dict[str, Any]] = [tweet]
        current_id = tweet["id_str"]
        for _ in range(50):
            nxt = child_of.get(current_id)
            if nxt is None:
                break
            chain.append(nxt)
            current_id = nxt["id_str"]

        # Sort oldest-first (API returns newest-first)
        chain.sort(key=lambda t: t["id_str"])

        posts = [
            Post(
                post_id=t["id_str"],
                author_handle=(t.get("user", {}).get("screen_name") or handle),
                created_at=_parse_tweet_date(t["created_at"]),
                text=t.get("full_text") or t.get("text", ""),
                url=f"https://x.com/{handle}/status/{t['id_str']}",
            )
            for t in chain
        ]
        threads.append(Thread(
            thread_id=chain[0]["id_str"],
            account_handle=handle,
            posts=posts,
        ))

    return threads


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_x_api_threads(
    *,
    handles: list[str],
    since_date: datetime,
    cookies: dict[str, str],
) -> list[Any]:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Fetch recent threads for all handles via the X internal GraphQL API.

    For each handle:
    1. Resolves the handle to a numeric user ID via ``UserByScreenName``.
    2. Fetches up to 40 recent tweets via ``UserTweets``.
    3. Reconstructs self-reply chains and filters by ``since_date``.

    :param handles: List of Twitter handles to fetch (without @).
    :param since_date: Timezone-aware UTC datetime; only threads whose root
                       post is at or after this time are returned.
    :param cookies: Dict with ``auth_token`` and ``ct0`` from Chrome.
    :returns: Flat list of Thread objects across all handles, unsorted.
    :raises requests.HTTPError: If the API returns a persistent non-2xx status
        (e.g. 401 when the Chrome session has expired — re-login to x.com in
        Chrome to refresh the cookies).

    Pre-conditions: ``since_date`` must be timezone-aware (UTC).
    Post-conditions: Every returned Thread has at least one Post with
        ``created_at >= since_date``.
    """
    session = _make_session(cookies)
    threads = []

    for handle in handles:
        user_id = _resolve_user_id(session, handle)
        raw_tweets = _fetch_raw_tweets(session, user_id)
        threads.extend(_build_threads(handle, raw_tweets, since_date))

    return threads
