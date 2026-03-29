"""
AI-generated: This module was created with the assistance of an AI pair programmer.

Tests for src/xs2n/twitter.py — the public fetch-layer API.

Covers:
- get_twitter_handles: reads handles from a JSON file.
- get_twitter_threads_from_handles: uses X API when cookies are available,
  falls back to Nitter RSS when they are not.
- get_twitter_threads: end-to-end convenience wrapper.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from xs2n.agents.schemas import Post, Thread
from xs2n.twitter_cookies import XCookiesMissing
import xs2n.twitter as twitter


_SINCE = datetime(2026, 3, 29, 0, 0, tzinfo=UTC)

_THREAD = Thread(
    thread_id="1001",
    account_handle="alice",
    posts=[
        Post(
            post_id="1001",
            author_handle="alice",
            created_at=datetime(2026, 3, 29, 10, 0, tzinfo=UTC),
            text="Hello",
            url="https://x.com/alice/status/1001",
        )
    ],
)
_FAKE_COOKIES = {"auth_token": "tok", "ct0": "csrf"}


def test_get_twitter_handles_returns_list(tmp_path: Path) -> None:
    handles_file = tmp_path / "handles.json"
    handles_file.write_text(json.dumps({"handles": ["alice", "bob"]}))

    result = twitter.get_twitter_handles(handles_file)

    assert result == ["alice", "bob"]


def test_get_twitter_handles_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        twitter.get_twitter_handles(tmp_path / "nonexistent.json")


def test_get_twitter_threads_from_handles_uses_x_api_when_cookies_present(
    monkeypatch,  # noqa: ANN001
) -> None:
    x_api_calls: list[dict] = []

    monkeypatch.setattr(twitter, "get_chrome_x_cookies", lambda: _FAKE_COOKIES)
    monkeypatch.setattr(
        twitter,
        "get_x_api_threads",
        lambda *, handles, since_date, cookies: x_api_calls.append(
            {"handles": handles, "since_date": since_date, "cookies": cookies}
        ) or [_THREAD],
    )

    result = twitter.get_twitter_threads_from_handles(["alice"], _SINCE)

    assert result == [_THREAD]
    assert x_api_calls == [
        {"handles": ["alice"], "since_date": _SINCE, "cookies": _FAKE_COOKIES}
    ]


def test_get_twitter_threads_from_handles_falls_back_to_rss_when_cookies_missing(
    monkeypatch,  # noqa: ANN001
) -> None:
    rss_calls: list[dict] = []

    monkeypatch.setattr(
        twitter, "get_chrome_x_cookies", lambda: (_ for _ in ()).throw(XCookiesMissing("no cookies"))
    )
    monkeypatch.setattr(
        twitter,
        "get_nitter_rss_threads",
        lambda *, handles, since_date: rss_calls.append(
            {"handles": handles, "since_date": since_date}
        ) or [_THREAD],
    )

    result = twitter.get_twitter_threads_from_handles(["alice"], _SINCE)

    assert result == [_THREAD]
    assert rss_calls == [{"handles": ["alice"], "since_date": _SINCE}]


def test_get_twitter_threads_loads_handles_and_fetches(
    tmp_path: Path,
    monkeypatch,  # noqa: ANN001
) -> None:
    handles_file = tmp_path / "handles.json"
    handles_file.write_text(json.dumps({"handles": ["alice"]}))

    monkeypatch.setattr(twitter, "get_chrome_x_cookies", lambda: _FAKE_COOKIES)
    monkeypatch.setattr(
        twitter, "get_x_api_threads", lambda **_: [_THREAD]
    )

    result = twitter.get_twitter_threads(handles_file, _SINCE)

    assert result == [_THREAD]
