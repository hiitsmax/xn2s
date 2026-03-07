from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xs2n.schemas.digest import DigestRunResult

from .helpers import load_taxonomy, write_json


DEFAULT_REPORT_RUNS_PATH = Path("data/report_runs")
DEFAULT_TAXONOMY_PATH = Path("docs/codex/report_taxonomy.json")
DEFAULT_REPORT_MODEL = "gpt-5.4"


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

    digest_llm = llm or DigestLLM(model=model)
    run_started_at = datetime.now(timezone.utc)
    run_id = run_started_at.strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    taxonomy = load_taxonomy(taxonomy_file)
    threads = load_threads(timeline_file=timeline_file)
    write_json(run_dir / "threads.json", threads)

    categorized_threads = categorize_threads(
        llm=digest_llm,
        taxonomy=taxonomy,
        threads=threads,
    )
    write_json(run_dir / "categorized_threads.json", categorized_threads)

    filtered_threads = filter_threads(
        llm=digest_llm,
        taxonomy=taxonomy,
        threads=categorized_threads,
    )
    write_json(run_dir / "filtered_threads.json", filtered_threads)

    processed_threads = process_threads(
        llm=digest_llm,
        threads=filtered_threads,
    )
    write_json(run_dir / "processed_threads.json", processed_threads)

    issue_threads, issues = group_issues(
        llm=digest_llm,
        threads=processed_threads,
    )
    write_json(run_dir / "issue_assignments.json", issue_threads)
    write_json(run_dir / "issues.json", issues)

    digest_markdown = render_digest(
        run_id=run_id,
        taxonomy=taxonomy,
        issue_threads=issue_threads,
        issues=issues,
    )
    digest_path = run_dir / "digest.md"
    digest_path.write_text(digest_markdown, encoding="utf-8")

    summary = {
        "run_id": run_id,
        "timeline_file": str(timeline_file),
        "taxonomy_file": str(taxonomy_file),
        "model": model,
        "thread_count": len(threads),
        "kept_count": len(processed_threads),
        "issue_count": len(issues),
        "digest_path": str(digest_path),
    }
    write_json(run_dir / "run.json", summary)

    return DigestRunResult(
        run_id=run_id,
        run_dir=run_dir,
        digest_path=digest_path,
        thread_count=len(threads),
        kept_count=len(processed_threads),
        issue_count=len(issues),
    )
