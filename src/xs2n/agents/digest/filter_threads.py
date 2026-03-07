from __future__ import annotations

from typing import Any

from .pipeline import (
    CategorizedThread,
    FilteredThread,
    FilterResult,
    TaxonomyConfig,
)


def run(
    *,
    agent: Any,
    taxonomy: TaxonomyConfig,
    threads: list[CategorizedThread],
) -> list[FilteredThread]:
    filtered_threads: list[FilteredThread] = []
    for thread in threads:
        result = agent.run(
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
        filtered_threads.append(
            FilteredThread(
                **thread.model_dump(),
                keep=result.keep,
                filter_reason=result.filter_reason,
            )
        )
    return filtered_threads
