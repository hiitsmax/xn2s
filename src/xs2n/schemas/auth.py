from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel

ProviderStatusName = Literal["missing", "ready", "expired", "unverified"]
REQUIRED_X_SESSION_COOKIE_NAMES = frozenset({"auth_token", "ct0"})


def extract_valid_x_session_cookies(payload: Mapping[str, object] | None) -> dict[str, str] | None:
    if payload is None:
        return None

    cookies = {
        name: value
        for name, value in payload.items()
        if isinstance(name, str) and isinstance(value, str)
    }
    if not REQUIRED_X_SESSION_COOKIE_NAMES.issubset(cookies):
        return None
    return cookies


def require_valid_x_session_cookies(
    payload: Mapping[str, object] | None,
    *,
    error_message: str,
) -> dict[str, str]:
    cookies = extract_valid_x_session_cookies(payload)
    if cookies is None:
        raise RuntimeError(error_message)
    return cookies


class ProviderStatus(BaseModel):
    status: ProviderStatusName
    summary: str
    detail: str | None = None


class RunReadiness(BaseModel):
    digest_ready: bool
    latest_ready: bool


class AuthDoctorResult(BaseModel):
    codex: ProviderStatus
    x: ProviderStatus
    run_readiness: RunReadiness
