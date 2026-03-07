from __future__ import annotations

from datetime import datetime, timezone

from xs2n.schemas.digest import Issue, IssueThread, TaxonomyConfig

from ..helpers import render_source_links


DEFAULT_MAX_STANDOUT_THREADS = 6


def run(
    *,
    run_id: str,
    taxonomy: TaxonomyConfig,
    issue_threads: list[IssueThread],
    issues: list[Issue],
) -> str:
    issued_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    by_thread_id = {thread.thread_id: thread for thread in issue_threads}
    visible_issue_slugs = {issue.slug for issue in issues}
    standout_threads = [
        thread
        for thread in issue_threads
        if thread.issue_slug in visible_issue_slugs
    ]
    standout_threads.sort(
        key=lambda thread: (thread.signal_score, thread.virality_score),
        reverse=True,
    )

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
                "No high-signal issues were produced in this run.",
                "",
            ]
        )
    else:
        for issue in issues:
            issue_members = [
                by_thread_id[thread_id]
                for thread_id in issue.thread_ids
                if thread_id in by_thread_id
            ]
            if not issue_members:
                continue
            lines.append(f"### {issue.title}")
            lines.append("")
            lines.append(issue.summary)
            lines.append("")
            for thread in issue_members:
                lines.append(
                    f"- **{thread.headline}** ({thread.category}; virality {thread.virality_score:.2f}) — "
                    f"{thread.main_claim}"
                )
                lines.append(f"  Why it belongs: {thread.why_this_thread_belongs}")
                lines.append(f"  Sources: {render_source_links(thread.source_urls)}")
            lines.append("")

    lines.extend(["## Standout Threads", ""])
    if not standout_threads:
        lines.extend(
            [
                "No processed threads were kept in this run.",
                "",
            ]
        )
    else:
        for thread in standout_threads[:DEFAULT_MAX_STANDOUT_THREADS]:
            lines.append(f"### {thread.headline}")
            lines.append("")
            lines.append(thread.why_it_matters)
            lines.append("")
            lines.append(f"- Claim: {thread.main_claim}")
            if thread.key_entities:
                lines.append(f"- Entities: {', '.join(thread.key_entities)}")
            lines.append(
                f"- Category: {thread.category}; Novelty: {thread.novelty_label}; Signal: {thread.signal_score}; "
                f"Virality: {thread.virality_score:.2f}"
            )
            if thread.disagreement_summary:
                lines.append(f"- Disagreement: {thread.disagreement_summary}")
            lines.append(f"- Sources: {render_source_links(thread.source_urls)}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"
