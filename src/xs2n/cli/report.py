from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess

import typer

from xs2n.agents import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_PARALLEL_WORKERS,
    DEFAULT_REPORT_RUNS_PATH,
    DEFAULT_TAXONOMY_PATH,
    run_digest_report,
)
from xs2n.cli.timeline import parse_since_datetime, run_timeline_ingestion
from xs2n.profile.timeline import DEFAULT_IMPORT_TIMELINE, IMPORT_TIMELINE_LIMIT
from xs2n.storage import DEFAULT_SOURCES_PATH, DEFAULT_TIMELINE_PATH

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


def _resolve_latest_since(
    *,
    since: str | None,
    lookback_hours: int,
    now: datetime | None = None,
) -> datetime:
    if since is not None:
        return parse_since_datetime(since)
    reference_now = now or datetime.now(timezone.utc)
    return reference_now - timedelta(hours=lookback_hours)


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


@report_app.command("digest")
def digest(
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
) -> None:
    """Generate a traceable markdown digest from timeline data."""

    try:
        result = run_digest_report(
            timeline_file=timeline_file,
            output_dir=output_dir,
            taxonomy_file=taxonomy_file,
            model=model,
            parallel_workers=parallel_workers,
        )
    except RuntimeError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error

    typer.echo(
        f"Digest run {result.run_id}: loaded {result.thread_count} threads, "
        f"kept {result.kept_count} threads, produced {result.issue_count} issues. "
        f"Saved markdown to {result.digest_path}."
    )


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
        Path("cookies.json"),
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
) -> None:
    """Ingest latest timeline data and render one digest."""

    since_datetime = _resolve_latest_since(
        since=since,
        lookback_hours=lookback_hours,
    )
    since_value = since_datetime.isoformat()

    ingest_label = (
        "Home->Following latest timeline"
        if home_latest
        else "source timelines"
    )
    typer.echo(
        f"Ingesting {ingest_label} before digest generation "
        f"(since {since_value})."
    )
    run_timeline_ingestion(
        account=None,
        from_sources=not home_latest,
        home_latest=home_latest,
        since=since_value,
        cookies_file=cookies_file,
        limit=limit,
        timeline_file=timeline_file,
        sources_file=sources_file,
    )

    try:
        result = run_digest_report(
            timeline_file=timeline_file,
            output_dir=output_dir,
            taxonomy_file=taxonomy_file,
            model=model,
            parallel_workers=parallel_workers,
        )
    except RuntimeError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error

    typer.echo(
        f"Latest digest run {result.run_id}: loaded {result.thread_count} threads, "
        f"kept {result.kept_count} threads, produced {result.issue_count} issues. "
        f"Saved markdown to {result.digest_path}."
    )
