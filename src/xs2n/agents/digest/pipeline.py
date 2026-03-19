from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from xs2n.schemas.digest import (
    Issue,
    IssueReportRunResult,
    IssueThread,
    PhaseTrace,
)

from .helpers import write_json


DEFAULT_REPORT_RUNS_PATH = Path("data/report_runs")
DEFAULT_REPORT_MODEL = "gpt-5.4-mini"
DEFAULT_REPORT_PARALLEL_WORKERS = 1
DEFAULT_TAXONOMY_PATH = Path("docs/codex/report_taxonomy.json")


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    return max(int((finished_at - started_at).total_seconds() * 1000), 0)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest_title_from_issues(issues: list[Issue]) -> str:
    if issues:
        return issues[0].title
    return "No issue digest produced"


def run_issue_report(
    *,
    timeline_file: Path,
    output_dir: Path = DEFAULT_REPORT_RUNS_PATH,
    model: str = DEFAULT_REPORT_MODEL,
    llm: Any | None = None,
    run_dir: Path | None = None,
) -> IssueReportRunResult:
    from .llm import DigestLLM
    from .steps.filter_threads import run as filter_threads
    from .steps.group_issues import run as group_issues
    from .steps.load_threads import run as load_threads

    run_started_at = datetime.now(timezone.utc)
    resolved_run_dir = run_dir
    if resolved_run_dir is None:
        run_id = run_started_at.strftime("%Y%m%dT%H%M%SZ")
        resolved_run_dir = output_dir / run_id
    else:
        run_id = resolved_run_dir.name
    resolved_run_dir.mkdir(parents=True, exist_ok=True)

    phases_path = resolved_run_dir / "phases.json"
    phases: list[PhaseTrace] = []
    current_phase_name: str | None = None
    current_phase_started_at: datetime | None = None
    credential_source: str | None = None
    digest_title: str = "No issue digest produced"
    primary_artifact_path: Path | None = None
    threads: list[Any] = []
    filtered_threads: list[Any] = []
    issue_threads: list[Any] = []
    issues: list[Any] = []

    def write_phase_traces() -> None:
        write_json(phases_path, phases)

    def write_run_summary(
        *,
        status: str,
        finished_at: datetime | None = None,
        error: Exception | None = None,
        failed_phase: str | None = None,
    ) -> None:
        summary = {
            "run_id": run_id,
            "status": status,
            "started_at": run_started_at.isoformat(),
            "finished_at": finished_at.isoformat() if finished_at is not None else None,
            "duration_ms": (
                _duration_ms(run_started_at, finished_at)
                if finished_at is not None
                else None
            ),
            "timeline_file": str(timeline_file),
            "model": model,
            "credential_source": credential_source,
            "thread_count": len(threads),
            "kept_count": len([thread for thread in filtered_threads if thread.keep]),
            "issue_count": len(issues),
            "digest_title": digest_title,
            "primary_artifact_path": (
                str(primary_artifact_path) if primary_artifact_path is not None else None
            ),
            "digest_path": (
                str(primary_artifact_path) if primary_artifact_path is not None else None
            ),
            "phases_path": str(phases_path),
            "llm_calls_dir": str(resolved_run_dir / "llm_calls"),
            "phase_counts": {
                "threads": len(threads),
                "filtered_threads": len(filtered_threads),
                "kept_threads": len([thread for thread in filtered_threads if thread.keep]),
                "issue_threads": len(issue_threads),
                "issues": len(issues),
            },
            "last_completed_phase": phases[-1].name if phases else None,
            "failed_phase": failed_phase,
            "error_type": type(error).__name__ if error is not None else None,
            "error_message": str(error) if error is not None else None,
        }
        write_json(resolved_run_dir / "run.json", summary)

    def complete_phase(
        *,
        name: str,
        started_at: datetime,
        input_count: int,
        output_count: int,
        artifact_paths: list[Path],
        counts: dict[str, int] | None = None,
    ) -> None:
        finished_at = datetime.now(timezone.utc)
        phases.append(
            PhaseTrace(
                name=name,
                status="completed",
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=_duration_ms(started_at, finished_at),
                input_count=input_count,
                output_count=output_count,
                artifact_paths=[str(path) for path in artifact_paths],
                counts=counts or {},
            )
        )
        write_phase_traces()
        write_run_summary(status="running")

    write_phase_traces()
    write_run_summary(status="running")

    try:
        digest_llm = llm or DigestLLM(model=model)
        credential_source = getattr(digest_llm, "source", None)
        configure_run_logging = getattr(digest_llm, "configure_run_logging", None)
        if callable(configure_run_logging):
            configure_run_logging(run_dir=resolved_run_dir)
        write_run_summary(status="running")

        current_phase_name = "load_threads"
        current_phase_started_at = datetime.now(timezone.utc)
        threads = load_threads(timeline_file=timeline_file)
        threads_path = resolved_run_dir / "threads.json"
        write_json(threads_path, threads)
        complete_phase(
            name=current_phase_name,
            started_at=current_phase_started_at,
            input_count=1,
            output_count=len(threads),
            artifact_paths=[threads_path],
            counts={"threads": len(threads)},
        )

        current_phase_name = "filter_threads"
        current_phase_started_at = datetime.now(timezone.utc)
        filtered_threads = filter_threads(
            llm=digest_llm,
            threads=threads,
        )
        filtered_threads_path = resolved_run_dir / "filtered_threads.json"
        write_json(filtered_threads_path, filtered_threads)
        kept_thread_count = sum(1 for thread in filtered_threads if thread.keep)
        complete_phase(
            name=current_phase_name,
            started_at=current_phase_started_at,
            input_count=len(threads),
            output_count=len(filtered_threads),
            artifact_paths=[filtered_threads_path],
            counts={
                "filtered_threads": len(filtered_threads),
                "kept_threads": kept_thread_count,
            },
        )

        current_phase_name = "group_issues"
        current_phase_started_at = datetime.now(timezone.utc)
        issue_threads, issues = group_issues(
            llm=digest_llm,
            threads=filtered_threads,
        )
        issue_assignments_path = resolved_run_dir / "issue_assignments.json"
        issues_path = resolved_run_dir / "issues.json"
        write_json(issue_assignments_path, issue_threads)
        write_json(issues_path, issues)
        digest_title = _digest_title_from_issues(issues)
        complete_phase(
            name=current_phase_name,
            started_at=current_phase_started_at,
            input_count=kept_thread_count,
            output_count=len(issues),
            artifact_paths=[issue_assignments_path, issues_path],
            counts={
                "issue_threads": len(issue_threads),
                "issues": len(issues),
            },
        )
    except Exception as error:
        failed_at = datetime.now(timezone.utc)
        if current_phase_name is not None and current_phase_started_at is not None:
            phases.append(
                PhaseTrace(
                    name=current_phase_name,
                    status="failed",
                    started_at=current_phase_started_at,
                    finished_at=failed_at,
                    duration_ms=_duration_ms(current_phase_started_at, failed_at),
                    input_count=0,
                    output_count=0,
                    artifact_paths=[],
                    counts={},
                    error_type=type(error).__name__,
                    error_message=str(error),
                )
            )
        write_phase_traces()
        write_run_summary(
            status="failed",
            finished_at=failed_at,
            error=error,
            failed_phase=current_phase_name,
        )
        raise

    finished_at = datetime.now(timezone.utc)
    write_run_summary(status="completed", finished_at=finished_at)

    return IssueReportRunResult(
        run_id=run_id,
        run_dir=resolved_run_dir,
        thread_count=len(threads),
        kept_count=len([thread for thread in filtered_threads if thread.keep]),
        issue_count=len(issues),
    )


