from __future__ import annotations

import json
import re
from typing import Any, TypeVar, cast

from openai import BadRequestError, OpenAI
from pydantic import BaseModel

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
        self._client = OpenAI(
            api_key=credentials.token,
            base_url=credentials.base_url,
        )

    def run(
        self,
        *,
        prompt: str,
        payload: Any,
        schema: type[SchemaT],
    ) -> SchemaT:
        payload_json = json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2)
        schema_json = _strict_json_schema(schema.model_json_schema())
        output_text: str | None = None

        try:
            with self._client.responses.stream(
                model=self._model,
                store=False,
                instructions=prompt,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": f"Input JSON:\n{payload_json}",
                            }
                        ],
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
        except BadRequestError as error:
            message = str(error)
            if (
                self._source.startswith("codex_auth")
                and "not supported when using Codex with a ChatGPT account" in message
            ):
                raise RuntimeError(
                    f"Model `{self._model}` is not supported via Codex auth. "
                    "Use a Codex-supported GPT-5 model such as `gpt-5.4`, "
                    "or export OPENAI_API_KEY for standard OpenAI API models."
                ) from error
            raise RuntimeError(f"Digest model request failed: {message}") from error
        except Exception as error:
            raise RuntimeError(f"Digest model request failed: {error}") from error

        resolved_text = output_text or _extract_text_from_response(final_response)
        if not resolved_text:
            raise RuntimeError("Digest model returned no structured output text.")

        try:
            return cast(SchemaT, schema.model_validate_json(resolved_text))
        except Exception as error:
            raise RuntimeError(
                "Digest model returned invalid structured output: "
                f"{error}. Raw output: {resolved_text}"
            ) from error
