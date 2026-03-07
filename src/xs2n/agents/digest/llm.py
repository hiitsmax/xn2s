from __future__ import annotations

import json
import os
from typing import Any, TypeVar, cast

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from .pipeline import DEFAULT_REPORT_MODEL, to_jsonable


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class DigestLLM:
    def __init__(
        self,
        *,
        model: str = DEFAULT_REPORT_MODEL,
        api_key: str | None = None,
    ) -> None:
        resolved_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required for `xs2n report digest`. "
                "Export the key and retry."
            )
        self._model = ChatOpenAI(model=model, temperature=0, api_key=resolved_key)

    def run(
        self,
        *,
        prompt: str,
        payload: Any,
        schema: type[SchemaT],
    ) -> SchemaT:
        structured_model = self._model.with_structured_output(schema, method="json_schema")
        response = structured_model.invoke(
            f"{prompt}\n\nInput JSON:\n{json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2)}"
        )
        return cast(SchemaT, response)
