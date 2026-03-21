from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ScheduleLastRun(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    run_id: str | None = None
    digest_path: str | None = None
    error_message: str | None = None


class ReportSchedule(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    cadence_kind: str
    time_local: str | None = None
    weekdays: list[str] = Field(default_factory=list)
    interval_hours: int | None = None
    cron_expression: str | None = None
    latest_arguments: dict[str, object] = Field(default_factory=dict)
    last_run: ScheduleLastRun | None = None


class ReportScheduleCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedules: list[ReportSchedule] = Field(default_factory=list)
