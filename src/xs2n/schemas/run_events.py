from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class RunEvent(BaseModel):
    event: Literal[
        "run_started",
        "phase_started",
        "phase_completed",
        "artifact_written",
        "run_completed",
        "run_failed",
    ]
    message: str
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str | None = None
    phase: str | None = None
    artifact_path: str | None = None
    counts: dict[str, int] = Field(default_factory=dict)
