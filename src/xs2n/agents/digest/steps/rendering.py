from __future__ import annotations

from datetime import datetime, timezone

from ..config import DEFAULT_MAX_STANDOUT_SIGNALS
from ..models import IssueCluster, SignalUnit, TaxonomyConfig


def _render_source_links(urls: list[str]) -> str:
    if not urls:
        return "No direct source link captured."
    return ", ".join(
        f"[source {index + 1}]({url})"
        for index, url in enumerate(urls)
    )


def render_digest(
    *,
    run_id: str,
    taxonomy: TaxonomyConfig,
    signals: list[SignalUnit],
    issues: list[IssueCluster],
) -> str:
    issued_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    by_unit_id = {unit.unit_id: unit for unit in signals}
    lines = [
        f"# xs2n Digest Issue {run_id}",
        "",
        f"_Generated {issued_at}. Categories loaded: {', '.join(category.slug for category in taxonomy.categories)}._",
        "",
        "## Top Issues",
        "",
    ]

    if not issues:
        lines.extend(
            [
                "No high-signal issue clusters were produced in this run.",
                "",
            ]
        )
    else:
        for issue in issues:
            issue_units = [
                by_unit_id[unit_id]
                for unit_id in issue.unit_ids
                if unit_id in by_unit_id
            ]
            if not issue_units:
                continue
            lines.append(f"### {issue.title}")
            lines.append("")
            lines.append(issue.summary)
            lines.append("")
            for unit in issue_units:
                lines.append(f"- **{unit.headline}** ({unit.category}) — {unit.main_claim}")
                lines.append(f"  Sources: {_render_source_links(unit.source_urls)}")
            lines.append("")

    lines.extend(["## Heated Threads Watch", ""])
    heated_units = [
        unit
        for unit in signals
        if unit.heat_status in {"heated", "still_active", "cooling_off"}
    ]
    if not heated_units:
        lines.extend(["No heated threads were tracked in this run.", ""])
    else:
        for unit in sorted(
            heated_units,
            key=lambda item: (item.heat_status != "heated", item.virality_score * -1),
        ):
            lines.append(
                f"- **{unit.title}** — {unit.heat_status.replace('_', ' ')}; momentum: {unit.momentum}; "
                f"signal: {unit.signal_score}; virality: {unit.virality_score:.2f}"
            )
            if unit.disagreement_summary:
                lines.append(f"  Disagreement: {unit.disagreement_summary}")
            lines.append(f"  Sources: {_render_source_links(unit.source_urls)}")
        lines.append("")

    lines.extend(["## Standout Signals", ""])
    for unit in signals[:DEFAULT_MAX_STANDOUT_SIGNALS]:
        lines.append(f"### {unit.headline}")
        lines.append("")
        lines.append(unit.why_it_matters)
        lines.append("")
        lines.append(f"- Claim: {unit.main_claim}")
        if unit.key_entities:
            lines.append(f"- Entities: {', '.join(unit.key_entities)}")
        lines.append(
            f"- Category: {unit.category}; Heat: {unit.heat_status.replace('_', ' ')}; Momentum: {unit.momentum}"
        )
        lines.append(f"- Sources: {_render_source_links(unit.source_urls)}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
