from __future__ import annotations

from typing import Any

from xs2n.schemas.digest import FilteredThread, ProcessedThread, ThreadProcessResult

from ..helpers import virality_score


def run(
    *,
    llm: Any,
    threads: list[FilteredThread],
) -> list[ProcessedThread]:
    processed_threads: list[ProcessedThread] = []
    for thread in threads:
        if not thread.keep:
            continue
        result = llm.run(
            prompt=(
                "You process one kept X/Twitter thread for a compact magazine-style digest. "
                "Return the raw thread-level output: the headline, main claim, why it matters, "
                "key entities, and whether the thread shows real disagreement."
            ),
            payload=thread,
            schema=ThreadProcessResult,
        )
        processed_threads.append(
            ProcessedThread(
                **thread.model_dump(),
                headline=result.headline,
                main_claim=result.main_claim,
                why_it_matters=result.why_it_matters,
                key_entities=result.key_entities,
                disagreement_present=result.disagreement_present,
                disagreement_summary=result.disagreement_summary,
                novelty_label=result.novelty_label,
                signal_score=result.signal_score,
                virality_score=sum(virality_score(tweet) for tweet in thread.tweets),
                source_urls=thread.source_urls,
            )
        )

    processed_threads.sort(
        key=lambda thread: (thread.signal_score, thread.virality_score),
        reverse=True,
    )
    return processed_threads
