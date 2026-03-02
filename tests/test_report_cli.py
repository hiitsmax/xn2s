from __future__ import annotations

from types import SimpleNamespace

import pytest
import typer

from xs2n.cli.report import _run_codex_command, auth


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
