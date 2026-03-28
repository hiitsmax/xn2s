from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

import httpx

from xs2n.codex_auth import build_codex_login_command, run_codex_command
from xs2n.credentials import (
    DEFAULT_CODEX_AUTH_PATH,
    DEFAULT_CODEX_BASE_URL,
    _extract_access_token,
    _load_json,
    _read_codex_keychain_auth,
    _resolve_codex_home,
)


CODEX_OAUTH_AUTH_MODE = "codex_oauth"
CODEX_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
DEFAULT_CODEX_REFRESH_URL = "https://auth.openai.com/oauth/token"
DEFAULT_REFRESH_LEEWAY_SECONDS = 120


@dataclass(frozen=True, slots=True)
class CodexOAuthCredentials:
    token: str
    base_url: str
    source: str
    account_id: str | None = None


class CodexOAuthLoginRequiredError(RuntimeError):
    def __init__(self, message: str, *, login_command: list[str]) -> None:
        super().__init__(message)
        self.login_command = login_command


def run_codex_oauth_login(*, device_auth: bool = False) -> int:
    """Delegate the interactive login flow to the installed Codex CLI."""
    return run_codex_command(build_codex_login_command(device_auth=device_auth))


def resolve_codex_oauth_credentials(
    *,
    refresh_if_needed: bool = True,
    refresh_leeway_seconds: int = DEFAULT_REFRESH_LEEWAY_SECONDS,
) -> CodexOAuthCredentials:
    """Load Codex OAuth credentials, refreshing file-backed tokens when possible."""
    codex_home = _resolve_codex_home()
    auth_path = codex_home / DEFAULT_CODEX_AUTH_PATH
    auth_doc = _load_json(auth_path)
    if auth_doc is not None:
        refreshed_doc = auth_doc
        if refresh_if_needed and _token_is_expiring_soon(
            _extract_access_token(auth_doc),
            refresh_leeway_seconds=refresh_leeway_seconds,
        ):
            refreshed_doc = _refresh_auth_file(auth_path=auth_path, auth_doc=auth_doc)
        token = _extract_access_token(refreshed_doc)
        if token:
            return CodexOAuthCredentials(
                token=token,
                base_url=DEFAULT_CODEX_BASE_URL,
                source="codex_auth_file",
                account_id=_extract_account_id(refreshed_doc),
            )

    keychain_doc = _read_codex_keychain_auth(codex_home)
    keychain_token = _extract_access_token(keychain_doc)
    if keychain_token:
        return CodexOAuthCredentials(
            token=keychain_token,
            base_url=DEFAULT_CODEX_BASE_URL,
            source="codex_auth_keychain",
            account_id=_extract_account_id(keychain_doc),
        )

    login_command = build_codex_login_command()
    raise CodexOAuthLoginRequiredError(
        "No Codex OAuth credentials found. Run "
        f"`{' '.join(login_command)}` and retry.",
        login_command=login_command,
    )


def _extract_account_id(doc: dict[str, Any] | None) -> str | None:
    if not isinstance(doc, dict):
        return None
    tokens = doc.get("tokens")
    if not isinstance(tokens, dict):
        return None
    account_id = tokens.get("account_id")
    if isinstance(account_id, str) and account_id.strip():
        return account_id.strip()
    return None


def _token_is_expiring_soon(
    access_token: str | None,
    *,
    refresh_leeway_seconds: int,
) -> bool:
    if not access_token:
        return False
    expires_at = _extract_expiry(access_token)
    if expires_at is None:
        return False
    return expires_at <= datetime.now(timezone.utc).timestamp() + refresh_leeway_seconds


def _extract_expiry(access_token: str) -> float | None:
    parts = access_token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(f"{payload}{padding}")
        doc = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return None
    exp = doc.get("exp")
    if isinstance(exp, int | float):
        return float(exp)
    return None


def _refresh_auth_file(*, auth_path: Path, auth_doc: dict[str, Any]) -> dict[str, Any]:
    tokens = auth_doc.get("tokens")
    if not isinstance(tokens, dict):
        return auth_doc
    refresh_token = tokens.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token.strip():
        return auth_doc

    response = httpx.post(
        os.getenv("CODEX_REFRESH_TOKEN_URL_OVERRIDE", DEFAULT_CODEX_REFRESH_URL),
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CODEX_OAUTH_CLIENT_ID,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10.0,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        return auth_doc
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        return auth_doc

    updated_tokens = dict(tokens)
    updated_tokens["access_token"] = access_token.strip()
    if isinstance(payload.get("refresh_token"), str) and payload["refresh_token"].strip():
        updated_tokens["refresh_token"] = payload["refresh_token"].strip()
    if isinstance(payload.get("id_token"), str) and payload["id_token"].strip():
        updated_tokens["id_token"] = payload["id_token"].strip()

    refreshed_doc = dict(auth_doc)
    refreshed_doc["tokens"] = updated_tokens
    refreshed_doc["last_refresh"] = datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )
    auth_path.write_text(json.dumps(refreshed_doc), encoding="utf-8")
    return refreshed_doc
