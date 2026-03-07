from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from xs2n.storage import load_report_state, load_timeline, save_report_state


DEFAULT_REPORT_RUNS_PATH = Path("data/report_runs")
DEFAULT_TAXONOMY_PATH = Path("docs/codex/report_taxonomy.json")
DEFAULT_REPORT_MODEL = "gpt-4.1-mini"
DEFAULT_WINDOW_MINUTES = 10
DEFAULT_REPLY_PERCENTILE = 95.0
DEFAULT_KEEP_HEAT_STATUSES = {"heated", "still_active"}
DEFAULT_DROP_CATEGORIES = {"promo", "personal_update", "ai_slop"}
DEFAULT_MAX_STANDOUT_REPLIES = 5
DEFAULT_MAX_ISSUES = 6
DEFAULT_MAX_STANDOUT_SIGNALS = 6

DEFAULT_TAXONOMY_DOC = {
    "categories": [
        {
            "slug": "breaking_news",
            "label": "Breaking News",
            "description": "Fresh developments, disclosures, or events people need to know now.",
        },
        {
            "slug": "policy",
            "label": "Policy",
            "description": "Government, regulation, governance, or institutional moves.",
        },
        {
            "slug": "research",
            "label": "Research",
            "description": "Technical findings, experiments, papers, or deep analytical work.",
        },
        {
            "slug": "product_launch",
            "label": "Product Launch",
            "description": "Meaningful product, feature, or company launches.",
        },
        {
            "slug": "market_move",
            "label": "Market Move",
            "description": "Financial, trading, token, or business movement with market relevance.",
        },
        {
            "slug": "analysis",
            "label": "Analysis",
            "description": "Thoughtful interpretation, synthesis, or second-order thinking.",
        },
        {
            "slug": "first_hand_signal",
            "label": "First-Hand Signal",
            "description": "Direct observation, operator experience, leaks, or on-the-ground evidence.",
        },
        {
            "slug": "debate",
            "label": "Debate",
            "description": "An active disagreement, argument, or clash of interpretations.",
        },
        {
            "slug": "meta_discourse",
            "label": "Meta Discourse",
            "description": "Discussion about the platform, media dynamics, or narrative framing.",
        },
        {
            "slug": "meme",
            "label": "Meme",
            "description": "Humor, memes, or jokes that may still reveal a real trend or reaction.",
        },
        {
            "slug": "promo",
            "label": "Promo",
            "description": "Marketing, self-promotion, obvious calls to action, or shallow launch spam.",
        },
        {
            "slug": "personal_update",
            "label": "Personal Update",
            "description": "Personal status updates with low public-information value.",
        },
        {
            "slug": "ai_slop",
            "label": "AI Slop",
            "description": "Low-effort, repetitive, generic, or synthetic filler without signal.",
        },
    ],
    "drop_categories": ["promo", "personal_update", "ai_slop"],
}


class TimelineRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tweet_id: str
    account_handle: str
    author_handle: str
    kind: Literal["post", "reply", "retweet"]
    created_at: datetime
    text: str
    retweeted_tweet_id: str | None = None
    retweeted_author_handle: str | None = None
    retweeted_created_at: str | None = None
    in_reply_to_tweet_id: str | None = None
    conversation_id: str | None = None
    timeline_source: str | None = None
    favorite_count: int | None = None
    retweet_count: int | None = None
    reply_count: int | None = None
    quote_count: int | None = None
    view_count: int | None = None

    @property
    def source_url(self) -> str:
        return f"https://x.com/{self.author_handle}/status/{self.tweet_id}"

    @property
    def conversation_key(self) -> str:
        return self.conversation_id or self.tweet_id

    @property
    def authored_by_source(self) -> bool:
        return self.author_handle == self.account_handle


class CategorySpec(BaseModel):
    slug: str
    label: str
    description: str


class TaxonomyConfig(BaseModel):
    categories: list[CategorySpec]
    drop_categories: list[str] = Field(default_factory=list)


