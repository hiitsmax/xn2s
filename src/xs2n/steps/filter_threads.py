from __future__ import annotations

from typing import Any

from xs2n.schemas import FilteredThread, ThreadFilterResult, ThreadInput


FILTER_THREADS_PROMPT = (
    "You review one X/Twitter thread for a low-noise issue digest. "
    "Drop only items that are obviously shallow, spammy, repetitive, or clearly "
    "not worth a serious reader's attention. Default to keeping borderline but real signal."
)


def run(
    *,
    llm: Any,
    threads: list[ThreadInput],
) -> list[FilteredThread]:
    filtered_threads: list[FilteredThread] = []
    for thread in threads:
        result = llm.run(
            prompt=FILTER_THREADS_PROMPT,
            payload={"thread": thread.model_dump(mode="json")},
            schema=ThreadFilterResult,
        )
        filtered_threads.append(
            FilteredThread(
                thread_id=thread.thread_id,
                account_handle=thread.account_handle,
                posts=thread.posts,
                keep=result.keep,
                filter_reason=result.filter_reason,
            )
        )
    return filtered_threads
