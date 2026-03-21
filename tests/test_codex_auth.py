from __future__ import annotations

import json
from pathlib import Path

import pytest

from xs2n.codex_auth import (
    DEFAULT_CODEX_BASE_URL,
    build_codex_login_command,
    build_codex_logout_command,
    build_codex_status_command,
)
from xs2n.credentials import resolve_model_credentials


def test_build_codex_commands_match_minimal_script_contract() -> None:
    assert build_codex_login_command() == ["codex", "login"]
    assert build_codex_login_command(device_auth=True) == [
        "codex",
        "login",
        "--device-auth",
    ]
    assert build_codex_status_command() == ["codex", "login", "status"]
    assert build_codex_logout_command() == ["codex", "logout"]


def test_resolve_model_credentials_uses_codex_auth_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "codex-access-token",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    credentials = resolve_model_credentials()

    assert credentials.token == "codex-access-token"
    assert credentials.base_url == DEFAULT_CODEX_BASE_URL
    assert credentials.source == "codex_auth_file"
