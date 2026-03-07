from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .backend import DigestBackend, OpenAIDigestBackend
from .config import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_RUNS_PATH,
    DEFAULT_TAXONOMY_PATH,
    DEFAULT_WINDOW_MINUTES,
)
from .io import (
    load_previous_threads,
    load_taxonomy,
    load_timeline_records,
    resolve_fresh_cutoff,
    save_next_state,
    write_json,
)
from .models import DigestRunResult
from .steps import (
    assemble_units,
    build_candidates,
    categorize_units,
    cluster_issues,
    extract_signals,
    filter_units,
    render_digest,
    select_report_records,
)


def run_digest_report(
    *,
    timeline_file: Path,
    output_dir: Path = DEFAULT_REPORT_RUNS_PATH,
    state_file: Path,
    taxonomy_file: Path = DEFAULT_TAXONOMY_PATH,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
    model: str = DEFAULT_REPORT_MODEL,
    backend: DigestBackend | None = None,
) -> DigestRunResult:
    run_started_at = datetime.now(timezone.utc)
    run_id = run_started_at.strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    taxonomy = load_taxonomy(taxonomy_file)
    state_doc, previous_threads, last_run_at = load_previous_threads(state_file)
    cutoff = resolve_fresh_cutoff(
        now=run_started_at,
        last_run_at=last_run_at,
        window_minutes=window_minutes,
    )

    resolved_backend = backend or OpenAIDigestBackend(model=model)
    timeline_records = load_timeline_records(timeline_file)
    selected_records = select_report_records(
        records=timeline_records,
        previous_threads=previous_threads,
        fresh_cutoff=cutoff,
    )
    write_json(run_dir / "selected_entries.json", selected_records)

    candidates = build_candidates(selected_records)
    write_json(run_dir / "candidates.json", candidates)

    assembled_units = assemble_units(
        backend=resolved_backend,
        taxonomy=taxonomy,
        candidates=candidates,
    )
    write_json(run_dir / "assembled_units.json", assembled_units)

    categorized_units = categorize_units(
        backend=resolved_backend,
        taxonomy=taxonomy,
        units=assembled_units,
    )
    write_json(run_dir / "categorized_units.json", categorized_units)

    filtered_units = filter_units(
        categorized_units=categorized_units,
        taxonomy=taxonomy,
    )
    write_json(run_dir / "filtered_units.json", filtered_units)

    signal_units = extract_signals(
        backend=resolved_backend,
        taxonomy=taxonomy,
        units=filtered_units,
        previous_threads=previous_threads,
    )
    write_json(run_dir / "signals.json", signal_units)

    issues = cluster_issues(
        backend=resolved_backend,
        taxonomy=taxonomy,
        units=signal_units,
    )
    write_json(run_dir / "issues.json", issues)

    digest_markdown = render_digest(
        run_id=run_id,
        taxonomy=taxonomy,
        signals=signal_units,
        issues=issues,
    )
    digest_path = run_dir / "digest.md"
    digest_path.write_text(digest_markdown, encoding="utf-8")

    save_next_state(
        previous_doc=state_doc,
        signals=signal_units,
        run_started_at=run_started_at,
        state_path=state_file,
    )

    summary = {
        "run_id": run_id,
        "timeline_file": str(timeline_file),
        "state_file": str(state_file),
        "taxonomy_file": str(taxonomy_file),
        "window_minutes": window_minutes,
        "model": model,
        "selected_count": len(selected_records),
        "candidate_count": len(candidates),
        "kept_count": len(signal_units),
        "issue_count": len(issues),
        "heated_count": sum(1 for unit in signal_units if unit.heat_status == "heated"),
        "digest_path": str(digest_path),
    }
    write_json(run_dir / "run.json", summary)

    return DigestRunResult(
        run_id=run_id,
        run_dir=run_dir,
        digest_path=digest_path,
        selected_count=len(selected_records),
        kept_count=len(signal_units),
        issue_count=len(issues),
        heated_count=summary["heated_count"],
    )
