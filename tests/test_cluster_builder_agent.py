from __future__ import annotations

from pathlib import Path

import xs2n.cluster_builder.agent as agent_module


def test_build_cluster_builder_agent_creates_single_cluster_builder_agent(
    monkeypatch, tmp_path: Path
) -> None:  # noqa: ANN001
    queue_path = tmp_path / "tweet_queue.json"
    cluster_path = tmp_path / "cluster_list.json"
    captured: dict[str, object] = {}

    class FakeLLM:
        def __init__(self, *, model, auth_mode):  # noqa: ANN001
            captured["llm"] = {
                "model": model,
                "auth_mode": auth_mode,
            }

    def fake_create_deep_agent(**kwargs):  # noqa: ANN001, ANN202
        captured["agent"] = kwargs
        return {"runtime": "ok", "kwargs": kwargs}

    monkeypatch.setattr(agent_module, "ChatOpenAICodexOAuth", FakeLLM)
    monkeypatch.setattr(agent_module, "_create_deep_agent", fake_create_deep_agent)

    runtime = agent_module.build_cluster_builder_agent(
        model="gpt-5.4-mini",
        queue_path=queue_path,
        cluster_path=cluster_path,
    )

    assert captured["llm"] == {
        "model": "gpt-5.4-mini",
        "auth_mode": "codex_oauth",
    }
    assert runtime["runtime"] == "ok"
    assert "get_queue_items" in captured["agent"]["system_prompt"]
    assert "deferred" in captured["agent"]["system_prompt"]
    assert "apply_cluster_mutation" in captured["agent"]["system_prompt"]
    assert "delegate tweet evaluation" not in captured["agent"]["system_prompt"].lower()
    assert "cluster builder agent" in captured["agent"]["system_prompt"].lower()
    assert "<tool_persistence_rules>" in captured["agent"]["system_prompt"]
    assert "<completeness_contract>" in captured["agent"]["system_prompt"]
    assert "<verification_loop>" in captured["agent"]["system_prompt"]
    assert "Do not ask the user for clarification." in captured["agent"]["system_prompt"]
    assert "subagents" not in captured["agent"]
    assert [tool.__name__ for tool in captured["agent"]["tools"]] == [
        "get_queue_items",
        "read_tweet",
        "defer_tweet",
        "complete_tweet",
        "list_clusters",
        "read_cluster",
        "apply_cluster_mutation",
    ]
