from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import typer
from twikit.errors import Forbidden, TooManyRequests

from xs2n.cli.timeline import (
    DEFAULT_IMPORT_TIMELINE,
    DEFAULT_MAX_RATE_LIMIT_RETRIES,
    DEFAULT_MAX_RATE_LIMIT_WAIT_SECONDS,
    DEFAULT_PAGE_DELAY_SECONDS,
    DEFAULT_RATE_LIMIT_POLL_SECONDS,
    DEFAULT_RATE_LIMIT_WAIT_SECONDS,
    DEFAULT_THREAD_OTHER_REPLIES_LIMIT,
    DEFAULT_THREAD_PARENT_LIMIT,
    DEFAULT_THREAD_REPLIES_LIMIT,
    import_home_latest_with_recovery,
    import_timeline_with_recovery,
    parse_since_datetime,
    run_timeline_ingestion,
    timeline,
)
from xs2n.profile.types import TimelineEntry, TimelineFetchResult, TimelineMergeResult

DEFAULT_TIMELINE_OPTIONS = {
    "slow_fetch_seconds": 0.0,
    "page_delay_seconds": 0.0,
    "thread_parent_limit": 0,
    "thread_replies_limit": 0,
    "thread_other_replies_limit": 0,
    "wait_on_rate_limit": True,
    "rate_limit_wait_seconds": DEFAULT_RATE_LIMIT_WAIT_SECONDS,
    "rate_limit_poll_seconds": DEFAULT_RATE_LIMIT_POLL_SECONDS,
    "max_rate_limit_wait_seconds": DEFAULT_MAX_RATE_LIMIT_WAIT_SECONDS,
    "max_rate_limit_retries": DEFAULT_MAX_RATE_LIMIT_RETRIES,
}


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
        "xs2n.cli.timeline.maybe_bootstrap_cookies_from_local_browser",
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
        "xs2n.cli.helpers.bootstrap_cookies_from_local_browser_with_choice",
        lambda cookies_file: cookies_file,
    )

    def fail_confirm(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("confirm should not be called when local cookies succeed")

    monkeypatch.setattr("typer.confirm", fail_confirm)
    monkeypatch.setattr(
        "xs2n.cli.helpers.bootstrap_cookies_via_browser",
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


def test_import_timeline_with_recovery_passes_page_delay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_import_timeline_entries(**kwargs):
        captured.update(kwargs)
        return _fetch_result()

    monkeypatch.setattr(
        "xs2n.cli.timeline.run_import_timeline_entries",
        fake_run_import_timeline_entries,
    )

    import_timeline_with_recovery(
        account="mx",
        cookies_file=tmp_path / "cookies.json",
        since_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
        limit=50,
        page_delay_seconds=1.5,
    )

    assert captured["page_delay_seconds"] == 1.5


def test_import_timeline_with_recovery_passes_thread_limits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_import_timeline_entries(**kwargs):
        captured.update(kwargs)
        return _fetch_result()

    monkeypatch.setattr(
        "xs2n.cli.timeline.run_import_timeline_entries",
        fake_run_import_timeline_entries,
    )

    import_timeline_with_recovery(
        account="mx",
        cookies_file=tmp_path / "cookies.json",
        since_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
        limit=50,
        thread_parent_limit=5,
        thread_replies_limit=7,
        thread_other_replies_limit=3,
    )

    assert captured["thread_parent_limit"] == 5
    assert captured["thread_replies_limit"] == 7
    assert captured["thread_other_replies_limit"] == 3


def test_import_home_latest_with_recovery_passes_page_delay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_import_home_latest_timeline_entries(**kwargs):
        captured.update(kwargs)
        return _fetch_result()

    monkeypatch.setattr(
        "xs2n.cli.timeline.run_import_home_latest_timeline_entries",
        fake_run_import_home_latest_timeline_entries,
    )

    import_home_latest_with_recovery(
        cookies_file=tmp_path / "cookies.json",
        since_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
        limit=50,
        page_delay_seconds=1.25,
    )

    assert captured["page_delay_seconds"] == 1.25


def test_timeline_requires_exactly_one_mode(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter):
        timeline(
            account=None,
            from_sources=False,
            home_latest=False,
            since="2026-03-01T00:00:00Z",
            cookies_file=tmp_path / "cookies.json",
            limit=50,
            timeline_file=tmp_path / "timeline.json",
            sources_file=tmp_path / "sources.json",
            **DEFAULT_TIMELINE_OPTIONS,
        )


def test_timeline_rejects_account_with_from_sources(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter):
        timeline(
            account="mx",
            from_sources=True,
            home_latest=False,
            since="2026-03-01T00:00:00Z",
            cookies_file=tmp_path / "cookies.json",
            limit=50,
            timeline_file=tmp_path / "timeline.json",
            sources_file=tmp_path / "sources.json",
            **DEFAULT_TIMELINE_OPTIONS,
        )


def test_timeline_rejects_account_with_home_latest(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter):
        timeline(
            account="mx",
            from_sources=False,
            home_latest=True,
            since="2026-03-01T00:00:00Z",
            cookies_file=tmp_path / "cookies.json",
            limit=50,
            timeline_file=tmp_path / "timeline.json",
            sources_file=tmp_path / "sources.json",
            **DEFAULT_TIMELINE_OPTIONS,
        )


def test_timeline_rejects_from_sources_with_home_latest(tmp_path: Path) -> None:
    with pytest.raises(typer.BadParameter):
        timeline(
            account=None,
            from_sources=True,
            home_latest=True,
            since="2026-03-01T00:00:00Z",
            cookies_file=tmp_path / "cookies.json",
            limit=50,
            timeline_file=tmp_path / "timeline.json",
            sources_file=tmp_path / "sources.json",
            **DEFAULT_TIMELINE_OPTIONS,
        )


def test_run_timeline_ingestion_from_sources_uses_python_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sources_file = tmp_path / "sources.json"
    sources_file.write_text(
        json.dumps({"profiles": [{"handle": "alpha"}]}),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_import(**kwargs):
        captured.update(kwargs)
        return TimelineFetchResult(entries=[], scanned=0, skipped_old=0)

    monkeypatch.setattr("xs2n.cli.timeline.import_timeline_with_recovery", fake_import)

    run_timeline_ingestion(
        account=None,
        from_sources=True,
        home_latest=False,
        since="2026-03-01T00:00:00Z",
        cookies_file=tmp_path / "cookies.json",
        timeline_file=tmp_path / "timeline.json",
        sources_file=sources_file,
    )

    assert captured["page_delay_seconds"] == DEFAULT_PAGE_DELAY_SECONDS
    assert captured["thread_parent_limit"] == DEFAULT_THREAD_PARENT_LIMIT
    assert captured["thread_replies_limit"] == DEFAULT_THREAD_REPLIES_LIMIT
    assert captured["thread_other_replies_limit"] == DEFAULT_THREAD_OTHER_REPLIES_LIMIT
    assert captured["limit"] == DEFAULT_IMPORT_TIMELINE
    assert captured["since_datetime"] == datetime(2026, 3, 1, tzinfo=timezone.utc)


def test_run_timeline_ingestion_home_latest_uses_python_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_fetch(**kwargs):
        captured.update(kwargs)
        return _fetch_result()

    monkeypatch.setattr(
        "xs2n.cli.timeline._fetch_home_latest_with_rate_limit_retries",
        fake_fetch,
    )
    monkeypatch.setattr(
        "xs2n.cli.timeline.merge_timeline_entries",
        lambda entries, path: TimelineMergeResult(added=len(entries), skipped_duplicates=0),
    )

    run_timeline_ingestion(
        account=None,
        from_sources=False,
        home_latest=True,
        since="2026-03-01T00:00:00Z",
        cookies_file=tmp_path / "cookies.json",
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
    )

    assert captured["page_delay_seconds"] == DEFAULT_PAGE_DELAY_SECONDS
    assert captured["wait_on_rate_limit"] is True
    assert captured["rate_limit_wait_seconds"] == DEFAULT_RATE_LIMIT_WAIT_SECONDS
    assert captured["rate_limit_poll_seconds"] == DEFAULT_RATE_LIMIT_POLL_SECONDS
    assert captured["max_rate_limit_wait_seconds"] == DEFAULT_MAX_RATE_LIMIT_WAIT_SECONDS
    assert captured["max_rate_limit_retries"] == DEFAULT_MAX_RATE_LIMIT_RETRIES
    assert captured["limit"] == DEFAULT_IMPORT_TIMELINE
    assert captured["since_datetime"] == datetime(2026, 3, 1, tzinfo=timezone.utc)


def test_timeline_from_sources_ingests_unique_valid_handles(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sources_file = tmp_path / "sources.json"
    sources_file.write_text(
        json.dumps(
            {
                "profiles": [
                    {"handle": "alpha"},
                    {"handle": "beta"},
                    {"handle": "alpha"},
                    {"handle": ""},
                    {"name": "missing_handle"},
                ]
            }
        ),
        encoding="utf-8",
    )

    imported_accounts: list[str] = []

    def fake_import(**kwargs):
        account = kwargs["account"]
        imported_accounts.append(account)
        return TimelineFetchResult(
            entries=[
                TimelineEntry(
                    tweet_id=f"{account}-1",
                    account_handle=account,
                    author_handle=account,
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

    monkeypatch.setattr(
        "xs2n.cli.timeline.import_timeline_with_recovery",
        fake_import,
    )
    monkeypatch.setattr(
        "xs2n.cli.timeline.merge_timeline_entries",
        lambda entries, path: TimelineMergeResult(added=len(entries), skipped_duplicates=0),
    )

    timeline(
        account=None,
        from_sources=True,
        home_latest=False,
        since="2026-03-01T00:00:00Z",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
        timeline_file=tmp_path / "timeline.json",
        sources_file=sources_file,
        **DEFAULT_TIMELINE_OPTIONS,
    )

    output = capsys.readouterr().out
    assert imported_accounts == ["alpha", "beta"]
    assert "Processed 2 of 2 accounts" in output


def test_timeline_from_sources_migrates_legacy_yaml_when_json_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sources_json = tmp_path / "sources.json"
    legacy_yaml = tmp_path / "sources.yaml"
    legacy_yaml.write_text(
        "\n".join(
            [
                "profiles:",
                "- handle: alpha",
                "  added_via: following_import",
                "  added_at: '2026-03-01T00:00:00+00:00'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    imported_accounts: list[str] = []

    def record_import(**kwargs):
        imported_accounts.append(kwargs["account"])
        return TimelineFetchResult(entries=[], scanned=0, skipped_old=0)

    monkeypatch.setattr("xs2n.cli.timeline.import_timeline_with_recovery", record_import)

    timeline(
        account=None,
        from_sources=True,
        home_latest=False,
        since="2026-03-01T00:00:00Z",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
        timeline_file=tmp_path / "timeline.json",
        sources_file=sources_json,
        **DEFAULT_TIMELINE_OPTIONS,
    )

    assert sources_json.exists()
    assert imported_accounts == ["alpha"]


def test_timeline_single_account_handles_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_rate_limit(**kwargs):
        raise TooManyRequests('status: 429, message: "Rate limit exceeded"')

    monkeypatch.setattr("xs2n.cli.timeline.import_timeline_with_recovery", raise_rate_limit)

    with pytest.raises(typer.Exit) as exc:
        timeline(
            account="mx",
            from_sources=False,
            home_latest=False,
            since="2026-03-01T00:00:00Z",
            cookies_file=tmp_path / "cookies.json",
            limit=50,
            timeline_file=tmp_path / "timeline.json",
            sources_file=tmp_path / "sources.json",
            wait_on_rate_limit=False,
            slow_fetch_seconds=0.0,
            page_delay_seconds=0.0,
            rate_limit_wait_seconds=900,
            rate_limit_poll_seconds=30,
            max_rate_limit_wait_seconds=1800,
            max_rate_limit_retries=30,
        )

    assert exc.value.exit_code == 1
    captured = capsys.readouterr()
    assert "rate limit" in captured.err.lower()


def test_timeline_from_sources_stops_cleanly_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sources_file = tmp_path / "sources.json"
    sources_file.write_text(
        json.dumps({"profiles": [{"handle": "alpha"}, {"handle": "beta"}]}),
        encoding="utf-8",
    )

    calls = {"count": 0}

    def flaky_import(**kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise TooManyRequests('status: 429, message: "Rate limit exceeded"')
        return TimelineFetchResult(
            entries=[
                TimelineEntry(
                    tweet_id="alpha-1",
                    account_handle="alpha",
                    author_handle="alpha",
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

    monkeypatch.setattr("xs2n.cli.timeline.import_timeline_with_recovery", flaky_import)
    monkeypatch.setattr(
        "xs2n.cli.timeline.merge_timeline_entries",
        lambda entries, path: TimelineMergeResult(added=len(entries), skipped_duplicates=0),
    )

    with pytest.raises(typer.Exit) as exc:
        timeline(
            account=None,
            from_sources=True,
            home_latest=False,
            since="2026-03-01T00:00:00Z",
            cookies_file=tmp_path / "cookies.json",
            limit=50,
            timeline_file=tmp_path / "timeline.json",
            sources_file=sources_file,
            wait_on_rate_limit=False,
            slow_fetch_seconds=0.0,
            page_delay_seconds=0.0,
            rate_limit_wait_seconds=900,
            rate_limit_poll_seconds=30,
            max_rate_limit_wait_seconds=1800,
            max_rate_limit_retries=30,
        )

    assert exc.value.exit_code == 1
    captured = capsys.readouterr()
    assert "processed 1 of 2 accounts" in captured.out.lower()
    assert "rate limit" in captured.err.lower()


def test_timeline_single_account_waits_and_retries_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = {"count": 0}
    sleep_calls: list[float] = []

    def flaky_import(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            reset_epoch = int(datetime.now(timezone.utc).timestamp()) + 1
            raise TooManyRequests(
                'status: 429, message: "Rate limit exceeded"',
                headers={"x-rate-limit-reset": str(reset_epoch)},
            )
        return _fetch_result()

    monkeypatch.setattr("xs2n.cli.timeline.import_timeline_with_recovery", flaky_import)
    monkeypatch.setattr(
        "xs2n.cli.timeline.merge_timeline_entries",
        lambda entries, path: TimelineMergeResult(added=len(entries), skipped_duplicates=0),
    )
    monkeypatch.setattr("xs2n.cli.timeline.time.sleep", lambda seconds: sleep_calls.append(seconds))

    timeline(
        account="mx",
        from_sources=False,
        home_latest=False,
        since="2026-03-01T00:00:00Z",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        slow_fetch_seconds=0.0,
        page_delay_seconds=0.0,
        wait_on_rate_limit=True,
        rate_limit_wait_seconds=900,
        rate_limit_poll_seconds=1,
        max_rate_limit_wait_seconds=1800,
        max_rate_limit_retries=2,
    )

    captured = capsys.readouterr()
    assert calls["count"] == 2
    assert sleep_calls
    assert "retry 1/2" in captured.err.lower()


def test_timeline_from_sources_applies_slow_fetch_delay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    sources_file = tmp_path / "sources.json"
    sources_file.write_text(
        json.dumps({"profiles": [{"handle": "alpha"}, {"handle": "beta"}]}),
        encoding="utf-8",
    )

    sleep_calls: list[float] = []

    monkeypatch.setattr(
        "xs2n.cli.timeline.import_timeline_with_recovery",
        lambda **kwargs: TimelineFetchResult(entries=[], scanned=0, skipped_old=0),
    )
    monkeypatch.setattr("xs2n.cli.timeline.time.sleep", lambda seconds: sleep_calls.append(seconds))

    timeline(
        account=None,
        from_sources=True,
        home_latest=False,
        since="2026-03-01T00:00:00Z",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
        timeline_file=tmp_path / "timeline.json",
        sources_file=sources_file,
        slow_fetch_seconds=0.25,
        page_delay_seconds=0.0,
        wait_on_rate_limit=True,
        rate_limit_wait_seconds=900,
        rate_limit_poll_seconds=30,
        max_rate_limit_wait_seconds=1800,
        max_rate_limit_retries=30,
    )

    assert 0.25 in sleep_calls


def test_timeline_home_latest_ingests_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "xs2n.cli.timeline.import_home_latest_with_recovery",
        lambda **kwargs: _fetch_result(),
    )
    monkeypatch.setattr(
        "xs2n.cli.timeline.merge_timeline_entries",
        lambda entries, path: TimelineMergeResult(added=len(entries), skipped_duplicates=0),
    )

    timeline(
        account=None,
        from_sources=False,
        home_latest=True,
        since="2026-03-01T00:00:00Z",
        cookies_file=tmp_path / "cookies.json",
        limit=50,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        slow_fetch_seconds=0.0,
        page_delay_seconds=0.0,
        wait_on_rate_limit=True,
        rate_limit_wait_seconds=900,
        rate_limit_poll_seconds=30,
        max_rate_limit_wait_seconds=1800,
        max_rate_limit_retries=30,
        thread_parent_limit=0,
        thread_replies_limit=0,
        thread_other_replies_limit=0,
    )

    output = capsys.readouterr().out
    assert "Home->Following timeline" in output


def test_timeline_home_latest_handles_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "xs2n.cli.timeline.import_home_latest_with_recovery",
        lambda **kwargs: (_ for _ in ()).throw(
            TooManyRequests('status: 429, message: "Rate limit exceeded"')
        ),
    )

    with pytest.raises(typer.Exit) as exc:
        timeline(
            account=None,
            from_sources=False,
            home_latest=True,
            since="2026-03-01T00:00:00Z",
            cookies_file=tmp_path / "cookies.json",
            limit=50,
            timeline_file=tmp_path / "timeline.json",
            sources_file=tmp_path / "sources.json",
            wait_on_rate_limit=False,
            slow_fetch_seconds=0.0,
            page_delay_seconds=0.0,
            rate_limit_wait_seconds=900,
            rate_limit_poll_seconds=30,
            max_rate_limit_wait_seconds=1800,
            max_rate_limit_retries=30,
            thread_parent_limit=0,
            thread_replies_limit=0,
            thread_other_replies_limit=0,
        )

    assert exc.value.exit_code == 1
    captured = capsys.readouterr()
    assert "rate limit" in captured.err.lower()
