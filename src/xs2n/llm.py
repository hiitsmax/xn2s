import json
from typing import Any, TypeVar, cast

from agents import Agent, OpenAIResponsesModel, RunConfig, Runner
from openai import AsyncOpenAI, BadRequestError
from pydantic import BaseModel

from .credentials import resolve_model_credentials


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLM:
    def __init__(self, *, model: str, api_key: str | None = None) -> None:
        credentials = resolve_model_credentials(api_key)
        self._model = model
        self._source = credentials.source
        self._client = AsyncOpenAI(
            api_key=credentials.token,
            base_url=credentials.base_url,
        )
        self._agent_model = OpenAIResponsesModel(
            model=self._model,
            openai_client=self._client,
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
        agent = Agent(
            name="digest_llm",
            instructions=prompt,
            model=self._agent_model,
            output_type=schema,
        )
        try:
            result = Runner.run_sync(
                agent,
                input=f"Input JSON:\n{payload_json}",
                run_config=RunConfig(tracing_disabled=True),
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

        output = getattr(result, "final_output", None)
        if output is None:
            raise RuntimeError("Digest model returned no structured output.")

        try:
            if isinstance(output, schema):
                return cast(SchemaT, output)
            return cast(SchemaT, schema.model_validate(output))
        except Exception as error:
            raise RuntimeError(
                "Digest model returned invalid structured output: "
                f"{error}. Raw output: {output}"
            ) from error
