from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import typer
from typer.models import OptionInfo

from xs2n.agents.digest.pipeline import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_RUNS_PATH,
    render_issue_digest_html,
    run_issue_report,
)
from xs2n.cli.timeline import run_timeline_ingestion
from xs2n.profile.timeline import DEFAULT_IMPORT_TIMELINE, IMPORT_TIMELINE_LIMIT
from xs2n.report_runtime import (
    DEFAULT_COOKIES_PATH,
    LatestRunArguments,
    resolve_latest_since as _resolve_latest_since,
    run_latest_report,
)
from xs2n.schemas.run_events import RunEvent
from xs2n.storage.sources import DEFAULT_SOURCES_PATH
from xs2n.storage.timeline import DEFAULT_TIMELINE_PATH

report_app = typer.Typer(
    help="Report pipeline commands.",
    no_args_is_help=True,
)


@report_app.callback()
def report_main() -> None:
    """Manage report pipeline utilities."""


def _run_codex_command(command: list[str]) -> None:
    try:
        completed = subprocess.run(command, check=False)
    except FileNotFoundError as error:
        typer.echo(
            "Could not find the Codex CLI binary. Install it with "
            "`npm install -g @openai/codex` and retry.",
            err=True,
        )
        raise typer.Exit(code=1) from error
    except OSError as error:
        typer.echo(f"Could not run {' '.join(command)}: {error}", err=True)
        raise typer.Exit(code=1) from error

    if completed.returncode != 0:
        raise typer.Exit(code=completed.returncode or 1)


def _render_saved_issue_run_html(*, run_dir: Path) -> Path:
    try:
        return render_issue_digest_html(run_dir=run_dir)
    except RuntimeError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error


def _build_human_echo(*, jsonl_events: bool):
    return lambda message: typer.echo(message, err=jsonl_events)


def _emit_jsonl_event(event: RunEvent) -> None:
    sys.stdout.write(event.model_dump_json() + "\n")
    sys.stdout.flush()


def _resolve_bool_option(value: bool | OptionInfo) -> bool:
    if isinstance(value, OptionInfo):
        return bool(value.default)
    return value


@report_app.command("auth")
def auth(
    status: bool = typer.Option(
        False,
        "--status",
        help="Show Codex authentication status.",
    ),
    logout: bool = typer.Option(
        False,
        "--logout",
        help="Log out from Codex authentication.",
    ),
    device_auth: bool = typer.Option(
        False,
        "--device-auth",
        help="Use Codex device-code auth flow for headless environments.",
    ),
    codex_bin: str = typer.Option(
        "codex",
        "--codex-bin",
        help="Codex CLI executable name/path.",
    ),
) -> None:
    """Authenticate report pipeline access via ChatGPT Codex auth."""

    if status and logout:
        raise typer.BadParameter("Use either --status or --logout, not both.")
    if (status or logout) and device_auth:
        raise typer.BadParameter("--device-auth can only be used for login.")

    if status:
        _run_codex_command([codex_bin, "login", "status"])
        return

    if logout:
        _run_codex_command([codex_bin, "logout"])
        return

    command = [codex_bin, "login"]
    if device_auth:
        command.append("--device-auth")
    _run_codex_command(command)


@report_app.command("issues")
def issues(
    timeline_file: Path = typer.Option(
        DEFAULT_TIMELINE_PATH,
        "--timeline-file",
        help="Timeline JSON with thread data produced by ingestion.",
    ),
    output_dir: Path = typer.Option(
        DEFAULT_REPORT_RUNS_PATH,
        "--output-dir",
        help="Directory where report run artifacts are written.",
    ),
    model: str = typer.Option(
        DEFAULT_REPORT_MODEL,
        "--model",
        help="OpenAI model name used for the loose filter and issue-building steps.",
    ),
    jsonl_events: bool = typer.Option(
        False,
        "--jsonl-events",
        help=(
            "Emit machine-readable JSONL progress events to stdout and route "
            "human-readable messages to stderr."
        ),
    ),
) -> None:
    """Build issue artifacts from timeline data."""

    resolved_jsonl_events = _resolve_bool_option(jsonl_events)
    human_echo = _build_human_echo(jsonl_events=resolved_jsonl_events)
    emit_event = _emit_jsonl_event if resolved_jsonl_events else None
    try:
        result = run_issue_report(
            timeline_file=timeline_file,
            output_dir=output_dir,
            model=model,
            emit_event=emit_event,
        )
    except RuntimeError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error

    human_echo(
        f"Issue run {result.run_id}: loaded {result.thread_count} threads, "
        f"kept {result.kept_count} threads, produced {result.issue_count} issues."
    )
    human_echo(f"Render later with: xs2n report html --run-dir {result.run_dir}")


@report_app.command("html")
def html_render(
    run_dir: Path = typer.Option(
        ...,
        "--run-dir",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Existing run directory containing issues.json and issue_assignments.json.",
    ),
) -> None:
    """Render one saved run into HTML."""

    html_path = _render_saved_issue_run_html(run_dir=run_dir)
    typer.echo(f"Rendered HTML digest to {html_path}.")


@report_app.command("latest")
def latest(
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
        max=IMPORT_TIMELINE_LIMIT,
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
        help=(
            "Ingest the authenticated Home -> Following latest timeline "
            "instead of crawling source handles from --sources-file."
        ),
    ),
    output_dir: Path = typer.Option(
        DEFAULT_REPORT_RUNS_PATH,
        "--output-dir",
        help="Directory where report run artifacts are written.",
    ),
    model: str = typer.Option(
        DEFAULT_REPORT_MODEL,
        "--model",
        help="OpenAI model name used for the loose filter and issue-building steps.",
    ),
    jsonl_events: bool = typer.Option(
        False,
        "--jsonl-events",
        help=(
            "Emit machine-readable JSONL progress events to stdout and route "
            "human-readable messages to stderr."
        ),
    ),
) -> None:
    """Ingest latest timeline data, build issues, and render HTML."""

    resolved_home_latest = _resolve_bool_option(home_latest)
    resolved_jsonl_events = _resolve_bool_option(jsonl_events)
    arguments = LatestRunArguments(
        since=since,
        lookback_hours=lookback_hours,
        cookies_file=cookies_file,
        limit=limit,
        timeline_file=timeline_file,
        sources_file=sources_file,
        home_latest=resolved_home_latest,
        output_dir=output_dir,
        model=model,
    )

    try:
        human_echo = _build_human_echo(jsonl_events=resolved_jsonl_events)
        run_latest_report(
            arguments,
            echo=human_echo,
            run_timeline_ingestion_fn=run_timeline_ingestion,
            run_issue_report_fn=run_issue_report,
            render_issue_digest_html_fn=render_issue_digest_html,
            emit_event=_emit_jsonl_event if resolved_jsonl_events else None,
        )
    except RuntimeError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
