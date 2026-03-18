from __future__ import annotations

from pathlib import Path

from xs2n.ui.auth_commands import (
    RunCommand,
    build_auth_doctor_command,
    build_codex_login_command,
    build_codex_logout_command,
    build_x_login_command,
    build_x_reset_command,
)

try:
    from xs2n.ui.run_arguments import RunCommand as SharedRunCommand
except ImportError:
    SharedRunCommand = RunCommand

RunCommand = SharedRunCommand


def test_build_auth_doctor_command_uses_json_and_cookie_path() -> None:
    command = build_auth_doctor_command(Path("tmp/cookies.json"))

    assert command == RunCommand(
        label="auth doctor",
        args=[
            "auth",
            "doctor",
            "--json",
            "--cookies-file",
            "tmp/cookies.json",
        ],
    )


def test_build_codex_login_and_logout_commands() -> None:
    assert build_codex_login_command() == RunCommand(
        label="report auth",
        args=["report", "auth"],
    )
    assert build_codex_logout_command() == RunCommand(
        label="report auth logout",
        args=["report", "auth", "--logout"],
    )


def test_build_x_login_and_reset_commands_use_cookie_path() -> None:
    cookies_file = Path("tmp/cookies.json")

    assert build_x_login_command(cookies_file) == RunCommand(
        label="auth x login",
        args=[
            "auth",
            "x",
            "login",
            "--cookies-file",
            "tmp/cookies.json",
        ],
    )
    assert build_x_reset_command(cookies_file) == RunCommand(
        label="auth x reset",
        args=[
            "auth",
            "x",
            "reset",
            "--cookies-file",
            "tmp/cookies.json",
        ],
    )
