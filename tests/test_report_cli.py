from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from xs2n.cli.report import (
    _resolve_latest_since,
    _run_codex_command,
    auth,
    digest,
    latest,
)


def test_report_auth_runs_codex_login(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "xs2n.cli.report._run_codex_command",
        lambda command: commands.append(command),
    )

    auth(status=False, logout=False, device_auth=False, codex_bin="codex")

    assert commands == [["codex", "login"]]


def test_report_auth_runs_device_auth_login(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "xs2n.cli.report._run_codex_command",
        lambda command: commands.append(command),
    )

    auth(status=False, logout=False, device_auth=True, codex_bin="codex")

    assert commands == [["codex", "login", "--device-auth"]]


def test_report_auth_runs_status_command(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "xs2n.cli.report._run_codex_command",
        lambda command: commands.append(command),
    )

    auth(status=True, logout=False, device_auth=False, codex_bin="codex")

    assert commands == [["codex", "login", "status"]]


def test_report_auth_runs_logout_command(monkeypatch: pytest.MonkeyPatch) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "xs2n.cli.report._run_codex_command",
        lambda command: commands.append(command),
    )

    auth(status=False, logout=True, device_auth=False, codex_bin="my-codex")

    assert commands == [["my-codex", "logout"]]


def test_report_auth_rejects_multiple_modes() -> None:
    with pytest.raises(typer.BadParameter):
        auth(status=True, logout=True, device_auth=False, codex_bin="codex")


def test_report_auth_rejects_device_auth_for_status() -> None:
    with pytest.raises(typer.BadParameter):
        auth(status=True, logout=False, device_auth=True, codex_bin="codex")


def test_run_codex_command_surfaces_missing_binary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise FileNotFoundError("codex")

    monkeypatch.setattr("xs2n.cli.report.subprocess.run", fake_run)

    with pytest.raises(typer.Exit) as error:
        _run_codex_command(["codex", "login"])

    assert error.value.exit_code == 1
    captured = capsys.readouterr()
    assert "npm install -g @openai/codex" in captured.err


def test_run_codex_command_uses_non_zero_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "xs2n.cli.report.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=7),
    )

    with pytest.raises(typer.Exit) as error:
        _run_codex_command(["codex", "login"])

    assert error.value.exit_code == 7


def test_report_digest_runs_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_run_digest_report(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            run_id="20260307T120000Z",
            thread_count=3,
            kept_count=2,
            issue_count=1,
            digest_path=tmp_path / "report_runs" / "digest.md",
        )

    monkeypatch.setattr("xs2n.cli.report.run_digest_report", fake_run_digest_report)

    digest(
        timeline_file=tmp_path / "timeline.json",
        output_dir=tmp_path / "report_runs",
        taxonomy_file=tmp_path / "taxonomy.json",
        model="gpt-5.4",
    )

    assert captured["model"] == "gpt-5.4"
    out = capsys.readouterr().out
    assert "loaded 3 threads" in out
    assert "produced 1 issues" in out


def test_report_digest_surfaces_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "xs2n.cli.report.run_digest_report",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("OPENAI_API_KEY missing")),
    )

    with pytest.raises(typer.Exit) as error:
        digest(
            timeline_file=tmp_path / "timeline.json",
            output_dir=tmp_path / "report_runs",
            taxonomy_file=tmp_path / "taxonomy.json",
            model="gpt-5.4",
        )

    assert error.value.exit_code == 1
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY missing" in captured.err


def test_resolve_latest_since_prefers_explicit_since() -> None:
    now = datetime(2026, 3, 8, 20, 0, tzinfo=timezone.utc)

    resolved = _resolve_latest_since(
        since="2026-03-01T10:30:00Z",
        lookback_hours=12,
        now=now,
    )

    assert resolved == datetime(2026, 3, 1, 10, 30, tzinfo=timezone.utc)


def test_resolve_latest_since_uses_lookback_window() -> None:
    now = datetime(2026, 3, 8, 20, 0, tzinfo=timezone.utc)

    resolved = _resolve_latest_since(
        since=None,
        lookback_hours=6,
        now=now,
    )

    assert resolved == now - timedelta(hours=6)


def test_report_latest_runs_timeline_then_digest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    timeline_calls: list[dict[str, object]] = []
    digest_calls: list[dict[str, object]] = []

    def fake_timeline(**kwargs):
        timeline_calls.append(kwargs)

    def fake_run_digest_report(**kwargs):
        digest_calls.append(kwargs)
        return SimpleNamespace(
            run_id="20260308T120000Z",
            thread_count=8,
            kept_count=3,
            issue_count=2,
            digest_path=tmp_path / "report_runs" / "digest.md",
        )

    monkeypatch.setattr("xs2n.cli.report.timeline", fake_timeline)
    monkeypatch.setattr("xs2n.cli.report.run_digest_report", fake_run_digest_report)

    latest(
        since="2026-03-08T00:00:00Z",
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=False,
        output_dir=tmp_path / "report_runs",
        taxonomy_file=tmp_path / "taxonomy.json",
        model="gpt-5.4",
    )

    assert len(timeline_calls) == 1
    assert timeline_calls[0]["from_sources"] is True
    assert timeline_calls[0]["home_latest"] is False
    assert timeline_calls[0]["account"] is None
    assert timeline_calls[0]["since"] == "2026-03-08T00:00:00+00:00"
    assert len(digest_calls) == 1
    assert digest_calls[0]["model"] == "gpt-5.4"
    out = capsys.readouterr().out
    assert "Ingesting source timelines before digest generation" in out
    assert "Latest digest run 20260308T120000Z" in out


def test_report_latest_routes_home_latest_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    timeline_calls: list[dict[str, object]] = []
    digest_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "xs2n.cli.report.timeline",
        lambda **kwargs: timeline_calls.append(kwargs),
    )
    monkeypatch.setattr(
        "xs2n.cli.report.run_digest_report",
        lambda **kwargs: digest_calls.append(kwargs)
        or SimpleNamespace(
            run_id="20260308T120000Z",
            thread_count=5,
            kept_count=2,
            issue_count=1,
            digest_path=tmp_path / "report_runs" / "digest.md",
        ),
    )

    latest(
        since="2026-03-08T00:00:00Z",
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=True,
        output_dir=tmp_path / "report_runs",
        taxonomy_file=tmp_path / "taxonomy.json",
        model="gpt-5.4",
    )

    assert len(timeline_calls) == 1
    assert timeline_calls[0]["from_sources"] is False
    assert timeline_calls[0]["home_latest"] is True
    assert timeline_calls[0]["account"] is None
    assert len(digest_calls) == 1
    out = capsys.readouterr().out
    assert "Ingesting Home->Following latest timeline before digest generation" in out


def test_report_latest_surfaces_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("xs2n.cli.report.timeline", lambda **kwargs: None)
    monkeypatch.setattr(
        "xs2n.cli.report.run_digest_report",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("digest failed")),
    )

    with pytest.raises(typer.Exit) as error:
        latest(
            since="2026-03-08T00:00:00Z",
            lookback_hours=24,
            cookies_file=tmp_path / "cookies.json",
            limit=120,
            timeline_file=tmp_path / "timeline.json",
            sources_file=tmp_path / "sources.json",
            home_latest=False,
            output_dir=tmp_path / "report_runs",
            taxonomy_file=tmp_path / "taxonomy.json",
            model="gpt-5.4",
        )

    assert error.value.exit_code == 1
    captured = capsys.readouterr()
    assert "digest failed" in captured.err
