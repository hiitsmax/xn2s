from __future__ import annotations

from .steps.load_threads import run as _load_threads
from .llm import DigestLLM
from .helpers import virality_score
from xs2n.schemas.digest import (
    FilteredThread,
    Issue,
    IssueReportRunResult,
    IssueSelectionResult,
    IssueThread,
    IssueWriteResult,
    ThreadFilterResult,
    ThreadInput,
    TimelineMedia,
    TimelineRecord,
)
from .pipeline import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_PARALLEL_WORKERS,
    DEFAULT_REPORT_RUNS_PATH,
    DEFAULT_TAXONOMY_PATH,
    render_issue_digest_html,
    run_issue_report,
)

_virality_score = virality_score
run_digest_report = run_issue_report

__all__ = [
    "DEFAULT_REPORT_MODEL",
    "DEFAULT_REPORT_PARALLEL_WORKERS",
    "DEFAULT_REPORT_RUNS_PATH",
    "DEFAULT_TAXONOMY_PATH",
    "DigestLLM",
    "FilteredThread",
    "Issue",
    "IssueReportRunResult",
    "IssueSelectionResult",
    "IssueThread",
    "IssueWriteResult",
    "ThreadFilterResult",
    "ThreadInput",
    "TimelineMedia",
    "TimelineRecord",
    "_load_threads",
    "_virality_score",
    "render_issue_digest_html",
    "run_digest_report",
    "run_issue_report",
]
