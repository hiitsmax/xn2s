from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from xs2n.ui.run_arguments import RunCommand
except ImportError:
    @dataclass(slots=True)
    class RunCommand:
        label: str
        args: list[str]
        stream_jsonl_events: bool = False


def build_auth_doctor_command(cookies_file: Path) -> RunCommand:
    return RunCommand(
        label="auth doctor",
        args=[
            "auth",
            "doctor",
            "--json",
            "--cookies-file",
            str(cookies_file),
        ],
    )


def build_codex_login_command() -> RunCommand:
    return RunCommand(
        label="report auth",
        args=["report", "auth"],
    )


def build_codex_logout_command() -> RunCommand:
    return RunCommand(
        label="report auth logout",
        args=["report", "auth", "--logout"],
    )


def build_x_login_command(cookies_file: Path) -> RunCommand:
    return RunCommand(
        label="auth x login",
        args=[
            "auth",
            "x",
            "login",
            "--cookies-file",
            str(cookies_file),
        ],
    )


def build_x_reset_command(cookies_file: Path) -> RunCommand:
    return RunCommand(
        label="auth x reset",
        args=[
            "auth",
            "x",
            "reset",
            "--cookies-file",
            str(cookies_file),
        ],
    )
