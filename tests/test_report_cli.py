from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

from xs2n.cli.report import (
    _resolve_latest_since,
    _run_codex_command,
    auth,
    issues,
    latest,
    report_app,
)
from xs2n.schemas.run_events import RunEvent

runner = CliRunner()


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


def test_report_issues_runs_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_run_issue_report(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            run_id="20260318T120000Z",
            run_dir=tmp_path / "report_runs" / "20260318T120000Z",
            thread_count=3,
            kept_count=2,
            issue_count=1,
        )

    monkeypatch.setattr("xs2n.cli.report.run_issue_report", fake_run_issue_report)

    issues(
        timeline_file=tmp_path / "timeline.json",
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4-mini",
    )

    assert captured["timeline_file"] == tmp_path / "timeline.json"
    assert captured["output_dir"] == tmp_path / "report_runs"
    assert captured["model"] == "gpt-5.4-mini"
    out = capsys.readouterr().out
    assert "Issue run 20260318T120000Z" in out
    assert "loaded 3 threads" in out
    assert "produced 1 issues" in out
    assert (
        "xs2n report html --run-dir "
        f"{tmp_path / 'report_runs' / '20260318T120000Z'}"
    ) in out


def test_report_issues_surfaces_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "xs2n.cli.report.run_issue_report",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("missing credentials")),
    )

    with pytest.raises(typer.Exit) as error:
        issues(
            timeline_file=tmp_path / "timeline.json",
            output_dir=tmp_path / "report_runs",
            model="gpt-5.4-mini",
        )

    assert error.value.exit_code == 1
    captured = capsys.readouterr()
    assert "missing credentials" in captured.err


def test_report_html_command_writes_html(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "report_runs" / "20260318T120000Z"
    run_dir.mkdir(parents=True)

    monkeypatch.setattr(
        "xs2n.cli.report.render_issue_digest_html",
        lambda **kwargs: run_dir / "digest.html",
    )

    result = runner.invoke(report_app, ["html", "--run-dir", str(run_dir)])

    assert result.exit_code == 0
    assert "Rendered HTML digest to" in result.stdout
    assert "digest.html" in result.stdout


def test_report_render_command_is_no_longer_available() -> None:
    result = runner.invoke(report_app, ["render", "--help"])

    assert result.exit_code != 0
    assert "No such command 'render'" in result.stdout or "No such command 'render'" in result.stderr


def test_report_html_surfaces_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "report_runs" / "20260318T120000Z"
    run_dir.mkdir(parents=True)

    monkeypatch.setattr(
        "xs2n.cli.report.render_issue_digest_html",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("render failed")),
    )

    result = runner.invoke(
        report_app,
        ["html", "--run-dir", str(run_dir)],
    )

    assert result.exit_code != 0
    assert "render failed" in result.stderr


def test_report_latest_help_tightens_home_latest_description() -> None:
    command = typer.main.get_command(report_app).commands["latest"]
    home_latest_option = next(
        param for param in command.params if param.name == "home_latest"
    )

    assert home_latest_option.help == (
        "Ingest the authenticated Home -> Following latest timeline "
        "instead of crawling source handles from --sources-file."
    )


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


