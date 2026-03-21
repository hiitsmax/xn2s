from __future__ import annotations

from dataclasses import InitVar, dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Callable

import typer

from xs2n.agents import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_RUNS_PATH,
)
from xs2n.cli.timeline import parse_since_datetime, run_timeline_ingestion
from xs2n.profile.timeline import DEFAULT_IMPORT_TIMELINE
from xs2n.schemas.run_events import RunEvent
from xs2n.storage import DEFAULT_SOURCES_PATH, DEFAULT_TIMELINE_PATH, load_timeline


DEFAULT_COOKIES_PATH = Path("cookies.json")


@dataclass(slots=True)
class RunCommand:
    label: str
    args: list[str]


@dataclass(slots=True)
class LatestReportResult:
    run_id: str
    run_dir: Path
    thread_count: int
    kept_count: int
    issue_count: int
    digest_path: Path


@dataclass(slots=True)
class IssuesRunArguments:
    timeline_file: Path = DEFAULT_TIMELINE_PATH
    output_dir: Path = DEFAULT_REPORT_RUNS_PATH
    model: str = DEFAULT_REPORT_MODEL

    @classmethod
    def from_form(
        cls,
        *,
        timeline_file: str | Path | None,
        output_dir: str | Path | None,
        model: str | None,
    ) -> IssuesRunArguments:
        return cls(
            timeline_file=_coerce_path(
                timeline_file,
                default=DEFAULT_TIMELINE_PATH,
            ),
            output_dir=_coerce_path(
                output_dir,
                default=DEFAULT_REPORT_RUNS_PATH,
            ),
            model=_coerce_text(model, default=DEFAULT_REPORT_MODEL),
        )

    def to_cli_args(self) -> list[str]:
        return [
            "report",
            "issues",
            "--timeline-file",
            str(self.timeline_file),
            "--output-dir",
            str(self.output_dir),
            "--model",
            self.model,
        ]

    def to_command(self) -> RunCommand:
        return RunCommand(label="report issues", args=self.to_cli_args())


