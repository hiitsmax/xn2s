from __future__ import annotations

import subprocess

from .credentials import DEFAULT_CODEX_BASE_URL


def build_codex_login_command(*, device_auth: bool = False) -> list[str]:
    command = ["codex", "login"]
    if device_auth:
        command.append("--device-auth")
    return command


def build_codex_status_command() -> list[str]:
    return ["codex", "login", "status"]


def build_codex_logout_command() -> list[str]:
    return ["codex", "logout"]


def run_codex_command(command: list[str]) -> int:
    try:
        completed = subprocess.run(command, check=False)
    except FileNotFoundError as error:
        raise RuntimeError(
            "Could not find the Codex CLI binary. Install it with "
            "`npm install -g @openai/codex` and retry."
        ) from error
    except OSError as error:
        raise RuntimeError(f"Could not run {' '.join(command)}: {error}") from error

    return completed.returncode or 0
