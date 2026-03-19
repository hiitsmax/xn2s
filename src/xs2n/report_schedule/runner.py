from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

import typer

from xs2n.report_runtime import run_latest_report
from xs2n.schemas.report_schedule import ScheduleLastRun
from xs2n.storage.report_schedules import DEFAULT_REPORT_SCHEDULES_PATH

from .catalog import (
    get_schedule_definition,
    latest_arguments_from_schedule,
    update_schedule_last_run,
)


DEFAULT_REPORT_SCHEDULE_LOCKS_PATH = Path("data/report_schedule_locks")


class _TeeStream:
    def __init__(self, *streams) -> None:
        self._streams = streams

    def write(self, chunk: str) -> int:
        for stream in self._streams:
            stream.write(chunk)
            stream.flush()
        return len(chunk)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def run_named_schedule(
    name: str,
    *,
    schedules_file: Path = DEFAULT_REPORT_SCHEDULES_PATH,
    lock_dir: Path = DEFAULT_REPORT_SCHEDULE_LOCKS_PATH,
) -> ScheduleLastRun:
    schedule = get_schedule_definition(name, schedules_file=schedules_file)
    return run_schedule_definition(
        schedule_name=schedule.name,
        latest_arguments=latest_arguments_from_schedule(schedule),
        log_dir=Path(schedule.log_dir),
        schedules_file=schedules_file,
        lock_dir=lock_dir,
    )


def run_schedule_definition(
    *,
    schedule_name: str,
    latest_arguments,
    log_dir: Path,
    schedules_file: Path,
    lock_dir: Path,
) -> ScheduleLastRun:
    started_at = datetime.now(timezone.utc)
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{schedule_name}.lock"

    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        last_run = ScheduleLastRun(
            status="skipped_locked",
            started_at=started_at.isoformat(),
            finished_at=datetime.now(timezone.utc).isoformat(),
            exit_code=0,
            run_id=None,
            digest_path=None,
            error_message="Schedule is already running.",
        )
        update_schedule_last_run(
            schedule_name,
            last_run,
            schedules_file=schedules_file,
        )
        typer.echo(f"Report schedule {schedule_name} is already running; skipping.")
        return last_run

    try:
        os.write(lock_fd, f"{os.getpid()}\n".encode("utf-8"))
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")
        stdout_path = log_dir / f"{timestamp}.stdout.log"
        stderr_path = log_dir / f"{timestamp}.stderr.log"

        with stdout_path.open("w", encoding="utf-8") as stdout_file:
            with stderr_path.open("w", encoding="utf-8") as stderr_file:
                stdout_tee = _TeeStream(sys.stdout, stdout_file)
                stderr_tee = _TeeStream(sys.stderr, stderr_file)
                with redirect_stdout(stdout_tee), redirect_stderr(stderr_tee):
                    try:
                        result = run_latest_report(latest_arguments)
                    except typer.Exit as error:
                        exit_code = error.exit_code or 1
                        last_run = ScheduleLastRun(
                            status="failed",
                            started_at=started_at.isoformat(),
                            finished_at=datetime.now(timezone.utc).isoformat(),
                            exit_code=exit_code,
                            run_id=None,
                            digest_path=None,
                            error_message=(
                                str(error) or f"Schedule exited with code {exit_code}."
                            ),
                        )
                        update_schedule_last_run(
                            schedule_name,
                            last_run,
                            schedules_file=schedules_file,
                        )
                        raise typer.Exit(code=exit_code) from error
                    except Exception as error:
                        last_run = ScheduleLastRun(
                            status="failed",
                            started_at=started_at.isoformat(),
                            finished_at=datetime.now(timezone.utc).isoformat(),
                            exit_code=1,
                            run_id=None,
                            digest_path=None,
                            error_message=str(error),
                        )
                        update_schedule_last_run(
                            schedule_name,
                            last_run,
                            schedules_file=schedules_file,
                        )
                        raise typer.Exit(code=1) from error

        last_run = ScheduleLastRun(
            status="succeeded",
            started_at=started_at.isoformat(),
            finished_at=datetime.now(timezone.utc).isoformat(),
            exit_code=0,
            run_id=result.run_id,
            digest_path=str(result.digest_path),
            error_message=None,
        )
        update_schedule_last_run(
            schedule_name,
            last_run,
            schedules_file=schedules_file,
        )
        return last_run
    finally:
        os.close(lock_fd)
        lock_path.unlink(missing_ok=True)