def render_issue_digest_html(*, run_dir: Path) -> Path:
    from .steps.render_digest_html import run as render_digest_html

    started_at = datetime.now(timezone.utc)
    run_doc = _load_json(run_dir / "run.json")
    if not isinstance(run_doc, dict):
        raise RuntimeError(f"Run metadata is missing or invalid in {run_dir / 'run.json'}.")

    issues_doc = _load_json(run_dir / "issues.json")
    issue_threads_doc = _load_json(run_dir / "issue_assignments.json")
    if not isinstance(issues_doc, list) or not isinstance(issue_threads_doc, list):
        raise RuntimeError("Run is missing issues.json or issue_assignments.json.")

    issues = [Issue.model_validate(item) for item in issues_doc if isinstance(item, dict)]
    issue_threads = [
        IssueThread.model_validate(item)
        for item in issue_threads_doc
        if isinstance(item, dict)
    ]

    digest_title = _digest_title_from_issues(issues)
    html_text = render_digest_html(
        run_id=str(run_doc.get("run_id") or run_dir.name),
        digest_title=digest_title,
        issues=issues,
        issue_threads=issue_threads,
    )
    html_path = run_dir / "digest.html"
    html_path.write_text(html_text, encoding="utf-8")

    run_doc["digest_title"] = digest_title
    run_doc["primary_artifact_path"] = str(html_path)
    run_doc["digest_path"] = str(html_path)
    write_json(run_dir / "run.json", run_doc)

    phases_path = run_dir / "phases.json"
    phases_doc = _load_json(phases_path)
    if not isinstance(phases_doc, list):
        phases_doc = []
    finished_at = datetime.now(timezone.utc)
    phases_doc.append(
        PhaseTrace(
            name="render_digest_html",
            status="completed",
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=_duration_ms(started_at, finished_at),
            input_count=len(issues),
            output_count=1,
            artifact_paths=[str(html_path)],
            counts={"issues": len(issues)},
        ).model_dump(mode="json")
    )
    write_json(phases_path, phases_doc)
    return html_path
