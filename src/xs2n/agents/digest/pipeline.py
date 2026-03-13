from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xs2n.schemas.digest import DigestRunResult, PhaseTrace

from .helpers import load_taxonomy, write_json


DEFAULT_REPORT_RUNS_PATH = Path("data/report_runs")
DEFAULT_TAXONOMY_PATH = Path("docs/codex/report_taxonomy.json")
DEFAULT_REPORT_MODEL = "gpt-5.4"


def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
    return max(int((finished_at - started_at).total_seconds() * 1000), 0)


def run_digest_report(
    *,
    timeline_file: Path,
    output_dir: Path = DEFAULT_REPORT_RUNS_PATH,
    taxonomy_file: Path = DEFAULT_TAXONOMY_PATH,
    model: str = DEFAULT_REPORT_MODEL,
    llm: Any | None = None,
) -> DigestRunResult:
    from .llm import DigestLLM
    from .steps.categorize_threads import run as categorize_threads
    from .steps.filter_threads import run as filter_threads
    from .steps.group_issues import run as group_issues
    from .steps.load_threads import run as load_threads
    from .steps.process_threads import run as process_threads
    from .steps.render_digest import run as render_digest

    run_started_at = datetime.now(timezone.utc)
    run_id = run_started_at.strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    taxonomy_snapshot_path = run_dir / "taxonomy.json"
    phases_path = run_dir / "phases.json"
    llm_calls_dir = run_dir / "llm_calls"
    phases: list[PhaseTrace] = []
    current_phase_name: str | None = None
    current_phase_started_at: datetime | None = None
    credential_source: str | None = None
    taxonomy = None
    digest_path: Path | None = None
    threads: list[Any] = []
    categorized_threads: list[Any] = []
    filtered_threads: list[Any] = []
    processed_threads: list[Any] = []
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
            "taxonomy_file": str(taxonomy_file),
            "taxonomy_snapshot_path": (
                str(taxonomy_snapshot_path)
                if taxonomy_snapshot_path.exists()
                else None
            ),
            "model": model,
            "credential_source": credential_source,
            "thread_count": len(threads),
            "kept_count": len(processed_threads),
            "issue_count": len(issues),
            "digest_path": str(digest_path) if digest_path is not None else None,
            "phases_path": str(phases_path),
            "llm_calls_dir": str(llm_calls_dir),
            "phase_counts": {
                "threads": len(threads),
                "categorized_threads": len(categorized_threads),
                "filtered_threads": len(filtered_threads),
                "kept_threads": len(processed_threads),
                "issue_threads": len(issue_threads),
                "issues": len(issues),
            },
            "last_completed_phase": phases[-1].name if phases else None,
            "failed_phase": failed_phase,
            "error_type": type(error).__name__ if error is not None else None,
            "error_message": str(error) if error is not None else None,
        }
        write_json(run_dir / "run.json", summary)

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
            configure_run_logging(run_dir=run_dir)
        write_run_summary(status="running")

        current_phase_name = "load_taxonomy"
        current_phase_started_at = datetime.now(timezone.utc)
        taxonomy = load_taxonomy(taxonomy_file)
        write_json(taxonomy_snapshot_path, taxonomy)
        complete_phase(
            name=current_phase_name,
            started_at=current_phase_started_at,
            input_count=1,
            output_count=len(taxonomy.categories),
            artifact_paths=[taxonomy_snapshot_path],
            counts={"categories": len(taxonomy.categories)},
        )

        current_phase_name = "load_threads"
        current_phase_started_at = datetime.now(timezone.utc)
        threads = load_threads(timeline_file=timeline_file)
        threads_path = run_dir / "threads.json"
        write_json(threads_path, threads)
        complete_phase(
            name=current_phase_name,
            started_at=current_phase_started_at,
            input_count=1,
            output_count=len(threads),
            artifact_paths=[threads_path],
            counts={"threads": len(threads)},
        )

        current_phase_name = "categorize_threads"
        current_phase_started_at = datetime.now(timezone.utc)
        categorized_threads = categorize_threads(
            llm=digest_llm,
            taxonomy=taxonomy,
            threads=threads,
        )
        categorized_threads_path = run_dir / "categorized_threads.json"
        write_json(categorized_threads_path, categorized_threads)
        complete_phase(
            name=current_phase_name,
            started_at=current_phase_started_at,
            input_count=len(threads),
            output_count=len(categorized_threads),
            artifact_paths=[categorized_threads_path],
            counts={"categorized_threads": len(categorized_threads)},
        )

        current_phase_name = "filter_threads"
        current_phase_started_at = datetime.now(timezone.utc)
        filtered_threads = filter_threads(
            llm=digest_llm,
            taxonomy=taxonomy,
            threads=categorized_threads,
        )
        filtered_threads_path = run_dir / "filtered_threads.json"
        write_json(filtered_threads_path, filtered_threads)
        kept_thread_count = sum(1 for thread in filtered_threads if thread.keep)
        complete_phase(
            name=current_phase_name,
            started_at=current_phase_started_at,
            input_count=len(categorized_threads),
            output_count=len(filtered_threads),
            artifact_paths=[filtered_threads_path],
            counts={
                "filtered_threads": len(filtered_threads),
                "kept_threads": kept_thread_count,
            },
        )

        current_phase_name = "process_threads"
        current_phase_started_at = datetime.now(timezone.utc)
        processed_threads = process_threads(
            llm=digest_llm,
            threads=filtered_threads,
        )
        processed_threads_path = run_dir / "processed_threads.json"
        write_json(processed_threads_path, processed_threads)
        complete_phase(
            name=current_phase_name,
            started_at=current_phase_started_at,
            input_count=kept_thread_count,
            output_count=len(processed_threads),
            artifact_paths=[processed_threads_path],
            counts={"processed_threads": len(processed_threads)},
        )

        current_phase_name = "group_issues"
        current_phase_started_at = datetime.now(timezone.utc)
        issue_threads, issues = group_issues(
            llm=digest_llm,
            threads=processed_threads,
        )
        issue_assignments_path = run_dir / "issue_assignments.json"
        issues_path = run_dir / "issues.json"
        write_json(issue_assignments_path, issue_threads)
        write_json(issues_path, issues)
        complete_phase(
            name=current_phase_name,
            started_at=current_phase_started_at,
            input_count=len(processed_threads),
            output_count=len(issues),
            artifact_paths=[issue_assignments_path, issues_path],
            counts={
                "issue_threads": len(issue_threads),
                "issues": len(issues),
            },
        )

        current_phase_name = "render_digest"
        current_phase_started_at = datetime.now(timezone.utc)
        digest_markdown = render_digest(
            run_id=run_id,
            taxonomy=taxonomy,
            issue_threads=issue_threads,
            issues=issues,
        )
        digest_path = run_dir / "digest.md"
        digest_path.write_text(digest_markdown, encoding="utf-8")
        complete_phase(
            name=current_phase_name,
            started_at=current_phase_started_at,
            input_count=len(issues),
            output_count=1,
            artifact_paths=[digest_path],
            counts={"issues": len(issues)},
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

    return DigestRunResult(
        run_id=run_id,
        run_dir=run_dir,
        digest_path=digest_path or run_dir / "digest.md",
        thread_count=len(threads),
        kept_count=len(processed_threads),
        issue_count=len(issues),
    )
