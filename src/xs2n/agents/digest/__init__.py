from __future__ import annotations

from .steps.load_threads import run as _load_threads
from .llm import DigestLLM
from .helpers import DEFAULT_TAXONOMY_DOC, virality_score
from xs2n.schemas.digest import (
    CategorizationResult,
    CategorySpec,
    DigestRunResult,
    FilterResult,
    Issue,
    IssueAssignmentResult,
    ProcessedThread,
    TaxonomyConfig,
    ThreadProcessResult,
    ThreadInput,
    TimelineRecord,
)
from .pipeline import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_RUNS_PATH,
    DEFAULT_TAXONOMY_PATH,
    run_digest_report,
)

_virality_score = virality_score

__all__ = [
    "CategorizationResult",
    "CategorySpec",
    "DEFAULT_REPORT_MODEL",
    "DEFAULT_REPORT_RUNS_PATH",
    "DEFAULT_TAXONOMY_DOC",
    "DEFAULT_TAXONOMY_PATH",
    "DigestRunResult",
    "FilterResult",
    "Issue",
    "IssueAssignmentResult",
    "DigestLLM",
    "ProcessedThread",
    "TaxonomyConfig",
    "ThreadProcessResult",
    "ThreadInput",
    "TimelineRecord",
    "_load_threads",
    "_virality_score",
    "run_digest_report",
]
