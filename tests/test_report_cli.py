from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from xs2n.cli.report import _run_codex_command, auth, digest


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
            selected_count=3,
            kept_count=2,
            issue_count=1,
            heated_count=1,
            digest_path=tmp_path / "report_runs" / "digest.md",
        )

    monkeypatch.setattr("xs2n.cli.report.run_digest_report", fake_run_digest_report)

    digest(
        timeline_file=tmp_path / "timeline.json",
        output_dir=tmp_path / "report_runs",
        state_file=tmp_path / "report_state.json",
        taxonomy_file=tmp_path / "taxonomy.json",
        window_minutes=15,
        model="gpt-4.1-mini",
    )

    assert captured["window_minutes"] == 15
    assert captured["model"] == "gpt-4.1-mini"
    out = capsys.readouterr().out
    assert "selected 3 entries" in out
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
            state_file=tmp_path / "report_state.json",
            taxonomy_file=tmp_path / "taxonomy.json",
            window_minutes=15,
            model="gpt-4.1-mini",
        )

    assert error.value.exit_code == 1
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY missing" in captured.err