class ConversationCandidate(BaseModel):
    unit_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    standout_reply_ids: list[str] = Field(default_factory=list)
    standout_reply_threshold: float
    selected_by: list[str] = Field(default_factory=list)


class AssemblyResult(BaseModel):
    title: str
    summary: str
    include_tweet_ids: list[str]
    highlight_tweet_ids: list[str] = Field(default_factory=list)
    why_this_is_one_unit: str


class AssembledUnit(BaseModel):
    unit_id: str
    conversation_id: str
    account_handle: str
    title: str
    summary: str
    why_this_is_one_unit: str
    tweets: list[TimelineRecord]
    included_tweet_ids: list[str]
    highlight_tweet_ids: list[str]
    standout_reply_ids: list[str] = Field(default_factory=list)


class CategorizationResult(BaseModel):
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str


class CategorizedUnit(BaseModel):
    unit_id: str
    conversation_id: str
    account_handle: str
    title: str
    summary: str
    why_this_is_one_unit: str
    tweets: list[TimelineRecord]
    included_tweet_ids: list[str]
    highlight_tweet_ids: list[str]
    standout_reply_ids: list[str]
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str


class FilteredUnit(BaseModel):
    unit_id: str
    conversation_id: str
    account_handle: str
    title: str
    summary: str
    why_this_is_one_unit: str
    tweets: list[TimelineRecord]
    included_tweet_ids: list[str]
    highlight_tweet_ids: list[str]
    standout_reply_ids: list[str]
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str
    keep: bool
    filter_reason: str


class SignalResult(BaseModel):
    headline: str
    main_claim: str
    why_it_matters: str
    key_entities: list[str] = Field(default_factory=list)
    disagreement_present: bool
    disagreement_summary: str | None = None
    novelty_label: str
    signal_score: int = Field(ge=0, le=100)


class SignalUnit(BaseModel):
    unit_id: str
    conversation_id: str
    account_handle: str
    title: str
    summary: str
    category: str
    subcategory: str | None = None
    editorial_angle: str
    tweets: list[TimelineRecord]
    included_tweet_ids: list[str]
    highlight_tweet_ids: list[str]
    standout_reply_ids: list[str]
    headline: str
    main_claim: str
    why_it_matters: str
    key_entities: list[str]
    disagreement_present: bool
    disagreement_summary: str | None = None
    novelty_label: str
    signal_score: int
    virality_score: float
    engagement_totals: dict[str, int]
    heat_status: Literal["heated", "still_active", "cooling_off", "watch"]
    momentum: Literal["rising", "steady", "cooling"]
    source_urls: list[str]


class IssueCluster(BaseModel):
    title: str
    summary: str
    unit_ids: list[str]


class IssueClusterResult(BaseModel):
    issues: list[IssueCluster] = Field(default_factory=list)


class ThreadState(BaseModel):
    title: str
    heat_status: Literal["heated", "still_active", "cooling_off", "watch"]
    momentum: Literal["rising", "steady", "cooling"]
    virality_score: float
    disagreement_present: bool
    last_seen_at: datetime
    source_urls: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class DigestRunResult:
    run_id: str
    run_dir: Path
    digest_path: Path
    selected_count: int
    kept_count: int
    issue_count: int
    heated_count: int


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


def load_taxonomy(path: Path) -> TaxonomyConfig:
    if path.exists():
        return TaxonomyConfig.model_validate_json(path.read_text(encoding="utf-8"))
    return TaxonomyConfig.model_validate(DEFAULT_TAXONOMY_DOC)


def load_timeline_records(path: Path) -> list[TimelineRecord]:
    doc = load_timeline(path)
    raw_entries = doc.get("entries", [])
    if not isinstance(raw_entries, list):
        return []

    records: list[TimelineRecord] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        try:
            records.append(TimelineRecord.model_validate(item))
        except ValidationError:
            continue
    records.sort(key=lambda record: record.created_at, reverse=True)
    return records


