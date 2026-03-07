from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DEFAULT_REPORT_RUNS_PATH = Path("data/report_runs")
DEFAULT_TAXONOMY_PATH = Path("docs/codex/report_taxonomy.json")
DEFAULT_REPORT_MODEL = "gpt-4.1-mini"
DEFAULT_MAX_ISSUES = 6
DEFAULT_MAX_STANDOUT_THREADS = 6

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


class ThreadInput(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str] = Field(default_factory=list)
    context_tweet_ids: list[str] = Field(default_factory=list)
    latest_created_at: datetime

    @property
    def source_urls(self) -> list[str]:
        urls = [
            tweet.source_url
            for tweet in self.tweets
            if tweet.tweet_id in self.source_tweet_ids
        ]
        if urls:
            return urls[:3]
        if self.tweets:
            return [self.tweets[0].source_url]
        return []


class CategorizationResult(BaseModel):
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str


class CategorizedThread(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str]
    context_tweet_ids: list[str]
    latest_created_at: datetime
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str

    @property
    def source_urls(self) -> list[str]:
        return ThreadInput(**self.model_dump()).source_urls


class FilterResult(BaseModel):
    keep: bool
    filter_reason: str


class FilteredThread(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str]
    context_tweet_ids: list[str]
    latest_created_at: datetime
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str
    keep: bool
    filter_reason: str

    @property
    def source_urls(self) -> list[str]:
        return ThreadInput(**self.model_dump()).source_urls


class SignalResult(BaseModel):
    headline: str
    main_claim: str
    why_it_matters: str
    key_entities: list[str] = Field(default_factory=list)
    disagreement_present: bool
    disagreement_summary: str | None = None
    novelty_label: str
    signal_score: int = Field(ge=0, le=100)


class SignalThread(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str]
    context_tweet_ids: list[str]
    latest_created_at: datetime
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str
    keep: bool
    filter_reason: str
    headline: str
    main_claim: str
    why_it_matters: str
    key_entities: list[str]
    disagreement_present: bool
    disagreement_summary: str | None = None
    novelty_label: str
    signal_score: int
    virality_score: float
    source_urls: list[str] = Field(default_factory=list)


class IssueAssignmentResult(BaseModel):
    issue_slug: str
    issue_title: str
    issue_summary: str
    why_this_thread_belongs: str


class IssueThread(BaseModel):
    thread_id: str
    conversation_id: str
    account_handle: str
    tweets: list[TimelineRecord]
    source_tweet_ids: list[str]
    context_tweet_ids: list[str]
    latest_created_at: datetime
    category: str
    subcategory: str | None = None
    editorial_angle: str
    reasoning: str
    keep: bool
    filter_reason: str
    headline: str
    main_claim: str
    why_it_matters: str
    key_entities: list[str]
    disagreement_present: bool
    disagreement_summary: str | None = None
    novelty_label: str
    signal_score: int
    virality_score: float
    source_urls: list[str] = Field(default_factory=list)
    issue_slug: str
    issue_title: str
    issue_summary: str
    why_this_thread_belongs: str


class Issue(BaseModel):
    slug: str
    title: str
    summary: str
    thread_ids: list[str] = Field(default_factory=list)


@dataclass(slots=True)
class DigestRunResult:
    run_id: str
    run_dir: Path
    digest_path: Path
    thread_count: int
    kept_count: int
    issue_count: int


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


def virality_score(record: TimelineRecord) -> float:
    return (
        (1.0 * math.log1p(record.favorite_count or 0))
        + (2.5 * math.log1p(record.retweet_count or 0))
        + (2.0 * math.log1p(record.reply_count or 0))
        + (2.8 * math.log1p(record.quote_count or 0))
        + (0.15 * math.log1p(record.view_count or 0))
    )


def slugify_issue(value: str, *, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or fallback


def render_digest(
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
                lines.append(f"  Sources: {_render_source_links(thread.source_urls)}")
            lines.append("")

    lines.extend(["## Standout Threads", ""])
    if not standout_threads:
        lines.extend(
            [
                "No standalone thread signals were kept in this run.",
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
            lines.append(f"- Sources: {_render_source_links(thread.source_urls)}")
            lines.append("")

    return "\n".join(lines).strip() + "\n"
def _render_source_links(urls: list[str]) -> str:
    if not urls:
        return "No direct source link captured."
    return ", ".join(f"[source {index + 1}]({url})" for index, url in enumerate(urls))


def run_digest_report(
    *,
    timeline_file: Path,
    output_dir: Path = DEFAULT_REPORT_RUNS_PATH,
    taxonomy_file: Path = DEFAULT_TAXONOMY_PATH,
    model: str = DEFAULT_REPORT_MODEL,
    llm: Any | None = None,
) -> DigestRunResult:
    from .categorize_threads import run as categorize_threads
    from .extract_signals import run as extract_signals
    from .filter_threads import run as filter_threads
    from .group_issues import run as group_issues
    from .llm import DigestLLM
    from .load_threads import run as load_threads

    digest_llm = llm or DigestLLM(model=model)
    run_started_at = datetime.now(timezone.utc)
    run_id = run_started_at.strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    taxonomy = load_taxonomy(taxonomy_file)
    threads = load_threads(timeline_file=timeline_file)
    write_json(run_dir / "threads.json", threads)

    categorized_threads = categorize_threads(
        llm=digest_llm,
        taxonomy=taxonomy,
        threads=threads,
    )
    write_json(run_dir / "categorized_threads.json", categorized_threads)

    filtered_threads = filter_threads(
        llm=digest_llm,
        taxonomy=taxonomy,
        threads=categorized_threads,
    )
    write_json(run_dir / "filtered_threads.json", filtered_threads)

    signal_threads = extract_signals(
        llm=digest_llm,
        threads=filtered_threads,
    )
    write_json(run_dir / "signals.json", signal_threads)

    issue_threads, issues = group_issues(
        llm=digest_llm,
        threads=signal_threads,
    )
    write_json(run_dir / "issue_assignments.json", issue_threads)
    write_json(run_dir / "issues.json", issues)

    digest_markdown = render_digest(
        run_id=run_id,
        taxonomy=taxonomy,
        issue_threads=issue_threads,
        issues=issues,
    )
    digest_path = run_dir / "digest.md"
    digest_path.write_text(digest_markdown, encoding="utf-8")

    summary = {
        "run_id": run_id,
        "timeline_file": str(timeline_file),
        "taxonomy_file": str(taxonomy_file),
        "model": model,
        "thread_count": len(threads),
        "kept_count": len(signal_threads),
        "issue_count": len(issues),
        "digest_path": str(digest_path),
    }
    write_json(run_dir / "run.json", summary)

    return DigestRunResult(
        run_id=run_id,
        run_dir=run_dir,
        digest_path=digest_path,
        thread_count=len(threads),
        kept_count=len(signal_threads),
        issue_count=len(issues),
    )
