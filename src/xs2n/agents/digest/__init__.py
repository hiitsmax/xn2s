from __future__ import annotations

import warnings
from typing import Any

from .steps.load_threads import run as _load_threads
from .llm import DigestLLM
from .helpers import virality_score
from xs2n.schemas.digest import (
    IssueReportRunResult,
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


def run_digest_report(*args: Any, **kwargs: Any) -> IssueReportRunResult:
    # Compatibility shim for the retired digest-first entrypoint.
    warnings.warn(
        "run_digest_report is deprecated; use run_issue_report instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return run_issue_report(*args, **kwargs)

__all__ = [
    "DEFAULT_REPORT_MODEL",
    "DEFAULT_REPORT_PARALLEL_WORKERS",
    "DEFAULT_REPORT_RUNS_PATH",
    "DEFAULT_TAXONOMY_PATH",
    "DigestLLM",
    "IssueReportRunResult",
    "TimelineRecord",
    "render_issue_digest_html",
    "run_issue_report",
]
