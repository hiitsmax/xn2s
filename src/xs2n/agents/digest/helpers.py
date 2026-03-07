from __future__ import annotations

import json
import math
from pathlib import Path
import re
from typing import Any

from pydantic import BaseModel

from xs2n.schemas.digest import TaxonomyConfig, TimelineRecord


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


def render_source_links(urls: list[str]) -> str:
    if not urls:
        return "No direct source link captured."
    return ", ".join(f"[source {index + 1}]({url})" for index, url in enumerate(urls))
