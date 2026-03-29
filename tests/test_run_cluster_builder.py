from __future__ import annotations

import importlib.util
from pathlib import Path

from xs2n.cluster_builder.schemas import Cluster, TweetQueueItem


def load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_cluster_builder.py"
    spec = importlib.util.spec_from_file_location("run_cluster_builder_script", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_main_builds_agent_and_passes_langfuse_callback(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # noqa: ANN001
    module = load_script_module()
    queue_path = tmp_path / "tweet_queue.json"
    cluster_path = tmp_path / "cluster_list.json"
    calls: dict[str, object] = {}

    class FakeLangfuse:
        def __init__(self):  # noqa: D107
            calls["langfuse"] = True

    class FakeCallbackHandler:
        def __init__(self):  # noqa: D107
            calls["handler"] = "created"

    class FakeAgent:
        def invoke(self, payload, config):  # noqa: ANN001, ANN201
            calls["invoke"] = {
                "payload": payload,
                "config": config,
            }
            return {"ok": True}

    def fake_build_cluster_builder_agent(*, model, queue_path, cluster_path):  # noqa: ANN001, ANN202
        calls["build_agent"] = {
            "model": model,
            "queue_path": queue_path,
            "cluster_path": cluster_path,
        }
        return FakeAgent()

    monkeypatch.setattr(module, "Langfuse", FakeLangfuse)
    monkeypatch.setattr(module, "CallbackHandler", FakeCallbackHandler)
    monkeypatch.setattr(module, "build_cluster_builder_agent", fake_build_cluster_builder_agent)
    monkeypatch.setattr(
        module,
        "load_tweet_queue",
        lambda path: [
            TweetQueueItem(
                tweet_id="tweet-1",
                account_handle="alice",
                text="tweet",
                url="https://x.com/alice/status/tweet-1",
                created_at="2026-03-28T16:00:00Z",
                status="done",
            ),
            TweetQueueItem(
                tweet_id="tweet-2",
                account_handle="alice",
                text="tweet",
                url="https://x.com/alice/status/tweet-2",
                created_at="2026-03-28T16:00:00Z",
                status="deferred",
            ),
        ],
    )
    monkeypatch.setattr(
        module,
        "load_cluster_list",
        lambda path: [
            Cluster(
                cluster_id="cluster_001",
                title="Inference costs",
                description="desc",
                tweet_ids=["tweet-1"],
            )
        ],
    )

    exit_code = module.main(
        [
            "--queue-file",
            str(queue_path),
            "--cluster-file",
            str(cluster_path),
            "--model",
            "gpt-5.4-mini",
        ]
    )

    stdout = capsys.readouterr().out.strip().splitlines()

    assert exit_code == 0
    assert calls["langfuse"] is True
    assert calls["handler"] == "created"
    assert calls["build_agent"] == {
        "model": "gpt-5.4-mini",
        "queue_path": queue_path,
        "cluster_path": cluster_path,
    }
    assert calls["invoke"]["config"]["callbacks"][0].__class__.__name__ == "FakeCallbackHandler"
    assert "Process the current tweet queue to completion." in calls["invoke"]["payload"]["messages"][0]["content"]
    assert stdout == [
        "Cluster builder completed.",
        "Tweets done: 1",
        "Tweets deferred: 1",
        "Clusters written: 1",
    ]