def load_previous_threads(path: Path) -> tuple[dict[str, Any], dict[str, ThreadState], datetime | None]:
    state_doc = load_report_state(path)
    raw_threads = state_doc.get("threads", {})
    previous_threads: dict[str, ThreadState] = {}
    if isinstance(raw_threads, dict):
        for conversation_id, raw_value in raw_threads.items():
            if not isinstance(conversation_id, str) or not isinstance(raw_value, dict):
                continue
            try:
                previous_threads[conversation_id] = ThreadState.model_validate(raw_value)
            except ValidationError:
                continue

    last_run_at = None
    raw_last_run_at = state_doc.get("last_run_at")
    if isinstance(raw_last_run_at, str):
        try:
            last_run_at = datetime.fromisoformat(raw_last_run_at)
        except ValueError:
            last_run_at = None
    return state_doc, previous_threads, last_run_at


def resolve_fresh_cutoff(
    *,
    now: datetime,
    last_run_at: datetime | None,
    window_minutes: int,
) -> datetime:
    if last_run_at is not None and last_run_at <= now:
        return last_run_at
    return now - timedelta(minutes=max(1, window_minutes))


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    bounded = max(0.0, min(100.0, percentile_value))
    sorted_values = sorted(values)
    if bounded == 100.0:
        return sorted_values[-1]
    position = (len(sorted_values) - 1) * (bounded / 100.0)
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))
    lower_value = sorted_values[lower_index]
    upper_value = sorted_values[upper_index]
    if lower_index == upper_index:
        return lower_value
    weight = position - lower_index
    return lower_value + (upper_value - lower_value) * weight


def virality_score(record: TimelineRecord) -> float:
    return (
        (1.0 * math.log1p(record.favorite_count or 0))
        + (2.5 * math.log1p(record.retweet_count or 0))
        + (2.0 * math.log1p(record.reply_count or 0))
        + (2.8 * math.log1p(record.quote_count or 0))
        + (0.15 * math.log1p(record.view_count or 0))
    )


def aggregate_engagement(records: list[TimelineRecord]) -> dict[str, int]:
    return {
        "favorite_count": sum(record.favorite_count or 0 for record in records),
        "retweet_count": sum(record.retweet_count or 0 for record in records),
        "reply_count": sum(record.reply_count or 0 for record in records),
        "quote_count": sum(record.quote_count or 0 for record in records),
        "view_count": sum(record.view_count or 0 for record in records),
    }


def select_report_records(
    *,
    records: list[TimelineRecord],
    previous_threads: dict[str, ThreadState],
    fresh_cutoff: datetime,
) -> list[TimelineRecord]:
    tracked_conversations = {
        conversation_id
        for conversation_id, state in previous_threads.items()
        if state.heat_status in DEFAULT_KEEP_HEAT_STATUSES
    }
    selected = [
        record
        for record in records
        if record.created_at >= fresh_cutoff or record.conversation_key in tracked_conversations
    ]
    selected.sort(key=lambda record: record.created_at, reverse=True)
    return selected


