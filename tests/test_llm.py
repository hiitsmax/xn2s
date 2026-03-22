from __future__ import annotations

from types import SimpleNamespace

from pydantic import BaseModel

from xs2n.llm import LLM
import xs2n.llm as llm_module


class ExampleResult(BaseModel):
    value: str


def test_llm_run_uses_openai_agents_sdk_for_structured_output(
    monkeypatch,
) -> None:  # noqa: ANN001
    calls: dict[str, object] = {}

    class FakeAsyncOpenAI:
        def __init__(self, *, api_key: str, base_url: str | None = None) -> None:
            calls["async_client"] = {
                "api_key": api_key,
                "base_url": base_url,
            }

    class FakeModel:
        def __init__(
            self,
            model: str,
            openai_client: object,
            *,
            model_is_explicit: bool = True,
        ) -> None:
            self.openai_client = openai_client
            calls["model"] = {
                "model": model,
                "openai_client": openai_client,
                "model_is_explicit": model_is_explicit,
            }

    class FakeAgent:
        def __init__(
            self,
            *,
            name: str,
            instructions: str,
            model: object,
            output_type: type[BaseModel],
        ) -> None:
            calls["agent"] = {
                "name": name,
                "instructions": instructions,
                "model": model,
                "output_type": output_type,
            }

    class FakeRunner:
        @staticmethod
        def run_sync(agent: object, input: str, **_: object) -> object:
            calls["runner"] = {
                "agent": agent,
                "input": input,
            }
            return SimpleNamespace(final_output=ExampleResult(value="ok"))

    monkeypatch.setattr(llm_module, "AsyncOpenAI", FakeAsyncOpenAI, raising=False)
    monkeypatch.setattr(llm_module, "OpenAIResponsesModel", FakeModel, raising=False)
    monkeypatch.setattr(llm_module, "Agent", FakeAgent, raising=False)
    monkeypatch.setattr(llm_module, "Runner", FakeRunner, raising=False)

    llm = LLM(model="gpt-5.4-mini", api_key="test-key")
    result = llm.run(
        prompt="Return structured output.",
        payload={"topic": "ai"},
        schema=ExampleResult,
    )

    assert result == ExampleResult(value="ok")
    assert calls["agent"]["name"] == "digest_llm"
    assert calls["agent"]["instructions"] == "Return structured output."
    assert calls["agent"]["output_type"] is ExampleResult
    assert calls["model"] == {
        "model": "gpt-5.4-mini",
        "openai_client": calls["agent"]["model"].openai_client,
        "model_is_explicit": True,
    }
    assert calls["runner"]["agent"].__class__.__name__ == "FakeAgent"
    assert calls["runner"]["input"] == 'Input JSON:\n{\n  "topic": "ai"\n}'
