from __future__ import annotations

from pydantic import BaseModel


class ProviderStatus(BaseModel):
    status: str
    summary: str
    detail: str | None = None


class RunReadiness(BaseModel):
    digest_ready: bool
    latest_ready: bool


class AuthDoctorResult(BaseModel):
    codex: ProviderStatus
    x: ProviderStatus
    run_readiness: RunReadiness
