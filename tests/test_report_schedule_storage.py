from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from xs2n.schemas.report_schedule import (
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
                latest_arguments={
                    "lookback_hours": 12,
                    "cookies_file": "tmp/cookies.json",
                    "limit": 100,
                    "timeline_file": "tmp/timeline.json",
                    "sources_file": "tmp/sources.json",
                    "home_latest": True,
                    "output_dir": "tmp/report_runs",
                    "model": "gpt-5.4",
                },
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
    assert loaded.schedules[0].latest_arguments == catalog.schedules[0].latest_arguments
    assert loaded.schedules[0].last_run is None


def test_load_report_schedules_rejects_invalid_json(tmp_path: Path) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    schedules_file.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="report schedule catalog"):
        load_report_schedules(schedules_file)


def test_save_report_schedules_keeps_previous_file_on_replace_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    schedules_file.write_text('{"schedules":[{"name":"before"}]}\n', encoding="utf-8")
    catalog = ReportScheduleCatalog()
    replace_sources: list[Path] = []

    def fail_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        replace_sources.append(Path(source))
        raise OSError("disk full")

    monkeypatch.setattr("xs2n.storage.report_schedules.os.replace", fail_replace)

    with pytest.raises(OSError, match="disk full"):
        save_report_schedules(catalog, path=schedules_file)

    assert (
        schedules_file.read_text(encoding="utf-8")
        == '{"schedules":[{"name":"before"}]}\n'
    )
    assert replace_sources
    assert all(not source.exists() for source in replace_sources)


def test_load_report_schedules_accepts_legacy_fields_and_rewrites_compact(
    tmp_path: Path,
) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    schedules_file.write_text(
        json.dumps(
            {
                "schedules": [
                    {
                        "name": "morning-digest",
                        "cadence_kind": "hours",
                        "interval_hours": 6,
                        "latest_arguments": {
                            "lookback_hours": 24,
                            "cookies_file": "tmp/cookies.json",
                            "limit": 100,
                            "timeline_file": "tmp/timeline.json",
                            "sources_file": "tmp/sources.json",
                            "home_latest": False,
                            "output_dir": "tmp/report_runs",
                            "taxonomy_file": "tmp/taxonomy.json",
                            "model": "gpt-5.4",
                            "parallel_workers": 6,
                        },
                        "working_directory": "/tmp/xs2n",
                        "launcher_argv": ["/opt/homebrew/bin/uv", "run", "xs2n"],
                        "log_dir": "/tmp/xs2n/data/report_schedule_logs/morning-digest",
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = load_report_schedules(schedules_file)
    save_report_schedules(loaded, path=schedules_file)
    rewritten = json.loads(schedules_file.read_text(encoding="utf-8"))

    schedule = rewritten["schedules"][0]
    assert "taxonomy_file" not in schedule["latest_arguments"]
    assert "parallel_workers" not in schedule["latest_arguments"]
    assert "working_directory" not in schedule
    assert "launcher_argv" not in schedule
    assert "log_dir" not in schedule


def test_save_report_schedules_strips_last_run_from_catalog(
    tmp_path: Path,
) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    catalog = ReportScheduleCatalog(
        schedules=[
            ReportSchedule(
                name="morning-digest",
                cadence_kind="time",
                time_local="08:30",
                weekdays=[],
                latest_arguments={"lookback_hours": 24},
                last_run=ScheduleLastRun(
                    status="succeeded",
                    started_at="2026-03-18T08:30:00+00:00",
                    finished_at="2026-03-18T08:31:00+00:00",
                    exit_code=0,
                ),
            )
        ]
    )

    save_report_schedules(catalog, path=schedules_file)
    rewritten = json.loads(schedules_file.read_text(encoding="utf-8"))

    assert "last_run" not in rewritten["schedules"][0] or rewritten["schedules"][0]["last_run"] is None
