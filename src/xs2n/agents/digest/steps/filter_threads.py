from __future__ import annotations

from typing import Any

from xs2n.schemas.digest import (
    CategorizedThread,
    FilteredThread,
    FilterResult,
    TaxonomyConfig,
)

from ..helpers import map_in_thread_pool


def run(
    *,
    llm: Any,
    taxonomy: TaxonomyConfig,
    threads: list[CategorizedThread],
    parallel_workers: int,
) -> list[FilteredThread]:
    def filter_thread(thread: CategorizedThread) -> FilteredThread:
        result = llm.run(
            prompt=(
                "You decide whether one categorized X/Twitter thread belongs in a "
                "high-signal, low-noise digest. Default to keeping real signal. Default "
                "to dropping shallow promo, personal chatter, or obvious AI slop. Use the "
                "provided drop categories as a strong prior, but keep exceptional cases "
                "when the thread still adds real public signal."
            ),
            payload={
                "drop_categories": taxonomy.drop_categories,
                "thread": thread,
            },
            schema=FilterResult,
        )
        return FilteredThread(
            **thread.model_dump(),
            keep=result.keep,
            filter_reason=result.filter_reason,
        )

    return map_in_thread_pool(
        items=threads,
        worker=filter_thread,
        max_workers=parallel_workers,
    )