def build_candidates(records: list[TimelineRecord]) -> list[ConversationCandidate]:
    grouped: dict[str, list[TimelineRecord]] = {}
    for record in records:
        grouped.setdefault(record.conversation_key, []).append(record)

    external_reply_scores = [
        virality_score(record)
        for record in records
        if record.kind == "reply" and not record.authored_by_source
    ]
    standout_threshold = percentile(external_reply_scores, DEFAULT_REPLY_PERCENTILE)

    candidates: list[ConversationCandidate] = []
    for conversation_id, group in grouped.items():
        sorted_group = sorted(group, key=lambda record: record.created_at)
        account_handle = sorted_group[0].account_handle
        included_ids = {
            record.tweet_id
            for record in sorted_group
            if record.authored_by_source
        }
        selection_reasons: set[str] = set()
        if included_ids:
            selection_reasons.add("source_authored")

        records_by_id = {record.tweet_id: record for record in sorted_group}
        for record in sorted_group:
            if not record.authored_by_source:
                continue
            if record.in_reply_to_tweet_id and record.in_reply_to_tweet_id in records_by_id:
                included_ids.add(record.in_reply_to_tweet_id)
                selection_reasons.add("author_reply_context")

        standout_replies = [
            record
            for record in sorted_group
            if record.kind == "reply"
            and not record.authored_by_source
            and virality_score(record) >= standout_threshold
        ]
        if not standout_replies:
            fallback_replies = [
                record
                for record in sorted_group
                if record.kind == "reply" and not record.authored_by_source
            ]
            fallback_replies.sort(key=virality_score, reverse=True)
            standout_replies = fallback_replies[:1]

        standout_replies = sorted(
            standout_replies,
            key=virality_score,
            reverse=True,
        )[:DEFAULT_MAX_STANDOUT_REPLIES]

        for reply in standout_replies:
            included_ids.add(reply.tweet_id)
        if standout_replies:
            selection_reasons.add("standout_replies")

        filtered_group = [
            record for record in sorted_group if record.tweet_id in included_ids
        ]
        if not filtered_group:
            filtered_group = sorted_group[:1]
            selection_reasons.add("fallback_single")

        candidates.append(
            ConversationCandidate(
                unit_id=conversation_id,
                conversation_id=conversation_id,
                account_handle=account_handle,
                tweets=filtered_group,
                standout_reply_ids=[reply.tweet_id for reply in standout_replies],
                standout_reply_threshold=standout_threshold,
                selected_by=sorted(selection_reasons),
            )
        )

    candidates.sort(
        key=lambda candidate: max(tweet.created_at for tweet in candidate.tweets),
        reverse=True,
    )
    return candidates


def filter_units(
    *,
    categorized_units: list[CategorizedUnit],
    taxonomy: TaxonomyConfig,
) -> list[FilteredUnit]:
    drop_categories = set(taxonomy.drop_categories or DEFAULT_DROP_CATEGORIES)
    filtered: list[FilteredUnit] = []
    for unit in categorized_units:
        keep = unit.category not in drop_categories
        filter_reason = (
            "kept_for_signal" if keep else f"dropped_due_to_category:{unit.category}"
        )
        filtered.append(
            FilteredUnit(
                **unit.model_dump(),
                keep=keep,
                filter_reason=filter_reason,
            )
        )
    return filtered


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
            issue_units = [by_unit_id[unit_id] for unit_id in issue.unit_ids if unit_id in by_unit_id]
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


def save_next_state(
    *,
    previous_doc: dict[str, Any],
    signals: list[SignalUnit],
    run_started_at: datetime,
    state_path: Path,
) -> None:
    next_threads = previous_doc.get("threads", {})
    if not isinstance(next_threads, dict):
        next_threads = {}

    for unit in signals:
        next_threads[unit.conversation_id] = ThreadState(
            title=unit.title,
            heat_status=unit.heat_status,
            momentum=unit.momentum,
            virality_score=unit.virality_score,
            disagreement_present=unit.disagreement_present,
            last_seen_at=run_started_at,
            source_urls=unit.source_urls,
        ).model_dump(mode="json")

    save_report_state(
        {
            "last_run_at": run_started_at.isoformat(),
            "threads": next_threads,
        },
        state_path,
    )


def _render_source_links(urls: list[str]) -> str:
    if not urls:
        return "No direct source link captured."
    return ", ".join(f"[source {index + 1}]({url})" for index, url in enumerate(urls))


def run_digest_report(
    *,
    timeline_file: Path,
    output_dir: Path = DEFAULT_REPORT_RUNS_PATH,
    state_file: Path,
    taxonomy_file: Path = DEFAULT_TAXONOMY_PATH,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
    model: str = DEFAULT_REPORT_MODEL,
    backend: Any | None = None,
) -> DigestRunResult:
    from .agents import OpenAIDigestBackend, assemble_units, categorize_units, cluster_issues, extract_signals

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
