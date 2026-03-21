from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LatestRunArgumentsDoc(BaseModel):
    model_config = ConfigDict(extra="ignore")

    since: str | None = None
    lookback_hours: int = 24
    cookies_file: str = "cookies.json"
    limit: int = 100
    timeline_file: str = "data/timeline.json"
    sources_file: str = "data/sources.json"
    home_latest: bool = False
    output_dir: str = "data/report_runs"
    model: str = "gpt-5.4"


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
    latest_arguments: LatestRunArgumentsDoc
    last_run: ScheduleLastRun | None = None


class ReportScheduleCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedules: list[ReportSchedule] = Field(default_factory=list)
