"""
AI-generated: This module was created with the assistance of an AI pair programmer.

Tests for `src/xs2n/utils/twitter.py` — the public fetch-layer API.

Covers:
- get_twitter_handles: reads handles from a JSON file.
- get_twitter_threads_from_handles: uses Nitter RSS directly and warns about
  empty profiles.
- get_twitter_threads: end-to-end convenience wrapper.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from xs2n.schemas.twitter import Post, Thread
import xs2n.utils.twitter as twitter


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
def test_get_twitter_handles_returns_list(tmp_path: Path) -> None:
    handles_file = tmp_path / "handles.json"
    handles_file.write_text(json.dumps({"handles": ["alice", "bob"]}))

    result = twitter.get_twitter_handles(handles_file)

    assert result == ["alice", "bob"]


def test_get_twitter_handles_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        twitter.get_twitter_handles(tmp_path / "nonexistent.json")


def test_get_twitter_threads_from_handles_uses_nitter_rss_directly(
    monkeypatch,  # noqa: ANN001
) -> None:
    rss_calls: list[dict] = []

    monkeypatch.setattr(
        twitter,
        "get_nitter_rss_threads",
        lambda *, handles, since_date, report_progress=None: rss_calls.append(
            {"handles": handles, "since_date": since_date, "report_progress": report_progress}
        ) or [_THREAD],
    )

    result = twitter.get_twitter_threads_from_handles(["alice"], _SINCE)

    assert result == [_THREAD]
    assert rss_calls == [
        {"handles": ["alice"], "since_date": _SINCE, "report_progress": None}
    ]


def test_get_twitter_threads_from_handles_warns_for_empty_profiles(
    monkeypatch,  # noqa: ANN001
) -> None:
    rss_calls: list[dict] = []

    monkeypatch.setattr(
        twitter,
        "get_nitter_rss_threads",
        lambda *, handles, since_date, report_progress=None: rss_calls.append({
            "handles": handles,
            "since_date": since_date,
            "report_progress": report_progress,
        }) or ([] if handles == ["bob"] else [_THREAD]),
    )

    with pytest.warns(UserWarning, match="bob"):
        result = twitter.get_twitter_threads_from_handles(["alice", "bob"], _SINCE)

    assert result == [_THREAD]
    assert rss_calls == [
        {"handles": ["alice"], "since_date": _SINCE, "report_progress": None},
        {"handles": ["bob"], "since_date": _SINCE, "report_progress": None},
    ]


def test_get_twitter_threads_loads_handles_and_fetches(
    tmp_path: Path,
    monkeypatch,  # noqa: ANN001
) -> None:
    handles_file = tmp_path / "handles.json"
    handles_file.write_text(json.dumps({"handles": ["alice"]}))
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        twitter,
        "get_nitter_rss_threads",
        lambda **kwargs: calls.update({"kwargs": kwargs}) or [_THREAD],
    )

    messages: list[str] = []
    reporter = messages.append
    result = twitter.get_twitter_threads(handles_file, _SINCE, report_progress=reporter)

    assert result == [_THREAD]
    assert calls["kwargs"]["report_progress"] is reporter
    assert any("Loaded 1 handles" in message for message in messages)
