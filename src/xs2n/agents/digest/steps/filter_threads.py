from __future__ import annotations

from typing import Any

from xs2n.schemas.digest import FilteredThread, ThreadFilterResult, ThreadInput


def run(
    *,
    llm: Any,
    threads: list[ThreadInput],
) -> list[FilteredThread]:
    filtered_threads: list[FilteredThread] = []
    for thread in threads:
        result = llm.run(
            prompt=(
                "You review one X/Twitter thread for a low-noise issue digest. "
                "Drop only items that are obviously stupid, shallow, spammy, repetitive, "
                "or clearly not worth a serious reader's attention. "
                "Default to keeping borderline but real signal."
            ),
            payload={"thread": thread},
            schema=ThreadFilterResult,
            image_urls=thread.primary_tweet_media_urls,
        )
        filtered_threads.append(
            FilteredThread(
                **thread.model_dump(),
                keep=result.keep,
                filter_reason=result.filter_reason,
            )
        )
    return filtered_threads
