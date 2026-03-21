from __future__ import annotations

from typing import Any


def run(
    *,
    llm: Any,
    taxonomy: Any,
    threads: list[Any],
    parallel_workers: int,
) -> list[Any]:
    """Compatibility shim for a retired digest step.

    The active runtime now starts at thread loading, filtering, issue grouping,
    and HTML rendering. Categorization is no longer part of the live pipeline.
    """

    raise RuntimeError(
        "categorize_threads.run is retired and no longer part of the "
        "active digest pipeline."
    )
