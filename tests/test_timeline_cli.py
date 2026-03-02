from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from twikit.errors import Forbidden

from xs2n.cli.timeline import import_timeline_with_recovery, parse_since_datetime
from xs2n.profile.types import TimelineEntry, TimelineFetchResult


def _cloudflare_error() -> Forbidden:
    return Forbidden('status: 403, message: "Attention Required! | Cloudflare"')


def _fetch_result() -> TimelineFetchResult:
    return TimelineFetchResult(
        entries=[
            TimelineEntry(
                tweet_id="1",
                account_handle="mx",
                author_handle="mx",
                kind="post",
                created_at="2026-03-01T00:00:00+00:00",
                text="hello",
                retweeted_tweet_id=None,
                retweeted_author_handle=None,
                retweeted_created_at=None,
            )
        ],
        scanned=1,
        skipped_old=0,
    )


def test_parse_since_datetime_accepts_z_suffix() -> None:
    parsed = parse_since_datetime("2026-03-01T10:30:00Z")
    assert parsed == datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc)


def test_parse_since_datetime_assumes_utc_for_naive_input() -> None:
    parsed = parse_since_datetime("2026-03-01T10:30:00")
    assert parsed == datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc)


def test_import_timeline_with_recovery_bootstraps_local_cookies_before_first_attempt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bootstrap_calls = {"count": 0}

    def fake_bootstrap(cookies_file: Path) -> Path:
        bootstrap_calls["count"] += 1
        return cookies_file

    monkeypatch.setattr(
        "xs2n.cli.timeline.bootstrap_cookies_from_local_browser_with_choice",
        fake_bootstrap,
    )
    monkeypatch.setattr(
        "xs2n.cli.timeline.run_import_timeline_entries",
        lambda **kwargs: _fetch_result(),
    )

    result = import_timeline_with_recovery(
        account="mx",
        cookies_file=tmp_path / "cookies.json",
        since_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
        limit=50,
    )

    assert len(result.entries) == 1
    assert bootstrap_calls["count"] == 1


def test_import_timeline_with_recovery_retries_after_local_cookie_import(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = {"count": 0}

    def fake_run_import_timeline_entries(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise _cloudflare_error()
        return _fetch_result()

    monkeypatch.setattr(
        "xs2n.cli.timeline.run_import_timeline_entries",
        fake_run_import_timeline_entries,
    )
    monkeypatch.setattr(
        "xs2n.cli.timeline.bootstrap_cookies_from_local_browser_with_choice",
        lambda cookies_file: cookies_file,
    )

    def fail_confirm(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("confirm should not be called when local cookies succeed")

    monkeypatch.setattr("typer.confirm", fail_confirm)
    monkeypatch.setattr(
        "xs2n.cli.timeline.bootstrap_cookies_via_browser",
        lambda cookies_file: cookies_file,
    )

    result = import_timeline_with_recovery(
        account="mx",
        cookies_file=tmp_path / "cookies.json",
        since_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
        limit=50,
    )

    assert len(result.entries) == 1
    assert calls["count"] == 2
