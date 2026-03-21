from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from xs2n.cli.report_schedule import (
    create,
    delete,
    export_schedule,
    list_schedules,
    run_schedule,
    show,
)


def test_schedule_create_persists_definition(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schedules_file = tmp_path / "report_schedules.json"

    create(
        name="morning-digest",
        at="08:30",
        weekdays="mon,wed,fri",
        every_hours=None,
        cron_expression=None,
        replace=False,
        since=None,
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=True,
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4",
        schedules_file=schedules_file,
    )

    schedule_doc = json.loads(schedules_file.read_text(encoding="utf-8"))
    schedule = schedule_doc["schedules"][0]

    assert schedule["name"] == "morning-digest"
    assert schedule["cadence_kind"] == "time"
    assert schedule["time_local"] == "08:30"
    assert schedule["weekdays"] == ["mon", "wed", "fri"]
    assert schedule["latest_arguments"]["home_latest"] is True
    assert "taxonomy_file" not in schedule["latest_arguments"]
    assert "parallel_workers" not in schedule["latest_arguments"]
    assert "launcher_argv" not in schedule
    assert "working_directory" not in schedule
    assert "log_dir" not in schedule
    assert "Created report schedule morning-digest." in capsys.readouterr().out


def test_schedule_list_show_and_delete(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    create(
        name="morning-digest",
        at="08:30",
        weekdays=None,
        every_hours=None,
        cron_expression=None,
        replace=False,
        since=None,
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=False,
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4",
        schedules_file=schedules_file,
    )

    list_schedules(schedules_file=schedules_file)
    show(name="morning-digest", schedules_file=schedules_file)
    delete(name="morning-digest", schedules_file=schedules_file)

    output = capsys.readouterr().out
    assert "morning-digest" in output
    assert '"cadence_kind": "time"' in output
    assert "Deleted report schedule morning-digest." in output
    assert json.loads(schedules_file.read_text(encoding="utf-8")) == {"schedules": []}


def test_schedule_run_updates_last_run_on_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    create(
        name="morning-digest",
        at=None,
        weekdays=None,
        every_hours=6,
        cron_expression=None,
        replace=False,
        since=None,
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=False,
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4",
        schedules_file=schedules_file,
    )
    monkeypatch.setattr(
        "xs2n.report_schedule.runner.run_latest_report",
        lambda arguments: SimpleNamespace(
            run_id="20260318T190000Z",
            digest_path=tmp_path / "report_runs" / "20260318T190000Z" / "digest.md",
        ),
    )

    run_schedule(name="morning-digest", schedules_file=schedules_file)

    from xs2n.report_schedule.catalog import get_schedule_definition

    schedule = get_schedule_definition("morning-digest", schedules_file=schedules_file)
    assert schedule.last_run is not None
    assert schedule.last_run.status == "succeeded"
    assert schedule.last_run.exit_code == 0
    assert schedule.last_run.run_id == "20260318T190000Z"
    assert schedule.last_run.digest_path is not None
    assert schedule.last_run.digest_path.endswith("digest.md")


def test_schedule_run_records_locked_skip(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    create(
        name="morning-digest",
        at=None,
        weekdays=None,
        every_hours=6,
        cron_expression=None,
        replace=False,
        since=None,
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=False,
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4",
        schedules_file=schedules_file,
    )
    lock_dir = tmp_path / "report_schedule_locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    (lock_dir / "morning-digest.lock").write_text(
        f"{os.getpid()}\n",
        encoding="utf-8",
    )

    run_schedule(
        name="morning-digest",
        schedules_file=schedules_file,
        lock_dir=lock_dir,
    )

    from xs2n.report_schedule.catalog import get_schedule_definition

    schedule = get_schedule_definition("morning-digest", schedules_file=schedules_file)
    assert schedule.last_run is not None
    assert schedule.last_run.status == "skipped_locked"
    assert schedule.last_run.exit_code == 0
    assert "already running" in capsys.readouterr().out


def test_schedule_run_reclaims_stale_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    create(
        name="morning-digest",
        at=None,
        weekdays=None,
        every_hours=6,
        cron_expression=None,
        replace=False,
        since=None,
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=False,
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4",
        schedules_file=schedules_file,
    )
    lock_dir = tmp_path / "report_schedule_locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "morning-digest.lock"
    lock_path.write_text("999999\n", encoding="utf-8")
    monkeypatch.setattr(
        "xs2n.report_schedule.runner.run_latest_report",
        lambda arguments: SimpleNamespace(
            run_id="20260318T190000Z",
            digest_path=tmp_path / "report_runs" / "20260318T190000Z" / "digest.md",
        ),
    )

    run_schedule(
        name="morning-digest",
        schedules_file=schedules_file,
        lock_dir=lock_dir,
    )

    from xs2n.report_schedule.catalog import get_schedule_definition

    schedule = get_schedule_definition("morning-digest", schedules_file=schedules_file)
    assert schedule.last_run is not None
    assert schedule.last_run.status == "succeeded"
    assert not lock_path.exists()


def test_schedule_run_records_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    create(
        name="morning-digest",
        at=None,
        weekdays=None,
        every_hours=6,
        cron_expression=None,
        replace=False,
        since=None,
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=False,
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4",
        schedules_file=schedules_file,
    )
    monkeypatch.setattr(
        "xs2n.report_schedule.runner.run_latest_report",
        lambda arguments: (_ for _ in ()).throw(RuntimeError("digest exploded")),
    )

    with pytest.raises(typer.Exit) as error:
        run_schedule(name="morning-digest", schedules_file=schedules_file)

    assert error.value.exit_code == 1
    from xs2n.report_schedule.catalog import get_schedule_definition

    schedule = get_schedule_definition("morning-digest", schedules_file=schedules_file)
    assert schedule.last_run is not None
    assert schedule.last_run.status == "failed"
    assert schedule.last_run.error_message == "digest exploded"


def test_schedule_export_prints_target_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    create(
        name="morning-digest",
        at="08:30",
        weekdays="mon,fri",
        every_hours=None,
        cron_expression=None,
        replace=False,
        since=None,
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=False,
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4",
        schedules_file=schedules_file,
    )

    export_schedule(name="morning-digest", target="cron", schedules_file=schedules_file)
    cron_output = capsys.readouterr().out
    assert "report schedule run morning-digest" in cron_output

    export_schedule(name="morning-digest", target="launchd", schedules_file=schedules_file)
    launchd_output = capsys.readouterr().out
    assert "<key>ProgramArguments</key>" in launchd_output
    assert "<key>StartCalendarInterval</key>" in launchd_output

    export_schedule(name="morning-digest", target="systemd", schedules_file=schedules_file)
    systemd_output = capsys.readouterr().out
    assert "[Timer]" in systemd_output
    assert "OnCalendar=" in systemd_output


def test_schedule_export_rejects_raw_cron_for_non_cron_targets(
    tmp_path: Path,
) -> None:
    schedules_file = tmp_path / "report_schedules.json"
    create(
        name="morning-digest",
        at=None,
        weekdays=None,
        every_hours=None,
        cron_expression="15 8 * * 1-5",
        replace=False,
        since=None,
        lookback_hours=24,
        cookies_file=tmp_path / "cookies.json",
        limit=120,
        timeline_file=tmp_path / "timeline.json",
        sources_file=tmp_path / "sources.json",
        home_latest=False,
        output_dir=tmp_path / "report_runs",
        model="gpt-5.4",
        schedules_file=schedules_file,
    )

    with pytest.raises(typer.BadParameter):
        export_schedule(name="morning-digest", target="launchd", schedules_file=schedules_file)

    with pytest.raises(typer.BadParameter):
        export_schedule(name="morning-digest", target="systemd", schedules_file=schedules_file)
