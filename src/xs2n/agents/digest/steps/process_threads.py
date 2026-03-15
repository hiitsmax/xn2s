from __future__ import annotations

from typing import Any

from xs2n.schemas.digest import FilteredThread, ProcessedThread, ThreadProcessResult

from ..helpers import map_in_thread_pool, virality_score


def run(
    *,
    llm: Any,
    threads: list[FilteredThread],
    parallel_workers: int,
) -> list[ProcessedThread]:
    kept_threads = [thread for thread in threads if thread.keep]

    def process_thread(thread: FilteredThread) -> ProcessedThread:
        result = llm.run(
            prompt=(
                "You process one kept X/Twitter thread for a compact magazine-style digest. "
                "Return the raw thread-level output: the headline, main claim, why it matters, "
                "key entities, and whether the thread shows real disagreement."
            ),
            payload=thread,
            schema=ThreadProcessResult,
        )
        return ProcessedThread(
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

    processed_threads = map_in_thread_pool(
        items=kept_threads,
        worker=process_thread,
        max_workers=parallel_workers,
    )

    processed_threads.sort(
        key=lambda thread: (thread.signal_score, thread.virality_score),
        reverse=True,
    )
    return processed_threads
