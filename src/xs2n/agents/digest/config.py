from __future__ import annotations

from pathlib import Path


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
