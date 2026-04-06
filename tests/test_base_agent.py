from __future__ import annotations

import xs2n.agents.base_agent as module


def test_build_base_agent_loads_instructions_from_prompt_file(
    monkeypatch,
) -> None:  # noqa: ANN001
    monkeypatch.setattr(module, "configure_phoenix_tracing", lambda: True)

    scaffold = module.build_base_agent(
        model="gpt-5.4-mini",
        reasoning_effort="medium",
    )

    assert isinstance(scaffold, module.BaseAgent)
    assert scaffold.model == "gpt-5.4-mini"
    assert scaffold.reasoning_effort == "medium"
    assert "base agent" in scaffold.instructions.lower()


def test_base_agent_invoke_runs_openai_agents_sdk_without_tools(
    monkeypatch,
) -> None:  # noqa: ANN001
    captured: dict[str, object] = {}

    class FakeModel:
        pass

    class FakeAgent:
        def __init__(
            self,
            *,
            name: str,
            instructions: str,
            model: object,
            tools: list[object],
        ) -> None:
            captured["agent_init"] = {
                "name": name,
                "instructions": instructions,
                "model": model,
                "tools": tools,
            }

    class FakeRunner:
        @staticmethod
        def run_streamed(agent: object, input: str, **kwargs: object) -> object:
            captured["run_streamed"] = {
                "agent": agent,
                "input": input,
                "max_turns": kwargs.get("max_turns"),
                "run_config": kwargs.get("run_config"),
            }

            class FakeStreamingResult:
                final_output = "queue ready"

                async def stream_events(self):  # noqa: ANN202
                    for event in ():
                        yield event

            return FakeStreamingResult()

    def fake_build_openai_responses_model(*, model: str, api_key: str | None = None):  # noqa: ANN001, ANN202
        captured["build_model"] = {
            "model": model,
            "api_key": api_key,
        }
        return FakeModel()

    monkeypatch.setattr(module, "Agent", FakeAgent, raising=False)
    monkeypatch.setattr(module, "Runner", FakeRunner, raising=False)
    monkeypatch.setattr(
        module,
        "build_openai_responses_model",
        fake_build_openai_responses_model,
    )
    monkeypatch.setattr(
        module,
        "configure_phoenix_tracing",
        lambda: captured.setdefault("phoenix_tracing_configured", True),
    )

    scaffold = module.build_base_agent(
        model="gpt-5.4-mini",
        reasoning_effort="xhigh",
    )

    result = scaffold.invoke("Hello.")

    assert result == {"status": "completed", "final_output": "queue ready"}
    assert captured["phoenix_tracing_configured"] is True
    assert captured["build_model"] == {
        "model": "gpt-5.4-mini",
        "api_key": None,
    }
    assert captured["agent_init"]["name"] == "base_agent"
    assert captured["agent_init"]["instructions"] == scaffold.instructions
    assert captured["agent_init"]["tools"] == []
    assert captured["run_streamed"]["input"] == "Hello."
    assert captured["run_streamed"]["max_turns"] == module.DEFAULT_MAX_TURNS
    assert captured["run_streamed"]["run_config"].model_settings.store is False
