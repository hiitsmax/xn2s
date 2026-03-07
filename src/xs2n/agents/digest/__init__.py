from __future__ import annotations

from .load_threads import run as _load_threads
from .llm import DigestLLM
from xs2n.models.digest import (
    CategorizationResult,
    CategorySpec,
    DigestRunResult,
    FilterResult,
    Issue,
    IssueAssignmentResult,
    SignalResult,
    TaxonomyConfig,
    ThreadInput,
    TimelineRecord,
)
from .pipeline import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_RUNS_PATH,
    DEFAULT_TAXONOMY_DOC,
    DEFAULT_TAXONOMY_PATH,
    run_digest_report,
    virality_score,
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
    "SignalResult",
    "TaxonomyConfig",
    "ThreadInput",
    "TimelineRecord",
    "_load_threads",
    "_virality_score",
    "run_digest_report",
]