@dataclass(slots=True)
class LatestRunArguments:
    since: str | None = None
    lookback_hours: int = 24
    cookies_file: Path = DEFAULT_COOKIES_PATH
    limit: int = DEFAULT_IMPORT_TIMELINE
    timeline_file: Path = DEFAULT_TIMELINE_PATH
    sources_file: Path = DEFAULT_SOURCES_PATH
    home_latest: bool = False
    output_dir: Path = DEFAULT_REPORT_RUNS_PATH
    model: str = DEFAULT_REPORT_MODEL
    taxonomy_file: InitVar[str | Path | None] = None
    parallel_workers: InitVar[str | int | None] = None

    @classmethod
    def from_form(
        cls,
        *,
        since: str | None,
        lookback_hours: str | int | None,
        cookies_file: str | Path | None,
        limit: str | int | None,
        timeline_file: str | Path | None,
        sources_file: str | Path | None,
        home_latest: bool,
        output_dir: str | Path | None,
        model: str | None,
        taxonomy_file: str | Path | None = None,
        parallel_workers: str | int | None = None,
    ) -> LatestRunArguments:
        normalized_since = _coerce_optional_text(since)
        return cls(
            since=normalized_since,
            lookback_hours=_coerce_positive_int(
                lookback_hours,
                default=24,
                field_name="Lookback hours",
            ),
            cookies_file=_coerce_path(
                cookies_file,
                default=DEFAULT_COOKIES_PATH,
            ),
            limit=_coerce_positive_int(
                limit,
                default=DEFAULT_IMPORT_TIMELINE,
                field_name="Timeline limit",
            ),
            timeline_file=_coerce_path(
                timeline_file,
                default=DEFAULT_TIMELINE_PATH,
            ),
            sources_file=_coerce_path(
                sources_file,
                default=DEFAULT_SOURCES_PATH,
            ),
            home_latest=home_latest,
            output_dir=_coerce_path(
                output_dir,
                default=DEFAULT_REPORT_RUNS_PATH,
            ),
            model=_coerce_text(model, default=DEFAULT_REPORT_MODEL),
        )

    def to_cli_args(self) -> list[str]:
        args = [
            "report",
            "latest",
            "--lookback-hours",
            str(self.lookback_hours),
            "--cookies-file",
            str(self.cookies_file),
            "--limit",
            str(self.limit),
            "--timeline-file",
            str(self.timeline_file),
            "--sources-file",
            str(self.sources_file),
            "--output-dir",
            str(self.output_dir),
            "--model",
            self.model,
        ]
        if self.since is not None:
            args.extend(["--since", self.since])
        if self.home_latest:
            args.append("--home-latest")
        return args

    def to_command(self) -> RunCommand:
        return RunCommand(label="report latest", args=self.to_cli_args())

    def to_following_refresh_command(self) -> RunCommand:
        return RunCommand(
            label="refresh following sources",
            args=[
                "onboard",
                "--refresh-following",
                "--cookies-file",
                str(self.cookies_file),
                "--sources-file",
                str(self.sources_file),
            ],
        )

    def to_storage_doc(self) -> dict[str, object]:
        return {
            "since": self.since,
            "lookback_hours": self.lookback_hours,
            "cookies_file": str(self.cookies_file),
            "limit": self.limit,
            "timeline_file": str(self.timeline_file),
            "sources_file": str(self.sources_file),
            "home_latest": self.home_latest,
            "output_dir": str(self.output_dir),
            "model": self.model,
        }

    @classmethod
    def from_storage_doc(cls, doc: dict[str, object]) -> LatestRunArguments:
        return cls(
            since=doc.get("since") if isinstance(doc.get("since"), str) else None,
            lookback_hours=int(doc.get("lookback_hours", 24)),
            cookies_file=Path(str(doc.get("cookies_file", DEFAULT_COOKIES_PATH))),
            limit=int(doc.get("limit", DEFAULT_IMPORT_TIMELINE)),
            timeline_file=Path(str(doc.get("timeline_file", DEFAULT_TIMELINE_PATH))),
            sources_file=Path(str(doc.get("sources_file", DEFAULT_SOURCES_PATH))),
            home_latest=bool(doc.get("home_latest", False)),
            output_dir=Path(str(doc.get("output_dir", DEFAULT_REPORT_RUNS_PATH))),
            model=str(doc.get("model", DEFAULT_REPORT_MODEL)),
        )


def resolve_latest_since(
    *,
    since: str | None,
    lookback_hours: int,
    now: datetime | None = None,
) -> datetime:
    if since is not None:
        return parse_since_datetime(since)
    reference_now = now or datetime.now(timezone.utc)
    return reference_now - timedelta(hours=lookback_hours)


