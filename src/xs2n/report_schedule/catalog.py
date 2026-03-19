from __future__ import annotations

from pathlib import Path
import re
import shutil

import typer

from xs2n.report_runtime import LatestRunArguments
from xs2n.schemas.report_schedule import (
    LatestRunArgumentsDoc,
    ReportSchedule,
    ScheduleLastRun,
)
from xs2n.storage.report_schedules import (
    DEFAULT_REPORT_SCHEDULES_PATH,
    load_report_schedules,
    save_report_schedules,
)


_VALID_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_VALID_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_REPO_ROOT = Path(__file__).resolve().parents[3]


def build_schedule_definition(
    *,
    name: str,
    at: str | None,
    weekdays: str | None,
    every_hours: int | None,
    cron_expression: str | None,
    latest_arguments: LatestRunArguments,
) -> ReportSchedule:
    normalized_name = _normalize_schedule_name(name)
    cadence_kind, time_local, weekday_values, interval_hours, cron_value = _resolve_cadence(
        at=at,
        weekdays=weekdays,
        every_hours=every_hours,
        cron_expression=cron_expression,
    )
    launcher_argv = _resolve_launcher_argv()
    working_directory = str(_REPO_ROOT)
    log_dir = str(
        (_REPO_ROOT / "data" / "report_schedule_logs" / normalized_name).resolve()
    )

    return ReportSchedule(
        name=normalized_name,
        cadence_kind=cadence_kind,
        time_local=time_local,
        weekdays=weekday_values,
        interval_hours=interval_hours,
        cron_expression=cron_value,
        latest_arguments=LatestRunArgumentsDoc.model_validate(
            latest_arguments.to_storage_doc()
        ),
        working_directory=working_directory,
        launcher_argv=launcher_argv,
        log_dir=log_dir,
        last_run=None,
    )


def save_schedule_definition(
    schedule: ReportSchedule,
    *,
    schedules_file: Path = DEFAULT_REPORT_SCHEDULES_PATH,
    replace: bool = False,
) -> ReportSchedule:
    catalog = load_report_schedules(schedules_file)
    for index, existing in enumerate(catalog.schedules):
        if existing.name != schedule.name:
            continue
        if not replace:
            raise typer.BadParameter(
                f"Report schedule {schedule.name} already exists. Use --replace to overwrite it."
            )
        catalog.schedules[index] = schedule
        save_report_schedules(catalog, path=schedules_file)
        return schedule

    catalog.schedules.append(schedule)
    catalog.schedules.sort(key=lambda item: item.name)
    save_report_schedules(catalog, path=schedules_file)
    return schedule


def list_schedule_definitions(
    *,
    schedules_file: Path = DEFAULT_REPORT_SCHEDULES_PATH,
) -> list[ReportSchedule]:
    return load_report_schedules(schedules_file).schedules


def get_schedule_definition(
    name: str,
    *,
    schedules_file: Path = DEFAULT_REPORT_SCHEDULES_PATH,
) -> ReportSchedule:
    normalized_name = _normalize_schedule_name(name)
    for schedule in load_report_schedules(schedules_file).schedules:
        if schedule.name == normalized_name:
            return schedule
    raise typer.BadParameter(f"Report schedule {normalized_name} does not exist.")


def delete_schedule_definition(
    name: str,
    *,
    schedules_file: Path = DEFAULT_REPORT_SCHEDULES_PATH,
) -> ReportSchedule:
    normalized_name = _normalize_schedule_name(name)
    catalog = load_report_schedules(schedules_file)
    for index, schedule in enumerate(catalog.schedules):
        if schedule.name != normalized_name:
            continue
        removed = catalog.schedules.pop(index)
        save_report_schedules(catalog, path=schedules_file)
        return removed
    raise typer.BadParameter(f"Report schedule {normalized_name} does not exist.")


