from __future__ import annotations

from ..backend import DigestBackend
from ..config import DEFAULT_MAX_ISSUES
from ..models import IssueCluster, SignalUnit, TaxonomyConfig


def cluster_issues(
    *,
    backend: DigestBackend,
    taxonomy: TaxonomyConfig,
    units: list[SignalUnit],
) -> list[IssueCluster]:
    if not units:
        return []
    cluster_result = backend.cluster_issues(taxonomy=taxonomy, units=units)
    known_unit_ids = {unit.unit_id for unit in units}
    clusters: list[IssueCluster] = []
    assigned: set[str] = set()
    for issue in cluster_result.issues:
        valid_ids = [
            unit_id
            for unit_id in issue.unit_ids
            if unit_id in known_unit_ids and unit_id not in assigned
        ]
        if not valid_ids:
            continue
        assigned.update(valid_ids)
        clusters.append(
            IssueCluster(
                title=issue.title,
                summary=issue.summary,
                unit_ids=valid_ids,
            )
        )

    unassigned = [unit for unit in units if unit.unit_id not in assigned]
    for unit in unassigned:
        clusters.append(
            IssueCluster(
                title=unit.headline,
                summary=unit.why_it_matters,
                unit_ids=[unit.unit_id],
            )
        )
    return clusters[:DEFAULT_MAX_ISSUES]
