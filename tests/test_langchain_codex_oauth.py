from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from xs2n.langchain_codex_oauth import (
    ChatOpenAICodexOAuth,
    CodexOAuthCredentials,
    CodexOAuthLoginRequiredError,
    resolve_codex_oauth_credentials,
)
import xs2n.langchain_codex_oauth.auth as auth_module
import xs2n.langchain_codex_oauth.chat_openai as chat_module


def _make_access_token(*, expires_at: datetime) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": int(expires_at.timestamp())}).encode("utf-8")
    ).decode().rstrip("=")
    return f"{header}.{payload}.signature"


class _FakeResponse:
    def __init__(self, *, text: str = "pong", output: list[object] | None = None) -> None:
        self.id = "resp_123"
        self.error = None
        self.model = "gpt-5.4-mini"
        self.output = output or [
            SimpleNamespace(
                type="message",
                id="msg_123",
                content=[
                    SimpleNamespace(
                        type="output_text",
                        text=text,
                        annotations=[],
                    )
                ],
            )
        ]
        self.usage = None
        self.service_tier = None

    def model_dump(self, *, exclude_none: bool = True, mode: str = "json") -> dict:
        if self.output and getattr(self.output[0], "type", None) == "function_call":
            return {
                "id": self.id,
                "object": "response",
                "model": self.model,
                "output": [
                    {
                        "type": "function_call",
                        "name": self.output[0].name,
                        "arguments": self.output[0].arguments,
                        "call_id": self.output[0].call_id,
                    }
                ],
                "status": "completed",
            }
        return {
            "id": self.id,
            "object": "response",
            "model": self.model,
            "output": [
                {
                    "type": "message",
                    "id": "msg_123",
                    "content": [
                        {
                            "type": "output_text",
                            "text": getattr(self.output[0].content[0], "text", ""),
                        }
                    ],
                }
            ],
            "status": "completed",
        }


class _FakeEvent:
    def __init__(self, response: _FakeResponse) -> None:
        self.type = "response.completed"
        self.response = response


class _FakeStream:
    def __init__(self, events: list[object]) -> None:
        self._events = events

    def __enter__(self) -> _FakeStream:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False

    def __iter__(self):
        return iter(self._events)


def _install_fake_clients(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: _FakeResponse | None = None,
) -> dict[str, object]:
    calls: dict[str, object] = {}
    fake_response = response or _FakeResponse(text="pong")

    class FakeResponses:
        def create(self, **payload: object) -> _FakeStream:
            calls["payload"] = payload
            return _FakeStream([_FakeEvent(fake_response)])

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            calls.setdefault("openai_init", []).append(kwargs)
            self.responses = FakeResponses()

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs: object) -> None:
            calls.setdefault("async_openai_init", []).append(kwargs)
            self.responses = FakeResponses()

    monkeypatch.setattr(chat_module.openai, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(chat_module.openai, "AsyncOpenAI", FakeAsyncOpenAI)
    monkeypatch.setattr(
        chat_module,
        "resolve_codex_oauth_credentials",
        lambda **_: CodexOAuthCredentials(
            token="codex-access-token",
            base_url="https://chatgpt.com/backend-api/codex",
            source="codex_auth_file",
            account_id="acct_123",
        ),
    )
    return calls


def test_build_codex_responses_payload_moves_system_messages_to_instructions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_clients(monkeypatch)
    llm = ChatOpenAICodexOAuth(model="gpt-5.4-mini", auth_mode="codex_oauth")

    payload = llm._build_codex_responses_payload(
        [SystemMessage("Be terse."), HumanMessage("ping")],
    )

    assert payload["model"] == "gpt-5.4-mini"
    assert payload["instructions"] == "Be terse."
    assert payload["input"] == [{"role": "user", "content": "ping"}]
    assert payload["store"] is False


def test_build_codex_responses_payload_injects_default_instructions_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_clients(monkeypatch)
    llm = ChatOpenAICodexOAuth(model="gpt-5.4-mini", auth_mode="codex_oauth")

    payload = llm._build_codex_responses_payload([HumanMessage("ping")])

    assert payload["instructions"] == "You are a helpful assistant."


def test_build_codex_responses_payload_flattens_tools_and_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_clients(monkeypatch)
    llm = ChatOpenAICodexOAuth(model="gpt-5.4-mini", auth_mode="codex_oauth")

    payload = llm._build_codex_responses_payload(
        [SystemMessage("Return JSON."), HumanMessage("ping")],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Lookup a value.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        tool_choice={"type": "function", "function": {"name": "lookup"}},
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "Example",
                "schema": {"type": "object", "properties": {"value": {"type": "string"}}},
                "strict": True,
            },
        },
    )

    assert payload["tools"] == [
        {
            "type": "function",
            "name": "lookup",
            "description": "Lookup a value.",
            "parameters": {"type": "object", "properties": {}},
        }
    ]
    assert payload["tool_choice"] == {"type": "function", "name": "lookup"}
    assert payload["text"]["format"]["type"] == "json_schema"
    assert "response_format" not in payload


