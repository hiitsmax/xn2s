from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


DEFAULT_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
DEFAULT_CODEX_HOME = Path("~/.codex").expanduser()
DEFAULT_CODEX_AUTH_PATH = Path("auth.json")


@dataclass(frozen=True, slots=True)
class ResolvedDigestCredentials:
    token: str
    base_url: str | None
    source: str


def _resolve_codex_home() -> Path:
    configured = os.getenv("CODEX_HOME")
    candidate = Path(configured).expanduser() if configured else DEFAULT_CODEX_HOME
    try:
        return candidate.resolve()
    except OSError:
        return candidate


def _extract_access_token(doc: dict[str, Any] | None) -> str | None:
    if not isinstance(doc, dict):
        return None
    tokens = doc.get("tokens")
    if not isinstance(tokens, dict):
        return None
    access_token = tokens.get("access_token")
    if not isinstance(access_token, str):
        return None
    token = access_token.strip()
    return token or None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _compute_codex_keychain_account(codex_home: Path) -> str:
    digest = hashlib.sha256(str(codex_home).encode("utf-8")).hexdigest()
    return f"cli|{digest[:16]}"


def _read_codex_keychain_auth(codex_home: Path) -> dict[str, Any] | None:
    if sys.platform != "darwin":
        return None

    account = _compute_codex_keychain_account(codex_home)
    try:
        completed = subprocess.run(
            [
                "security",
                "find-generic-password",
                "-s",
                "Codex Auth",
                "-a",
                account,
                "-w",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError:
        return None

    if completed.returncode != 0:
        return None

    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def resolve_digest_credentials(api_key: str | None = None) -> ResolvedDigestCredentials:
    resolved_api_key = (api_key or os.getenv("OPENAI_API_KEY") or "").strip()
    if resolved_api_key:
        base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or None
        return ResolvedDigestCredentials(
            token=resolved_api_key,
            base_url=base_url,
            source="openai_api_key",
        )

    codex_home = _resolve_codex_home()
    auth_doc = _load_json(codex_home / DEFAULT_CODEX_AUTH_PATH)
    file_token = _extract_access_token(auth_doc)
    if file_token:
        return ResolvedDigestCredentials(
            token=file_token,
            base_url=DEFAULT_CODEX_BASE_URL,
            source="codex_auth_file",
        )

    keychain_doc = _read_codex_keychain_auth(codex_home)
    keychain_token = _extract_access_token(keychain_doc)
    if keychain_token:
        return ResolvedDigestCredentials(
            token=keychain_token,
            base_url=DEFAULT_CODEX_BASE_URL,
            source="codex_auth_keychain",
        )

    raise RuntimeError(
        "No model credentials found for `xs2n report digest`. "
        "Either export OPENAI_API_KEY or run `xs2n report auth` to log into Codex, then retry."
    )
