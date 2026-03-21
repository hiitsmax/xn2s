from __future__ import annotations

import json
import re
from typing import Any, TypeVar, cast

from openai import BadRequestError, OpenAI
from pydantic import BaseModel

from .credentials import resolve_model_credentials


SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _schema_format_name(schema: type[BaseModel]) -> str:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", schema.__name__).lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", snake).strip("_")
    return normalized or "response_schema"


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
        model: str,
        api_key: str | None = None,
    ) -> None:
        credentials = resolve_model_credentials(api_key)
        self._model = model
        self._source = credentials.source
        self._client = OpenAI(
            api_key=credentials.token,
            base_url=credentials.base_url,
        )

    @property
    def source(self) -> str:
        return self._source

    def run(
        self,
        *,
        prompt: str,
        payload: Any,
        schema: type[SchemaT],
    ) -> SchemaT:
        payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
        try:
            response = self._client.responses.create(
                model=self._model,
                input=[
                    {
                        "role": "system",
                        "content": prompt,
                    },
                    {
                        "role": "user",
                        "content": f"Input JSON:\n{payload_json}",
                    },
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": _schema_format_name(schema),
                        "schema": _strict_json_schema(schema.model_json_schema()),
                        "strict": True,
                    }
                },
            )
        except BadRequestError as error:
            message = str(error)
            if (
                self._source.startswith("codex_auth")
                and "not supported when using Codex with a ChatGPT account" in message
            ):
                raise RuntimeError(
                    f"Model `{self._model}` is not supported via Codex auth. "
                    "Use a Codex-supported GPT-5 model such as `gpt-5.4-mini`, "
                    "or export OPENAI_API_KEY for standard OpenAI API models."
                ) from error
            raise RuntimeError(f"Digest model request failed: {message}") from error
        except Exception as error:
            raise RuntimeError(f"Digest model request failed: {error}") from error

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise RuntimeError("Digest model returned no structured output text.")

        try:
            return cast(SchemaT, schema.model_validate_json(output_text))
        except Exception as error:
            raise RuntimeError(
                "Digest model returned invalid structured output: "
                f"{error}. Raw output: {output_text}"
            ) from error