def update_schedule_last_run(
    name: str,
    last_run: ScheduleLastRun,
    *,
    schedules_file: Path = DEFAULT_REPORT_SCHEDULES_PATH,
) -> ReportSchedule:
    normalized_name = _normalize_schedule_name(name)
    catalog = load_report_schedules(schedules_file)
    for index, schedule in enumerate(catalog.schedules):
        if schedule.name != normalized_name:
            continue
        updated = schedule.model_copy(update={"last_run": last_run})
        catalog.schedules[index] = updated
        save_report_schedules(catalog, path=schedules_file)
        return updated
    raise typer.BadParameter(f"Report schedule {normalized_name} does not exist.")


def describe_schedule(schedule: ReportSchedule) -> str:
    if schedule.cadence_kind == "time":
        if schedule.weekdays:
            return f"{schedule.name}: at {schedule.time_local} on {','.join(schedule.weekdays)}"
        return f"{schedule.name}: at {schedule.time_local} daily"
    if schedule.cadence_kind == "hours":
        return f"{schedule.name}: every {schedule.interval_hours} hours"
    return f"{schedule.name}: cron {schedule.cron_expression}"


def latest_arguments_from_schedule(schedule: ReportSchedule) -> LatestRunArguments:
    return LatestRunArguments.from_storage_doc(
        schedule.latest_arguments.model_dump(mode="json")
    )


def _normalize_schedule_name(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise typer.BadParameter("Schedule name cannot be blank.")
    if not _VALID_NAME_RE.fullmatch(candidate):
        raise typer.BadParameter(
            "Schedule name must start with a letter or number and use only letters, numbers, dots, underscores, or dashes."
        )
    return candidate


def _resolve_cadence(
    *,
    at: str | None,
    weekdays: str | None,
    every_hours: int | None,
    cron_expression: str | None,
) -> tuple[str, str | None, list[str], int | None, str | None]:
    active_modes = sum(
        (
            at is not None,
            every_hours is not None,
            cron_expression is not None,
        )
    )
    if active_modes != 1:
        raise typer.BadParameter(
            "Use exactly one cadence: --at, --every-hours, or --cron."
        )

    if at is not None:
        return (
            "time",
            _normalize_time_local(at),
            _parse_weekdays(weekdays),
            None,
            None,
        )

    if weekdays is not None:
        raise typer.BadParameter("--weekdays can only be used together with --at.")

    if every_hours is not None:
        if every_hours < 1:
            raise typer.BadParameter("--every-hours must be at least 1.")
        return ("hours", None, [], every_hours, None)

    normalized_cron = (cron_expression or "").strip()
    if not normalized_cron:
        raise typer.BadParameter("--cron cannot be blank.")
    return ("cron", None, [], None, normalized_cron)


def _normalize_time_local(value: str) -> str:
    candidate = value.strip()
    match = re.fullmatch(r"(\d{2}):(\d{2})", candidate)
    if match is None:
        raise typer.BadParameter("--at must use HH:MM 24-hour format.")
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        raise typer.BadParameter("--at must use a valid 24-hour clock time.")
    return f"{hour:02d}:{minute:02d}"


def _parse_weekdays(value: str | None) -> list[str]:
    if value is None:
        return []
    normalized = [item.strip().lower() for item in value.split(",") if item.strip()]
    if not normalized:
        return []
    invalid = [item for item in normalized if item not in _VALID_WEEKDAYS]
    if invalid:
        raise typer.BadParameter(
            "Use weekdays from mon,tue,wed,thu,fri,sat,sun."
        )
    seen: list[str] = []
    for item in normalized:
        if item not in seen:
            seen.append(item)
    return seen


def _resolve_launcher_argv() -> list[str]:
    for command in ("uv", "xs2n"):
        resolved = shutil.which(command)
        if resolved is None:
            continue
        executable = str(Path(resolved).resolve())
        if command == "uv":
            return [executable, "run", "xs2n"]
        return [executable]
    raise typer.BadParameter(
        "Could not resolve a runnable `uv` or `xs2n` binary for schedule execution."
    )
