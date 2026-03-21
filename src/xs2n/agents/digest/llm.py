from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
from typing import Any, TypeVar, cast

from openai import BadRequestError, OpenAI
from pydantic import BaseModel

from xs2n.schemas.digest import LLMCallTrace

from .credentials import resolve_digest_credentials
from .helpers import to_jsonable
from .pipeline import DEFAULT_REPORT_MODEL


SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _schema_format_name(schema: type[BaseModel]) -> str:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", schema.__name__).lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", snake).strip("_")
    return normalized or "response_schema"


def _extract_text_from_response(response: Any) -> str | None:
    output = getattr(response, "output", None)
    if not isinstance(output, list):
        return None

    for item in output:
        content = getattr(item, "content", None)
        if not isinstance(content, list):
            continue
        for part in content:
            text = getattr(part, "text", None)
            if isinstance(text, str) and text.strip():
                return text
    return None


def _strict_json_schema(fragment: Any) -> Any:
    if isinstance(fragment, list):
        return [_strict_json_schema(item) for item in fragment]
    if not isinstance(fragment, dict):
        return fragment

    normalized = {key: _strict_json_schema(value) for key, value in fragment.items()}
    if normalized.get("type") == "object":
        normalized.setdefault("additionalProperties", False)
        properties = normalized.get("properties")
        if isinstance(properties, dict):
            normalized["required"] = list(properties.keys())
    return normalized


class DigestLLM:
    def __init__(
        self,
        *,
        model: str = DEFAULT_REPORT_MODEL,
        api_key: str | None = None,
    ) -> None:
        credentials = resolve_digest_credentials(api_key)
        self._model = model
        self._source = credentials.source
        self._client_options = {
            "api_key": credentials.token,
            "base_url": credentials.base_url,
        }
        self._thread_local = threading.local()
        self._trace_dir: Path | None = None
        self._call_index = 0
        self._trace_lock = threading.Lock()

    @property
    def source(self) -> str:
        return self._source

    def configure_run_logging(self, *, run_dir: Path) -> None:
        self._trace_dir = run_dir / "llm_calls"
        self._trace_dir.mkdir(parents=True, exist_ok=True)
        with self._trace_lock:
            self._call_index = 0

    def _get_client(self) -> OpenAI:
        client = getattr(self._thread_local, "client", None)
        if client is None:
            client = OpenAI(**self._client_options)
            self._thread_local.client = client
        return cast(OpenAI, client)

    def _next_call_id(self) -> int:
        with self._trace_lock:
            self._call_index += 1
            return self._call_index

    def _write_call_trace(
        self,
        *,
        prompt: str,
        payload: Any,
        schema: type[BaseModel],
        phase_name: str,
        item_id: str | None,
        started_at: datetime,
        finished_at: datetime,
        output_text: str | None,
        result: BaseModel | None,
        image_urls: list[str],
        response_id: str | None,
        request_id: str | None,
        usage: Any,
        error: RuntimeError | None,
    ) -> None:
        if self._trace_dir is None:
            return

        call_id = self._next_call_id()
        trace = LLMCallTrace(
            call_id=call_id,
            phase=phase_name,
            item_id=item_id,
            schema_name=schema.__name__,
            model=self._model,
            credential_source=self._source,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=max(
                int((finished_at - started_at).total_seconds() * 1000),
                0,
            ),
            prompt=prompt,
            payload=to_jsonable(payload),
            image_urls=image_urls,
            output_text=output_text,
            result=to_jsonable(result),
            response_id=response_id,
            request_id=request_id,
            usage=to_jsonable(usage),
            error_type=type(error).__name__ if error is not None else None,
            error_message=str(error) if error is not None else None,
        )
        item_suffix = re.sub(
            r"[^a-zA-Z0-9_.-]+",
            "_",
            trace.item_id or f"call_{call_id:03d}",
        ).strip("_")
        filename = f"{call_id:03d}_{trace.phase}_{item_suffix}.json"
        self._trace_dir.joinpath(filename).write_text(
            f"{trace.model_dump_json(indent=2)}\n",
            encoding="utf-8",
        )

    def run(
        self,
        *,
        prompt: str,
        payload: Any,
        schema: type[SchemaT],
        image_urls: list[str] | None = None,
        phase_name: str = "llm",
        item_id: str | None = None,
    ) -> SchemaT:
        started_at = datetime.now(timezone.utc)
        payload_json = json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2)
        resolved_image_urls = image_urls or []
        schema_json = _strict_json_schema(schema.model_json_schema())
        output_text: str | None = None
        response_id: str | None = None
        request_id: str | None = None
        usage: Any = None
        final_response: Any = None
        parsed_result: SchemaT | None = None
        runtime_error: RuntimeError | None = None

        try:
            input_content = [
                {
                    "type": "input_text",
                    "text": f"Input JSON:\n{payload_json}",
                }
            ]
            input_content.extend(
                {
                    "type": "input_image",
                    "image_url": {"url": image_url},
                }
                for image_url in resolved_image_urls
            )
            with self._get_client().responses.stream(
                model=self._model,
                store=False,
                instructions=prompt,
                input=[
                    {
                        "role": "user",
                        "content": input_content,
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": _schema_format_name(schema),
                        "schema": schema_json,
                        "strict": True,
                    }
                },
            ) as stream:
                for event in stream:
                    if event.type == "response.output_text.done":
                        output_text = event.text
                final_response = stream.get_final_response()
                response_id = getattr(final_response, "id", None)
                request_id = getattr(final_response, "_request_id", None)
                usage = getattr(final_response, "usage", None)
        except BadRequestError as error:
            message = str(error)
            if (
                self._source.startswith("codex_auth")
                and "not supported when using Codex with a ChatGPT account" in message
            ):
                runtime_error = RuntimeError(
                    f"Model `{self._model}` is not supported via Codex auth. "
                    "Use a Codex-supported GPT-5 model such as `gpt-5.4-mini`, "
                    "or export OPENAI_API_KEY for standard OpenAI API models."
                )
            else:
                runtime_error = RuntimeError(
                    f"Digest model request failed: {message}"
                )
        except Exception as error:
            runtime_error = RuntimeError(f"Digest model request failed: {error}")

        if runtime_error is None:
            resolved_text = output_text or _extract_text_from_response(final_response)
            if not resolved_text:
                runtime_error = RuntimeError(
                    "Digest model returned no structured output text."
                )
            else:
                output_text = resolved_text
                try:
                    parsed_result = cast(SchemaT, schema.model_validate_json(resolved_text))
                except Exception as error:
                    runtime_error = RuntimeError(
                        "Digest model returned invalid structured output: "
                        f"{error}. Raw output: {resolved_text}"
                    )

        finished_at = datetime.now(timezone.utc)
        self._write_call_trace(
            prompt=prompt,
            payload=payload,
            schema=schema,
            phase_name=phase_name,
            item_id=item_id,
            started_at=started_at,
            finished_at=finished_at,
            output_text=output_text,
            result=parsed_result,
            image_urls=resolved_image_urls,
            response_id=response_id,
            request_id=request_id,
            usage=usage,
            error=runtime_error,
        )

        if runtime_error is not None:
            raise runtime_error
        return cast(SchemaT, parsed_result)
