from __future__ import annotations

from typing import Any

from xs2n.schemas.digest import (
    CategorizationResult,
    CategorizedThread,
    TaxonomyConfig,
    ThreadInput,
)

from ..helpers import map_in_thread_pool


def run(
    *,
    llm: Any,
    taxonomy: TaxonomyConfig,
    threads: list[ThreadInput],
    parallel_workers: int,
) -> list[CategorizedThread]:
    allowed_categories = {category.slug for category in taxonomy.categories}
    fallback_category = taxonomy.categories[0].slug if taxonomy.categories else "analysis"
    taxonomy_payload = [
        {
            "slug": category.slug,
            "label": category.label,
            "description": category.description,
        }
        for category in taxonomy.categories
    ]

    def categorize_thread(thread: ThreadInput) -> CategorizedThread:
        result = llm.run(
            prompt=(
                "You are categorizing one X/Twitter thread for a high-signal digest. "
                "Pick exactly one category slug from the provided taxonomy. Prefer the "
                "most informative category over the safest category."
            ),
            payload={
                "taxonomy": taxonomy_payload,
                "thread": thread,
            },
            schema=CategorizationResult,
        )
        category = result.category if result.category in allowed_categories else fallback_category
        return CategorizedThread(
            **thread.model_dump(),
            category=category,
            subcategory=result.subcategory,
            editorial_angle=result.editorial_angle,
            reasoning=result.reasoning,
        )

    return map_in_thread_pool(
        items=threads,
        worker=categorize_thread,
        max_workers=parallel_workers,
    )
