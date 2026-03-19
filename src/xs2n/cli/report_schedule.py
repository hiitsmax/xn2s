from __future__ import annotations

import json
from pathlib import Path

import typer
from typer.models import OptionInfo

from xs2n.agents import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_PARALLEL_WORKERS,
    DEFAULT_REPORT_RUNS_PATH,
    DEFAULT_TAXONOMY_PATH,
)
from xs2n.profile.timeline import DEFAULT_IMPORT_TIMELINE
from xs2n.report_runtime import DEFAULT_COOKIES_PATH, LatestRunArguments
from xs2n.report_schedule import (
    DEFAULT_REPORT_SCHEDULE_LOCKS_PATH,
    build_schedule_definition,
    delete_schedule_definition,
    describe_schedule,
    get_schedule_definition,
    list_schedule_definitions,
    render_schedule_export,
    run_named_schedule,
    save_schedule_definition,
)
from xs2n.storage import DEFAULT_SOURCES_PATH, DEFAULT_TIMELINE_PATH
from xs2n.storage.report_schedules import DEFAULT_REPORT_SCHEDULES_PATH


schedule_app = typer.Typer(
    help="Manage named report schedule definitions.",
    no_args_is_help=True,
)


@schedule_app.callback()
def schedule_main() -> None:
    """Manage report schedule definitions and exports."""


@schedule_app.command("create")
def create(
    name: str,
    at: str | None = typer.Option(
        None,
        "--at",
        help="Run at a local HH:MM clock time.",
    ),
    weekdays: str | None = typer.Option(
        None,
        "--weekdays",
        help="Optional comma-separated weekdays for --at (mon,tue,...).",
    ),
    every_hours: int | None = typer.Option(
        None,
        "--every-hours",
        min=1,
        help="Run on a fixed hourly interval.",
    ),
    cron_expression: str | None = typer.Option(
        None,
        "--cron",
        help="Raw cron expression source of truth.",
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        help="Replace an existing schedule with the same name.",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        help="ISO datetime cutoff for timeline ingestion. Overrides --lookback-hours when provided.",
    ),
    lookback_hours: int = typer.Option(
        24,
        "--lookback-hours",
        min=1,
        help="When --since is omitted, ingest timeline entries from now minus this many hours.",
    ),
    cookies_file: Path = typer.Option(
        DEFAULT_COOKIES_PATH,
        "--cookies-file",
        help="Twikit cookies file for authenticated scraping.",
    ),
    limit: int = typer.Option(
        DEFAULT_IMPORT_TIMELINE,
        "--limit",
        min=1,
        help="Maximum number of timeline entries to ingest in this run.",
    ),
    timeline_file: Path = typer.Option(
        DEFAULT_TIMELINE_PATH,
        "--timeline-file",
        help="Where timeline entries are stored.",
    ),
    sources_file: Path = typer.Option(
        DEFAULT_SOURCES_PATH,
        "--sources-file",
        help="Where source handles are stored for batch ingestion.",
    ),
    home_latest: bool = typer.Option(
        False,
        "--home-latest",
        help="Use authenticated Home -> Following latest timeline instead of --from-sources.",
    ),
    output_dir: Path = typer.Option(
        DEFAULT_REPORT_RUNS_PATH,
        "--output-dir",
        help="Directory where report run artifacts are written.",
    ),
    taxonomy_file: Path = typer.Option(
        DEFAULT_TAXONOMY_PATH,
        "--taxonomy-file",
        help="Editable taxonomy JSON file.",
    ),
    model: str = typer.Option(
        DEFAULT_REPORT_MODEL,
        "--model",
        help="OpenAI model name used for structured digest steps.",
    ),
    parallel_workers: int = typer.Option(
        DEFAULT_REPORT_PARALLEL_WORKERS,
        "--parallel-workers",
        min=1,
        help="Worker count for parallel categorize/filter/process digest steps.",
    ),
    schedules_file: Path = typer.Option(
        DEFAULT_REPORT_SCHEDULES_PATH,
        "--schedules-file",
        help="Where report schedules are stored.",
    ),
) -> None:
    """Create or replace a named report schedule."""

    latest_arguments = LatestRunArguments(
        since=since,
        lookback_hours=lookback_hours,
        cookies_file=cookies_file,
        limit=limit,
        timeline_file=timeline_file,
        sources_file=sources_file,
        home_latest=home_latest,
        output_dir=output_dir,
        taxonomy_file=taxonomy_file,
        model=model,
        parallel_workers=parallel_workers,
    )
    schedule = build_schedule_definition(
        name=name,
        at=at,
        weekdays=weekdays,
        every_hours=every_hours,
        cron_expression=cron_expression,
        latest_arguments=latest_arguments,
    )
    save_schedule_definition(
        schedule,
        schedules_file=schedules_file,
        replace=replace,
    )
    typer.echo(f"Created report schedule {schedule.name}.")


@schedule_app.command("list")
def list_schedules(
    schedules_file: Path = typer.Option(
        DEFAULT_REPORT_SCHEDULES_PATH,
        "--schedules-file",
        help="Where report schedules are stored.",
    ),
) -> None:
    """List saved report schedules."""

    schedules = list_schedule_definitions(schedules_file=schedules_file)
    if not schedules:
        typer.echo("No report schedules defined.")
        return
    for schedule in schedules:
        typer.echo(describe_schedule(schedule))


@schedule_app.command("show")
def show(
    name: str,
    schedules_file: Path = typer.Option(
        DEFAULT_REPORT_SCHEDULES_PATH,
        "--schedules-file",
        help="Where report schedules are stored.",
    ),
) -> None:
    """Show one saved report schedule as JSON."""

    schedule = get_schedule_definition(name, schedules_file=schedules_file)
    typer.echo(json.dumps(schedule.model_dump(mode="json"), indent=2))


@schedule_app.command("run")
def run_schedule(
    name: str,
    schedules_file: Path = typer.Option(
        DEFAULT_REPORT_SCHEDULES_PATH,
        "--schedules-file",
        help="Where report schedules are stored.",
    ),
    lock_dir: Path = typer.Option(
        DEFAULT_REPORT_SCHEDULE_LOCKS_PATH,
        "--lock-dir",
        help="Directory used for schedule overlap locks.",
    ),
) -> None:
    """Run one saved report schedule."""

    resolved_lock_dir = (
        DEFAULT_REPORT_SCHEDULE_LOCKS_PATH
        if isinstance(lock_dir, OptionInfo)
        else lock_dir
    )
    run_named_schedule(
        name,
        schedules_file=schedules_file,
        lock_dir=resolved_lock_dir,
    )


@schedule_app.command("export")
def export_schedule(
    name: str,
    target: str = typer.Option(
        ...,
        "--target",
        help="Export target: cron, launchd, or systemd.",
    ),
    schedules_file: Path = typer.Option(
        DEFAULT_REPORT_SCHEDULES_PATH,
        "--schedules-file",
        help="Where report schedules are stored.",
    ),
) -> None:
    """Print install-ready export output for one saved schedule."""

    schedule = get_schedule_definition(name, schedules_file=schedules_file)
    try:
        rendered = render_schedule_export(schedule, target=target)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    typer.echo(rendered.rstrip())


@schedule_app.command("delete")
def delete(
    name: str,
    schedules_file: Path = typer.Option(
        DEFAULT_REPORT_SCHEDULES_PATH,
        "--schedules-file",
        help="Where report schedules are stored.",
    ),
) -> None:
    """Delete one saved report schedule."""

    deleted = delete_schedule_definition(name, schedules_file=schedules_file)
    typer.echo(f"Deleted report schedule {deleted.name}.")
