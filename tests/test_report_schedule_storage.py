from __future__ import annotations

from pathlib import Path

from xs2n.schemas.report_schedule import (
    LatestRunArgumentsDoc,
    ReportSchedule,
    ReportScheduleCatalog,
    ScheduleLastRun,
)
from xs2n.storage.report_schedules import load_report_schedules, save_report_schedules


def test_report_schedules_round_trip(tmp_path: Path) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    catalog = ReportScheduleCatalog(
        schedules=[
            ReportSchedule(
                name="morning-digest",
                cadence_kind="time",
                time_local="08:30",
                weekdays=["mon", "wed", "fri"],
                interval_hours=None,
                cron_expression=None,
                latest_arguments=LatestRunArgumentsDoc(
                    lookback_hours=12,
                    cookies_file="tmp/cookies.json",
                    limit=100,
                    timeline_file="tmp/timeline.json",
                    sources_file="tmp/sources.json",
                    home_latest=True,
                    output_dir="tmp/report_runs",
                    taxonomy_file="tmp/taxonomy.json",
                    model="gpt-5.4",
                    parallel_workers=6,
                ),
                working_directory="/tmp/xs2n",
                launcher_argv=["/opt/homebrew/bin/uv", "run", "xs2n"],
                log_dir="/tmp/xs2n/data/report_schedule_logs/morning-digest",
                last_run=ScheduleLastRun(
                    status="succeeded",
                    started_at="2026-03-18T08:30:00+00:00",
                    finished_at="2026-03-18T08:31:00+00:00",
                    exit_code=0,
                    run_id="20260318T083000Z",
                    digest_path="/tmp/xs2n/data/report_runs/20260318T083000Z/digest.md",
                    error_message=None,
                ),
            )
        ]
    )

    save_report_schedules(catalog, path=schedules_file)
    loaded = load_report_schedules(schedules_file)

    assert loaded == catalog
