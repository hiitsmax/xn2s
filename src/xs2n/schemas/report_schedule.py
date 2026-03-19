from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LatestRunArgumentsDoc(BaseModel):
    since: str | None = None
    lookback_hours: int = 24
    cookies_file: str = "cookies.json"
    limit: int = 100
    timeline_file: str = "data/timeline.json"
    sources_file: str = "data/sources.json"
    home_latest: bool = False
    output_dir: str = "data/report_runs"
    taxonomy_file: str = "docs/codex/report_taxonomy.json"
    model: str = "gpt-5.4"
    parallel_workers: int = 4


class ScheduleLastRun(BaseModel):
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    run_id: str | None = None
    digest_path: str | None = None
    error_message: str | None = None


class ReportSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    cadence_kind: str
    time_local: str | None = None
    weekdays: list[str] = Field(default_factory=list)
    interval_hours: int | None = None
    cron_expression: str | None = None
    latest_arguments: LatestRunArgumentsDoc
    working_directory: str
    launcher_argv: list[str]
    log_dir: str
    last_run: ScheduleLastRun | None = None


class ReportScheduleCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schedules: list[ReportSchedule] = Field(default_factory=list)
