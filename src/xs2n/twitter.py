"""
AI-generated: This module was created with the assistance of an AI pair programmer.

Public API for the Twitter fetch layer.

Purpose:
    Load account handles from a JSON file and retrieve their recent tweets,
    reconstructing self-reply chains into full Threads.

Fetch strategy (tried in order):
    1. X internal REST v1.1 API with Chrome session cookies — primary path.
       Returns full tweet text, full thread chains, and is authenticated.
       Requires the user to be logged in to x.com in Chrome.
    2. Nitter RSS — fallback when Chrome cookies are unavailable or expired.
       Returns only the first post of each thread; no chain reconstruction.

Pre-conditions: The handles file must be a JSON object with a ``"handles"`` key
    whose value is a list of Twitter usernames (without @).
Post-conditions: Returns a flat list of Thread objects; handles that fail all
    methods are silently skipped.
"""

import json
from datetime import datetime
from pathlib import Path

from xs2n.agents.schemas import Thread
from xs2n.twitter_cookies import XCookiesMissing, get_chrome_x_cookies
from xs2n.twitter_nitter_rss import get_nitter_rss_threads
from xs2n.twitter_x_api import get_x_api_threads


def get_twitter_handles(path: str | Path) -> list[str]:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Load the list of Twitter handles from a JSON file.

    :param path: Path to a JSON file with the shape ``{"handles": ["handle1", ...]}``.
    :returns: List of handle strings (without @).
    :raises FileNotFoundError: If the file does not exist.
    :raises KeyError: If the JSON object has no ``"handles"`` key.
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["handles"]


def get_twitter_threads_from_handles(
    handles: list[str],
    since_date: datetime,
) -> list[Thread]:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Fetch recent threads for the given handles.

    Tries the X internal API first (Chrome cookies + REST v1.1).  If Chrome
    cookies are missing or expired, falls back to Nitter RSS which returns
    one Thread per tweet without chain reconstruction.

    :param handles: List of Twitter handles (without @).
    :param since_date: Timezone-aware UTC datetime; only threads whose root
                       post is at or after this time are returned.
    :returns: Flat list of Thread objects across all handles.
    """
    # Primary: X API with Chrome cookies — full thread reconstruction
    try:
        cookies = get_chrome_x_cookies()
        return get_x_api_threads(handles=handles, since_date=since_date, cookies=cookies)
    except XCookiesMissing:
        pass  # Chrome not logged in → use Nitter fallback

    # Fallback: Nitter RSS — single-tweet threads, no chain reconstruction
    return get_nitter_rss_threads(handles=handles, since_date=since_date)


def get_twitter_threads(handles_path: str | Path, since_date: datetime) -> list[Thread]:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.

    Load handles from a file and fetch their recent threads.

    Convenience wrapper combining ``get_twitter_handles`` and
    ``get_twitter_threads_from_handles``.

    :param handles_path: Path to the handles JSON file.
    :param since_date: Timezone-aware UTC datetime; only threads whose root
                       post is at or after this time are returned.
    :returns: Flat list of Thread objects.
    """
    handles = get_twitter_handles(handles_path)
    return get_twitter_threads_from_handles(handles, since_date)
