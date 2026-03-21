from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from xs2n.agents.digest.credentials import DEFAULT_CODEX_BASE_URL, resolve_digest_credentials
from xs2n.agents.digest.llm import DigestLLM, _strict_json_schema


class _SimpleResult(BaseModel):
    answer: str


def test_resolve_digest_credentials_prefers_openai_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")

    credentials = resolve_digest_credentials()

    assert credentials.token == "sk-test"
    assert credentials.base_url == "https://example.test/v1"
    assert credentials.source == "openai_api_key"


def test_resolve_digest_credentials_uses_codex_auth_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "codex-access-token",
                    "refresh_token": "codex-refresh-token",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    credentials = resolve_digest_credentials()

    assert credentials.token == "codex-access-token"
    assert credentials.base_url == DEFAULT_CODEX_BASE_URL
    assert credentials.source == "codex_auth_file"


def test_resolve_digest_credentials_requires_api_key_or_codex_auth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex"))
    monkeypatch.setattr(
        "xs2n.agents.digest.credentials._read_codex_keychain_auth",
        lambda codex_home: None,
    )

    with pytest.raises(RuntimeError) as error:
        resolve_digest_credentials()

    assert "run `xs2n report auth`" in str(error.value)


def test_digest_llm_streams_structured_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_calls: list[dict[str, str | None]] = []
    stream_calls: list[dict[str, object]] = []

    class FakeStream:
        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return False

        def __iter__(self):  # noqa: ANN204
            return iter(
                [
                    SimpleNamespace(
                        type="response.output_text.done",
                        text='{"answer":"OK"}',
                    )
                ]
            )

        def get_final_response(self):  # noqa: ANN204
            return SimpleNamespace(output=[])

    class FakeOpenAI:
        def __init__(self, *, api_key: str, base_url: str | None = None) -> None:
            init_calls.append({"api_key": api_key, "base_url": base_url})
            self.responses = self

        def stream(self, **kwargs):  # noqa: ANN003, ANN204
            stream_calls.append(kwargs)
            return FakeStream()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("xs2n.agents.digest.llm.OpenAI", FakeOpenAI)

    llm = DigestLLM(model="gpt-5.4")
    result = llm.run(
        prompt="Return JSON only.",
        payload={"value": 7},
        schema=_SimpleResult,
    )

    assert result == _SimpleResult(answer="OK")
    assert init_calls == [{"api_key": "sk-test", "base_url": None}]
    assert len(stream_calls) == 1
    request = stream_calls[0]
    assert request["model"] == "gpt-5.4"
    assert request["store"] is False
    assert request["instructions"] == "Return JSON only."
    assert request["input"] == [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": 'Input JSON:\n{\n  "value": 7\n}',
                }
            ],
        }
    ]
    assert request["text"] == {
        "format": {
            "type": "json_schema",
            "name": "simple_result",
            "schema": _strict_json_schema(_SimpleResult.model_json_schema()),
            "strict": True,
        }
    }


def test_digest_llm_writes_explicit_trace_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeStream:
        def __enter__(self):  # noqa: ANN204
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001, ANN204
            return False

        def __iter__(self):  # noqa: ANN204
            return iter(
                [
                    SimpleNamespace(
                        type="response.output_text.done",
                        text='{"answer":"OK"}',
                    )
                ]
            )

        def get_final_response(self):  # noqa: ANN204
            return SimpleNamespace(output=[])

    class FakeOpenAI:
        def __init__(self, *, api_key: str, base_url: str | None = None) -> None:
            self.responses = self

        def stream(self, **kwargs):  # noqa: ANN003, ANN204
            return FakeStream()

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr("xs2n.agents.digest.llm.OpenAI", FakeOpenAI)

    llm = DigestLLM(model="gpt-5.4")
    llm.configure_run_logging(run_dir=tmp_path)

    result = llm.run(
        prompt="Return JSON only.",
        payload={"thread": {"thread_id": "conv-1"}},
        schema=_SimpleResult,
        phase_name="group_issues",
        item_id="conv-1",
    )

    trace_path = tmp_path / "llm_calls" / "001_group_issues_conv-1.json"
    trace_doc = json.loads(trace_path.read_text(encoding="utf-8"))

    assert result == _SimpleResult(answer="OK")
    assert trace_doc["phase"] == "group_issues"
    assert trace_doc["item_id"] == "conv-1"
    assert trace_doc["schema_name"] == "_SimpleResult"


def test_digest_llm_surfaces_codex_unsupported_model_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(
        json.dumps({"tokens": {"access_token": "codex-access-token"}}),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    class FakeBadRequestError(Exception):
        pass

    class FailingOpenAI:
        def __init__(self, *, api_key: str, base_url: str | None = None) -> None:
            self.responses = self

        def stream(self, **kwargs):  # noqa: ANN003, ANN204
            raise FakeBadRequestError(
                "The 'gpt-4.1-mini' model is not supported when using Codex with a ChatGPT account."
            )

    monkeypatch.setattr("xs2n.agents.digest.llm.BadRequestError", FakeBadRequestError)
    monkeypatch.setattr("xs2n.agents.digest.llm.OpenAI", FailingOpenAI)

    llm = DigestLLM(model="gpt-4.1-mini")

    with pytest.raises(RuntimeError) as error:
        llm.run(
            prompt="Return JSON only.",
            payload={"value": 7},
            schema=_SimpleResult,
        )

    assert "Model `gpt-4.1-mini` is not supported via Codex auth." in str(error.value)
