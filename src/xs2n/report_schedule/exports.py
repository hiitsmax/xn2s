from __future__ import annotations

from pathlib import Path
import plistlib
import re
import shlex

from xs2n.schemas.report_schedule import ReportSchedule

from .catalog import (
    resolve_schedule_launcher_argv,
    resolve_schedule_log_dir,
    resolve_schedule_working_directory,
)


_SYSTEMD_DAY_NAMES = {
    "mon": "Mon",
    "tue": "Tue",
    "wed": "Wed",
    "thu": "Thu",
    "fri": "Fri",
    "sat": "Sat",
    "sun": "Sun",
}
_LAUNCHD_WEEKDAYS = {
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
    "sun": 7,
}


def render_schedule_export(schedule: ReportSchedule, *, target: str) -> str:
    normalized_target = target.strip().lower()
    if normalized_target == "cron":
        return _render_cron_export(schedule)
    if normalized_target == "launchd":
        return _render_launchd_export(schedule)
    if normalized_target == "systemd":
        return _render_systemd_export(schedule)
    raise ValueError("Export target must be one of: cron, launchd, systemd.")


def _render_cron_export(schedule: ReportSchedule) -> str:
    command = _render_shell_command(schedule)
    if schedule.cadence_kind == "time":
        hour, minute = _split_time(schedule.time_local)
        day_of_week = (
            "*"
            if not schedule.weekdays
            else ",".join(day.upper() for day in schedule.weekdays)
        )
        return f"{minute} {hour} * * {day_of_week} {command}"

    if schedule.cadence_kind == "hours":
        return f"0 */{schedule.interval_hours} * * * {command}"

    return f"{schedule.cron_expression} {command}"


def _render_launchd_export(schedule: ReportSchedule) -> str:
    _require_friendly_cadence(schedule, target="launchd")
    log_dir = resolve_schedule_log_dir(schedule.name)
    plist_doc: dict[str, object] = {
        "Label": _schedule_unit_name(schedule.name, prefix="xs2n.report.schedule."),
        "ProgramArguments": _schedule_command_argv(schedule),
        "WorkingDirectory": str(resolve_schedule_working_directory()),
        "StandardOutPath": str(log_dir / "launchd.stdout.log"),
        "StandardErrorPath": str(log_dir / "launchd.stderr.log"),
    }
    if schedule.cadence_kind == "time":
        hour, minute = _split_time(schedule.time_local)
        if schedule.weekdays:
            plist_doc["StartCalendarInterval"] = [
                {
                    "Weekday": _LAUNCHD_WEEKDAYS[weekday],
                    "Hour": hour,
                    "Minute": minute,
                }
                for weekday in schedule.weekdays
            ]
        else:
            plist_doc["StartCalendarInterval"] = {
                "Hour": hour,
                "Minute": minute,
            }
    else:
        plist_doc["StartInterval"] = schedule.interval_hours * 3600

    return plistlib.dumps(plist_doc, sort_keys=False).decode("utf-8")


def _render_systemd_export(schedule: ReportSchedule) -> str:
    _require_friendly_cadence(schedule, target="systemd")
    unit_name = _schedule_unit_name(schedule.name, prefix="xs2n-report-schedule-")
    log_dir = resolve_schedule_log_dir(schedule.name)
    service = "\n".join(
        [
            f"# {unit_name}.service",
            "[Unit]",
            f"Description=Run xs2n report schedule {schedule.name}",
            "",
            "[Service]",
            "Type=oneshot",
            f"WorkingDirectory={resolve_schedule_working_directory()}",
            f"ExecStart={shlex.join(_schedule_command_argv(schedule))}",
            f"StandardOutput=append:{log_dir / 'systemd.stdout.log'}",
            f"StandardError=append:{log_dir / 'systemd.stderr.log'}",
        ]
    )
    if schedule.cadence_kind == "time":
        if schedule.weekdays:
            weekday_part = ",".join(_SYSTEMD_DAY_NAMES[day] for day in schedule.weekdays)
            calendar_value = f"{weekday_part} *-*-* {schedule.time_local}:00"
        else:
            calendar_value = f"*-*-* {schedule.time_local}:00"
    else:
        calendar_value = None

    timer_lines = [
        f"# {unit_name}.timer",
        "[Unit]",
        f"Description=Schedule xs2n report schedule {schedule.name}",
        "",
        "[Timer]",
        "Persistent=true",
    ]
    if calendar_value is not None:
        timer_lines.append(f"OnCalendar={calendar_value}")
    else:
        timer_lines.append(f"OnUnitActiveSec={schedule.interval_hours}h")
    timer_lines.extend(
        [
            f"Unit={unit_name}.service",
            "",
            "[Install]",
            "WantedBy=timers.target",
        ]
    )
    timer_body = "\n".join(timer_lines)
    return f"{service}\n\n{timer_body}\n"


def _render_shell_command(schedule: ReportSchedule) -> str:
    log_dir = resolve_schedule_log_dir(schedule.name)
    stdout_path = log_dir / "cron.stdout.log"
    stderr_path = log_dir / "cron.stderr.log"
    command = shlex.join(_schedule_command_argv(schedule))
    return (
        f"cd {shlex.quote(str(resolve_schedule_working_directory()))} && "
        f"{command} >> {shlex.quote(str(stdout_path))} "
        f"2>> {shlex.quote(str(stderr_path))}"
    )


def _schedule_command_argv(schedule: ReportSchedule) -> list[str]:
    return [*resolve_schedule_launcher_argv(), "report", "schedule", "run", schedule.name]


def _split_time(value: str | None) -> tuple[int, int]:
    if value is None:
        raise ValueError("Time-based schedules require time_local.")
    hour_text, minute_text = value.split(":", maxsplit=1)
    return int(hour_text), int(minute_text)


def _require_friendly_cadence(schedule: ReportSchedule, *, target: str) -> None:
    if schedule.cadence_kind == "cron":
        raise ValueError(
            f"Schedules created with --cron can only be exported to cron in v1, not {target}."
        )


def _schedule_unit_name(name: str, *, prefix: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-")
    return f"{prefix}{sanitized or 'schedule'}"
