from __future__ import annotations

from typing import Any


def run(
    *,
    run_id: str,
    taxonomy: Any,
    issue_threads: list[Any],
    issues: list[Any],
) -> str:
    """Compatibility shim for the retired markdown digest renderer."""

    raise RuntimeError(
        "render_digest.run is retired; the active pipeline renders HTML via "
        "render_digest_html.run."
    )
