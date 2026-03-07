from __future__ import annotations

from .backend import DigestBackend, OpenAIDigestBackend
from .config import (
    DEFAULT_REPORT_MODEL,
    DEFAULT_REPORT_RUNS_PATH,
    DEFAULT_TAXONOMY_DOC,
    DEFAULT_TAXONOMY_PATH,
    DEFAULT_WINDOW_MINUTES,
)
from .models import (
    AssemblyResult,
    CategorizationResult,
    ConversationCandidate,
    DigestRunResult,
    FilteredUnit,
    IssueCluster,
    IssueClusterResult,
    SignalResult,
    ThreadState,
    TimelineRecord,
)
from .pipeline import run_digest_report
from .steps import build_candidates, select_report_records, virality_score

_build_candidates = build_candidates
_select_report_records = select_report_records
_virality_score = virality_score

__all__ = [
    "AssemblyResult",
    "CategorizationResult",
    "ConversationCandidate",
    "DEFAULT_REPORT_MODEL",
    "DEFAULT_REPORT_RUNS_PATH",
    "DEFAULT_TAXONOMY_DOC",
    "DEFAULT_TAXONOMY_PATH",
    "DEFAULT_WINDOW_MINUTES",
    "DigestBackend",
    "DigestRunResult",
    "FilteredUnit",
    "IssueCluster",
    "IssueClusterResult",
    "OpenAIDigestBackend",
    "SignalResult",
    "ThreadState",
    "TimelineRecord",
    "_build_candidates",
    "_select_report_records",
    "_virality_score",
    "run_digest_report",
]
