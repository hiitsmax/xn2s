from __future__ import annotations

from typing import Any, AsyncIterator, Iterator, Literal

import openai
from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models.chat_models import generate_from_stream
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.runnables.config import run_in_executor
from langchain_openai import ChatOpenAI
from pydantic import Field, model_validator

from .auth import CODEX_OAUTH_AUTH_MODE, resolve_codex_oauth_credentials
from .responses import (
    build_codex_responses_payload,
    construct_chat_result_from_response,
    convert_responses_event_to_chunk,
    extract_completed_response,
)


class ChatOpenAICodexOAuth(ChatOpenAI):
    """`ChatOpenAI` facade that routes requests through Codex OAuth credentials."""

    auth_mode: Literal["codex_oauth"] = Field(default=CODEX_OAUTH_AUTH_MODE)

    @model_validator(mode="after")
    def validate_environment(self):  # type: ignore[override]
        if self.auth_mode != CODEX_OAUTH_AUTH_MODE:
            raise ValueError(
                f"`auth_mode` must be `{CODEX_OAUTH_AUTH_MODE}` for this facade."
            )
        credentials = resolve_codex_oauth_credentials()
        client_params: dict[str, Any] = {
            "api_key": credentials.token,
            "base_url": credentials.base_url,
            "timeout": self.request_timeout,
            "default_headers": self.default_headers,
            "default_query": self.default_query,
        }
        if self.max_retries is not None:
            client_params["max_retries"] = self.max_retries

        self.root_client = openai.OpenAI(**client_params)
        self.root_async_client = openai.AsyncOpenAI(**client_params)
        self.client = self.root_client.responses
        self.async_client = self.root_async_client.responses
        return self

    def _build_codex_responses_payload(
        self,
        messages: list[BaseMessage],
        *,
        stop: list[str] | None = None,
        stream: bool | None = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        request_kwargs = dict(kwargs)
        if stop is not None:
            request_kwargs["stop"] = stop
        if stream is not None:
            request_kwargs["stream"] = stream
        return build_codex_responses_payload(
            model=self.model_name,
            messages=messages,
            default_params=self._default_params,
            kwargs=request_kwargs,
        )

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        payload = self._build_codex_responses_payload(
            messages,
            stop=stop,
            stream=True,
            **kwargs,
        )
        with self.root_client.responses.create(**payload) as stream:
            for event in stream:
                chunk = convert_responses_event_to_chunk(event=event)
                if chunk is None:
                    continue
                if run_manager:
                    run_manager.on_llm_new_token(chunk.text, chunk=chunk)
                yield chunk

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._build_codex_responses_payload(
            messages,
            stop=stop,
            stream=True,
            **kwargs,
        )
        completed_response = None
        with self.root_client.responses.create(**payload) as stream:
            for event in stream:
                chunk = convert_responses_event_to_chunk(event=event)
                if chunk is not None and run_manager:
                    run_manager.on_llm_new_token(chunk.text, chunk=chunk)
                completed_response = extract_completed_response(event) or completed_response

        if completed_response is None:
            return generate_from_stream(iter(()))
        return construct_chat_result_from_response(
            response=completed_response,
            provider_name="openai-codex",
            schema=kwargs.get("response_format"),
        )

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        payload = self._build_codex_responses_payload(
            messages,
            stop=stop,
            stream=True,
            **kwargs,
        )
        context_manager = await self.root_async_client.responses.create(**payload)
        async with context_manager as stream:
            async for event in stream:
                chunk = convert_responses_event_to_chunk(event=event)
                if chunk is None:
                    continue
                if run_manager:
                    await run_manager.on_llm_new_token(chunk.text, chunk=chunk)
                yield chunk

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._build_codex_responses_payload(
            messages,
            stop=stop,
            stream=True,
            **kwargs,
        )
        completed_response = None
        context_manager = await self.root_async_client.responses.create(**payload)
        async with context_manager as stream:
            async for event in stream:
                chunk = convert_responses_event_to_chunk(event=event)
                if chunk is not None and run_manager:
                    await run_manager.on_llm_new_token(chunk.text, chunk=chunk)
                completed_response = extract_completed_response(event) or completed_response

        if completed_response is None:
            raise RuntimeError("Codex OAuth stream ended without a completed response.")
        return await run_in_executor(
            None,
            construct_chat_result_from_response,
            response=completed_response,
            provider_name="openai-codex",
            schema=kwargs.get("response_format"),
        )