def test_resolve_codex_oauth_credentials_refreshes_expired_file_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    auth_path = codex_home / "auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "last_refresh": "2026-03-28T15:55:46.035944Z",
                "tokens": {
                    "access_token": _make_access_token(
                        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5)
                    ),
                    "refresh_token": "refresh-token",
                    "account_id": "acct_123",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "access_token": "fresh-access-token",
                "refresh_token": "fresh-refresh-token",
            }

    monkeypatch.setattr(auth_module.httpx, "post", lambda *args, **kwargs: FakeResponse())

    credentials = resolve_codex_oauth_credentials()

    updated_doc = json.loads(auth_path.read_text(encoding="utf-8"))
    assert credentials.token == "fresh-access-token"
    assert updated_doc["tokens"]["access_token"] == "fresh-access-token"
    assert updated_doc["tokens"]["refresh_token"] == "fresh-refresh-token"
    assert updated_doc["last_refresh"]


def test_resolve_codex_oauth_credentials_requires_login_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))

    with pytest.raises(CodexOAuthLoginRequiredError) as error:
        resolve_codex_oauth_credentials()

    assert "codex login" in str(error.value)


def test_chat_openai_codex_oauth_invoke_uses_responses_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_clients(monkeypatch)
    llm = ChatOpenAICodexOAuth(model="gpt-5.4-mini", auth_mode="codex_oauth")

    response = llm.invoke([SystemMessage("Be terse."), HumanMessage("ping")])

    assert response.content == "pong"
    assert calls["payload"]["stream"] is True
    assert calls["payload"]["instructions"] == "Be terse."
    assert calls["payload"]["input"] == [{"role": "user", "content": "ping"}]


class ExampleStructuredResult(BaseModel):
    value: str


def test_chat_openai_codex_oauth_with_structured_output_parses_json_schema_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_clients(monkeypatch, response=_FakeResponse(text='{"value":"ok"}'))
    llm = ChatOpenAICodexOAuth(model="gpt-5.4-mini", auth_mode="codex_oauth")

    runnable = llm.with_structured_output(
        ExampleStructuredResult,
        method="json_schema",
    )
    result = runnable.invoke([HumanMessage("Return JSON.")])

    assert result == ExampleStructuredResult(value="ok")


def test_chat_openai_codex_oauth_parses_function_calls_into_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool_response = _FakeResponse(
        output=[
            SimpleNamespace(
                type="function_call",
                name="lookup",
                arguments='{"topic":"ai"}',
                call_id="call_123",
            )
        ]
    )
    _install_fake_clients(monkeypatch, response=tool_response)
    llm = ChatOpenAICodexOAuth(model="gpt-5.4-mini", auth_mode="codex_oauth")

    message = llm.invoke([HumanMessage("Use the tool.")])

    assert message.content == ""
    assert message.tool_calls == [
        {
            "name": "lookup",
            "args": {"topic": "ai"},
            "id": "call_123",
            "type": "tool_call",
        }
    ]
