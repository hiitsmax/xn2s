from __future__ import annotations

from typing import Any

from xs2n.models.digest import FilteredThread, SignalResult, SignalThread

from .pipeline import virality_score


def run(
    *,
    llm: Any,
    threads: list[FilteredThread],
) -> list[SignalThread]:
    signal_threads: list[SignalThread] = []
    for thread in threads:
        if not thread.keep:
            continue
        result = llm.run(
            prompt=(
                "You extract the signal from one kept X/Twitter thread for a compact "
                "magazine-style digest. Be concrete and brief. Name the claim, why it "
                "matters, any key entities, and whether the thread shows real disagreement."
            ),
            payload=thread,
            schema=SignalResult,
        )
        signal_threads.append(
            SignalThread(
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

    signal_threads.sort(
        key=lambda thread: (thread.signal_score, thread.virality_score),
        reverse=True,
    )
    return signal_threads
