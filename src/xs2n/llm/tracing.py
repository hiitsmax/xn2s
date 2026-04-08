from __future__ import annotations

import os
from typing import Any, Callable


DEFAULT_PHOENIX_COLLECTOR_ENDPOINT = "http://127.0.0.1:6006/v1/traces"
DEFAULT_PHOENIX_PROJECT_NAME = "xs2n"
_TRACING_CONFIGURED = False


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def configure_phoenix_tracing(
    *,
    register_phoenix: Callable[..., Any] | None = None,
) -> bool:
    global _TRACING_CONFIGURED

    if _TRACING_CONFIGURED:
        return True

    if _is_truthy(os.getenv("XS2N_DISABLE_TRACING")):
        return False

    os.environ.setdefault(
        "PHOENIX_COLLECTOR_ENDPOINT",
        DEFAULT_PHOENIX_COLLECTOR_ENDPOINT,
    )

    if register_phoenix is None:
        try:
            from phoenix.otel import register as register_phoenix
        except ModuleNotFoundError as error:  # pragma: no cover
            raise RuntimeError(
                "Phoenix tracing dependencies are missing. Run `uv sync --extra dev` "
                "to install the repo dependencies, including Arize Phoenix instrumentation."
            ) from error

    register_phoenix(
        endpoint=DEFAULT_PHOENIX_COLLECTOR_ENDPOINT,
        project_name=os.getenv("PHOENIX_PROJECT_NAME") or DEFAULT_PHOENIX_PROJECT_NAME,
        protocol="http/protobuf",
        verbose=False,
        auto_instrument=True,
    )
    _TRACING_CONFIGURED = True
    return True