def run_latest_report(
    arguments: LatestRunArguments,
    *,
    now: datetime | None = None,
    echo: Callable[[str], None] = typer.echo,
    run_timeline_ingestion_fn=None,
    run_issue_report_fn=None,
    render_issue_digest_html_fn=None,
    emit_event: Callable[[RunEvent], None] | None = None,
) -> LatestReportResult:
    run_timeline_ingestion_fn = run_timeline_ingestion_fn or run_timeline_ingestion
    if run_issue_report_fn is None or render_issue_digest_html_fn is None:
        from xs2n.agents import render_issue_digest_html, run_issue_report

        run_issue_report_fn = run_issue_report_fn or run_issue_report
        render_issue_digest_html_fn = (
            render_issue_digest_html_fn or render_issue_digest_html
        )

    since_datetime = resolve_latest_since(
        since=arguments.since,
        lookback_hours=arguments.lookback_hours,
        now=now,
    )
    since_value = since_datetime.isoformat()
    ingest_label = (
        "Home->Following latest timeline"
        if arguments.home_latest
        else "source timelines"
    )
    echo(
        f"Ingesting {ingest_label} before issue generation "
        f"(since {since_value})."
    )
    if emit_event is not None:
        emit_event(
            RunEvent(
                event="phase_started",
                message="Starting timeline ingestion.",
                phase="timeline_ingestion",
            )
        )

    run_timeline_ingestion_fn(
        account=None,
        from_sources=not arguments.home_latest,
        home_latest=arguments.home_latest,
        since=since_value,
        cookies_file=arguments.cookies_file,
        limit=arguments.limit,
        timeline_file=arguments.timeline_file,
        sources_file=arguments.sources_file,
    )
    if emit_event is not None:
        emit_event(
            RunEvent(
                event="phase_completed",
                message="Completed timeline ingestion.",
                phase="timeline_ingestion",
            )
        )

    timeline_window_file = arguments.output_dir / "timeline_window.json"
    timeline_window_file.parent.mkdir(parents=True, exist_ok=True)
    timeline_window_doc = _window_timeline_doc(
        timeline_file=arguments.timeline_file,
        since_datetime=since_datetime,
    )
    timeline_window_file.write_text(
        f"{json.dumps(timeline_window_doc, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )
    if emit_event is not None:
        emit_event(
            RunEvent(
                event="artifact_written",
                message="Wrote timeline window snapshot.",
                phase="timeline_window",
                artifact_path=str(timeline_window_file),
                counts={"entry_count": len(timeline_window_doc.get("entries", []))},
            )
        )

    issue_report_kwargs = {
        "timeline_file": timeline_window_file,
        "output_dir": arguments.output_dir,
        "model": arguments.model,
    }
    if emit_event is not None:
        issue_report_kwargs["emit_event"] = emit_event
    result = run_issue_report_fn(**issue_report_kwargs)

    render_kwargs = {"run_dir": result.run_dir}
    if emit_event is not None:
        render_kwargs["emit_event"] = emit_event
    digest_path = render_issue_digest_html_fn(**render_kwargs)
    echo(
        f"Latest issue run {result.run_id}: loaded {result.thread_count} threads, "
        f"kept {result.kept_count} threads, produced {result.issue_count} issues."
    )
    echo(f"Rendered HTML digest to {digest_path}.")
    return LatestReportResult(
        run_id=result.run_id,
        run_dir=result.run_dir,
        thread_count=result.thread_count,
        kept_count=result.kept_count,
        issue_count=result.issue_count,
        digest_path=digest_path,
    )


def _window_timeline_doc(
    *,
    timeline_file: Path,
    since_datetime: datetime,
) -> dict[str, list[dict[str, object]]]:
    doc = load_timeline(timeline_file)
    raw_entries = doc.get("entries", [])
    if not isinstance(raw_entries, list):
        return {"entries": []}

    filtered_entries: list[dict[str, object]] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        created_at = item.get("created_at")
        if not isinstance(created_at, str):
            continue
        try:
            item_datetime = parse_since_datetime(created_at)
        except typer.BadParameter:
            continue
        if item_datetime >= since_datetime:
            filtered_entries.append(item)
    return {"entries": filtered_entries}


def _coerce_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _coerce_text(value: str | None, *, default: str) -> str:
    normalized = _coerce_optional_text(value)
    return default if normalized is None else normalized


def _coerce_path(value: str | Path | None, *, default: Path) -> Path:
    if value is None:
        return default
    if isinstance(value, Path):
        return value
    normalized = value.strip()
    if not normalized:
        return default
    return Path(normalized)


def _coerce_positive_int(
    value: str | int | None,
    *,
    default: int,
    field_name: str,
) -> int:
    if value is None:
        return default

    if isinstance(value, int):
        normalized = value
    else:
        stripped = value.strip()
        if not stripped:
            return default
        try:
            normalized = int(stripped)
        except ValueError as error:
            raise ValueError(f"{field_name} must be a positive integer.") from error

    if normalized < 1:
        raise ValueError(f"{field_name} must be at least 1.")
    return normalized
