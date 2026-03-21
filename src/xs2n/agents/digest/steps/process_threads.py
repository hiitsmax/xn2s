from __future__ import annotations

from typing import Any


def run(
    *,
    llm: Any,
    threads: list[Any],
    parallel_workers: int,
) -> list[Any]:
    """Compatibility shim for a retired digest step.

    The active runtime no longer performs per-thread processing after filtering.
    """

    raise RuntimeError(
        "process_threads.run is retired and no longer part of the active "
        "digest pipeline."
    )