def test_report_latest_runs_timeline_then_windowed_issues_then_render(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    timeline_calls: list[dict[str, object]] = []
    issue_calls: list[dict[str, object]] = []
    render_calls: list[dict[str, object]] = []

    def fake_run_timeline_ingestion(**kwargs):
        timeline_calls.append(kwargs)
        timeline_file = kwargs["timeline_file"]
        assert isinstance(timeline_file, Path)
        timeline_file.write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "tweet_id": "old-1",
                            "account_handle": "mx",
                            "author_handle": "mx",
                            "kind": "post",
                            "created_at": "2026-03-07T23:59:00+00:00",
                            "text": "old",
                            "conversation_id": "conv-old",
                        },
                        {
                            "tweet_id": "fresh-1",
                            "account_handle": "mx",
                            "author_handle": "mx",
                            "kind": "post",
                            "created_at": "2026-03-08T01:00:00+00:00",
                            "text": "fresh",
                            "conversation_id": "conv-fresh",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

    def fake_run_issue_report(**kwargs):
        issue_calls.append(kwargs)
        timeline_file = kwargs["timeline_file"]
        assert isinstance(timeline_file, Path)
        snapshot_doc = json.loads(timeline_file.read_text(encoding="utf-8"))
        assert [entry["tweet_id"] for entry in snapshot_doc["entries"]] == ["fresh-1"]
        assert timeline_file.name == "timeline_window.json"
        return SimpleNamespace(
            run_id="20260318T120000Z",
            run_dir=tmp_path / "report_runs" / "20260318T120000Z",
            thread_count=1,
            kept_count=1,
            issue_count=1,
        )

    def fake_render_issue_digest_html(**kwargs):
        render_calls.append(kwargs)
        return tmp_path / "report_runs" / "20260318T120000Z" / "digest.html"

    monkeypatch.setattr("xs2n.cli.report.run_timeline_ingestion", fake_run_timeline_ingestion)
    monkeypatch.setattr("xs2n.cli.report.run_issue_report", fake_run_issue_report)
    monkeypatch.setattr(
        "xs2n.cli.report.render_issue_digest_html",
        fake_render_issue_digest_html,
    )

    latest(
        since="2026-03-08T00:00:00Z",
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=False,
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4-mini",
    )

    assert len(timeline_calls) == 1
    assert timeline_calls[0]["from_sources"] is True
    assert timeline_calls[0]["home_latest"] is False
    assert timeline_calls[0]["account"] is None
    assert timeline_calls[0]["since"] == "2026-03-08T00:00:00+00:00"
    assert len(issue_calls) == 1
    assert issue_calls[0]["model"] == "gpt-5.4-mini"
    assert issue_calls[0]["timeline_file"] != tmp_path / "timeline.json"
    assert len(render_calls) == 1
    assert render_calls[0]["run_dir"] == tmp_path / "report_runs" / "20260318T120000Z"
    out = capsys.readouterr().out
    assert "Ingesting source timelines before issue generation" in out
    assert "Latest issue run 20260318T120000Z" in out
    assert "Rendered HTML digest to" in out


def test_report_latest_routes_home_latest_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    timeline_calls: list[dict[str, object]] = []
    issue_calls: list[dict[str, object]] = []

    def fake_run_timeline_ingestion(**kwargs):
        timeline_calls.append(kwargs)
        timeline_file = kwargs["timeline_file"]
        assert isinstance(timeline_file, Path)
        timeline_file.write_text('{"entries": []}\n', encoding="utf-8")

    monkeypatch.setattr("xs2n.cli.report.run_timeline_ingestion", fake_run_timeline_ingestion)
    monkeypatch.setattr(
        "xs2n.cli.report.run_issue_report",
        lambda **kwargs: issue_calls.append(kwargs)
        or SimpleNamespace(
            run_id="20260318T120000Z",
            run_dir=tmp_path / "report_runs" / "20260318T120000Z",
            thread_count=0,
            kept_count=0,
            issue_count=0,
        ),
    )
    monkeypatch.setattr(
        "xs2n.cli.report.render_issue_digest_html",
        lambda **kwargs: tmp_path / "report_runs" / "20260318T120000Z" / "digest.html",
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
        model="gpt-5.4-mini",
    )

    assert len(timeline_calls) == 1
    assert timeline_calls[0]["from_sources"] is False
    assert timeline_calls[0]["home_latest"] is True
    assert timeline_calls[0]["account"] is None
    assert len(issue_calls) == 1
    out = capsys.readouterr().out
    assert "Ingesting Home->Following latest timeline before issue generation" in out


def test_report_latest_surfaces_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("xs2n.cli.report.run_timeline_ingestion", lambda **kwargs: None)
    monkeypatch.setattr(
        "xs2n.cli.report.run_issue_report",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("issue build failed")),
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
            model="gpt-5.4-mini",
        )

    assert error.value.exit_code == 1
    captured = capsys.readouterr()
    assert "issue build failed" in captured.err


def test_report_latest_can_emit_jsonl_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_timeline_ingestion(**kwargs):
        timeline_file = kwargs["timeline_file"]
        assert isinstance(timeline_file, Path)
        timeline_file.write_text('{"entries": []}\n', encoding="utf-8")

    def fake_run_issue_report(**kwargs):
        kwargs["emit_event"](
            RunEvent(
                event="run_started",
                message="Issue run 20260318T120000Z started.",
                run_id="20260318T120000Z",
            )
        )
        kwargs["emit_event"](
            RunEvent(
                event="run_completed",
                message="Issue run 20260318T120000Z completed.",
                run_id="20260318T120000Z",
            )
        )
        return SimpleNamespace(
            run_id="20260318T120000Z",
            run_dir=tmp_path / "report_runs" / "20260318T120000Z",
            thread_count=0,
            kept_count=0,
            issue_count=0,
        )

    def fake_render_issue_digest_html(**kwargs):
        digest_path = tmp_path / "report_runs" / "20260318T120000Z" / "digest.html"
        kwargs["emit_event"](
            RunEvent(
                event="artifact_written",
                message="Rendered HTML digest artifact.",
                run_id="20260318T120000Z",
                phase="render_digest_html",
                artifact_path=str(digest_path),
            )
        )
        return digest_path

    monkeypatch.setattr("xs2n.cli.report.run_timeline_ingestion", fake_run_timeline_ingestion)
    monkeypatch.setattr("xs2n.cli.report.run_issue_report", fake_run_issue_report)
    monkeypatch.setattr(
        "xs2n.cli.report.render_issue_digest_html",
        fake_render_issue_digest_html,
    )

    latest(
        since="2026-03-08T00:00:00Z",
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=False,
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4-mini",
        jsonl_events=True,
    )

    captured = capsys.readouterr()
    stdout_lines = [line for line in captured.out.splitlines() if line.strip()]

    assert len(stdout_lines) >= 4
    parsed_events = [json.loads(line) for line in stdout_lines]
    assert [event["event"] for event in parsed_events[:3]] == [
        "phase_started",
        "phase_completed",
        "artifact_written",
    ]
    assert any(event.get("run_id") == "20260318T120000Z" for event in parsed_events)
    assert "Ingesting source timelines before issue generation" in captured.err
    assert "Rendered HTML digest to" in captured.err


def test_report_latest_normalizes_optioninfo_booleans(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_latest_report(arguments, **kwargs):
        captured["home_latest"] = arguments.home_latest
        captured["emit_event"] = kwargs["emit_event"]

    monkeypatch.setattr("xs2n.cli.report.run_latest_report", fake_run_latest_report)

    latest(
        since=None,
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=typer.Option(True, "--home-latest"),
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4-mini",
        jsonl_events=typer.Option(True, "--jsonl-events"),
    )

    assert captured["home_latest"] is True
    assert captured["emit_event"] is not None
