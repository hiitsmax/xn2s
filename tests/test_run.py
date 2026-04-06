from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import xs2n.run as module
from xs2n.schemas.clustering import TweetQueueItem
from xs2n.schemas.twitter import Post, Thread


def test_main_fetches_threads_builds_queue_and_runs_agent_scaffold(
    monkeypatch,
    capsys,
) -> None:  # noqa: ANN001
    fetched_threads = [
        Thread(
            thread_id="thread-1",
            account_handle="alice",
            posts=[
                Post(
                    post_id="post-1",
                    author_handle="alice",
                    created_at="2026-03-21T10:00:00Z",
                    text="AI inference costs are dropping fast.",
                    url="https://x.com/alice/status/post-1",
                )
            ],
        )
    ]
    queue_items = [
        TweetQueueItem(
            tweet_id="thread-1",
            account_handle="alice",
            text="AI inference costs are dropping fast.",
            url="https://x.com/alice/status/post-1",
            created_at="2026-03-21T10:00:00Z",
        )
    ]
    expected_since_date = datetime(2026, 3, 21, 18, 0, tzinfo=UTC)
    calls: dict[str, object] = {}

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN206
            return cls(2026, 3, 22, 0, 0, tzinfo=tz or UTC)

    class FakeScaffold:
        def invoke(self, prompt):  # noqa: ANN001, ANN201
            calls["invoke"] = {"prompt": prompt}
            return {"status": "completed", "final_output": "queue ready"}

    def fake_get_twitter_threads(*, handles_path, since_date, report_progress):  # noqa: ANN001, ANN202
        report_progress("fetch progress line")
        calls["fetch"] = {
            "handles_path": handles_path,
            "since_date": since_date,
        }
        return fetched_threads

    def fake_build_tweet_queue_items(*, threads):  # noqa: ANN001, ANN202
        calls["queue_items"] = threads
        return queue_items

    def fake_save_tweet_queue(path, items):  # noqa: ANN001, ANN202
        calls["save_queue"] = {
            "path": path,
            "items": items,
        }

    def fake_build_base_agent(*, model, reasoning_effort, queue_path):  # noqa: ANN001, ANN202
        calls["build_scaffold"] = {
            "model": model,
            "reasoning_effort": reasoning_effort,
            "queue_path": queue_path,
        }
        return FakeScaffold()

    monkeypatch.setattr(module, "datetime", FixedDateTime)
    monkeypatch.setattr(module, "get_twitter_threads", fake_get_twitter_threads)
    monkeypatch.setattr(module, "build_tweet_queue_items", fake_build_tweet_queue_items)
    monkeypatch.setattr(module, "save_tweet_queue", fake_save_tweet_queue)
    monkeypatch.setattr(module, "build_base_agent", fake_build_base_agent)

    exit_code = module.main(["--hours", "6"])

    captured = capsys.readouterr()
    stdout = captured.out.strip().splitlines()
    stderr = captured.err

    assert exit_code == 0
    assert calls["fetch"] == {
        "handles_path": module.PROJECT_ROOT / "data" / "handles.json",
        "since_date": expected_since_date,
    }
    assert calls["queue_items"] == fetched_threads
    assert calls["save_queue"] == {
        "path": module.DEFAULT_QUEUE_PATH,
        "items": queue_items,
    }
    assert calls["build_scaffold"] == {
        "model": module.DEFAULT_MODEL,
        "reasoning_effort": module.DEFAULT_REASONING_EFFORT,
        "queue_path": module.DEFAULT_QUEUE_PATH,
    }
    assert calls["invoke"]["prompt"] == module.DEFAULT_SCAFFOLD_PROMPT
    assert stdout == [
        "Fetched 1 thread(s).",
        "Queue items ready: 1",
        "Agents SDK scaffold completed.",
        "Scaffold output: queue ready",
    ]
    assert "Starting run for the last 6 hour(s)." in stderr
    assert "fetch progress line" in stderr


def test_main_reuses_provided_tweet_list_file_and_skips_fetch(
    monkeypatch,
    capsys,
) -> None:  # noqa: ANN001
    calls: dict[str, object] = {}
    existing_queue = [
        TweetQueueItem(
            tweet_id="thread-1",
            account_handle="alice",
            text="tweet",
            url="https://x.com/alice/status/post-1",
            created_at="2026-03-21T10:00:00Z",
            status="pending",
        ),
        TweetQueueItem(
            tweet_id="thread-2",
            account_handle="bob",
            text="tweet",
            url="https://x.com/bob/status/post-2",
            created_at="2026-03-21T11:00:00Z",
            status="pending",
        ),
    ]
    provided_tweet_list_path = Path("/tmp/provided_tweet_list.json")

    class FakeScaffold:
        def invoke(self, prompt):  # noqa: ANN001, ANN201
            calls["invoke"] = {"prompt": prompt}
            return {"status": "completed", "final_output": "queue reused"}

    def fake_save_tweet_queue(path, items):  # noqa: ANN001, ANN202
        calls["save_queue"] = {
            "path": path,
            "items": items,
        }

    def fake_build_base_agent(*, model, reasoning_effort, queue_path):  # noqa: ANN001, ANN202
        calls["build_scaffold"] = {
            "model": model,
            "reasoning_effort": reasoning_effort,
            "queue_path": queue_path,
        }
        return FakeScaffold()

    monkeypatch.setattr(
        module,
        "get_twitter_threads",
        lambda **_: (_ for _ in ()).throw(AssertionError("fetch should not run")),
    )
    monkeypatch.setattr(
        module,
        "build_tweet_queue_items",
        lambda **_: (_ for _ in ()).throw(AssertionError("queue rebuild should not run")),
    )
    monkeypatch.setattr(module, "save_tweet_queue", fake_save_tweet_queue)
    monkeypatch.setattr(module, "build_base_agent", fake_build_base_agent)
    monkeypatch.setattr(module, "load_tweet_queue", lambda path: existing_queue)

    exit_code = module.main(["--tweet-list-file", str(provided_tweet_list_path)])

    captured = capsys.readouterr()
    stdout = captured.out.strip().splitlines()
    stderr = captured.err

    assert exit_code == 0
    assert calls["save_queue"] == {
        "path": module.DEFAULT_QUEUE_PATH,
        "items": existing_queue,
    }
    assert calls["build_scaffold"] == {
        "model": module.DEFAULT_MODEL,
        "reasoning_effort": module.DEFAULT_REASONING_EFFORT,
        "queue_path": module.DEFAULT_QUEUE_PATH,
    }
    assert calls["invoke"]["prompt"] == module.DEFAULT_SCAFFOLD_PROMPT
    assert stdout == [
        "Reused 2 queue item(s).",
        "Queue items ready: 2",
        "Agents SDK scaffold completed.",
        "Scaffold output: queue reused",
    ]
    assert "Skipping fetch because --tweet-list-file was provided." in stderr


def test_main_fails_when_agent_scaffold_raises_runtime_error(
    monkeypatch,
    capsys,
) -> None:  # noqa: ANN001
    fetched_threads = [
        Thread(
            thread_id="thread-1",
            account_handle="alice",
            posts=[
                Post(
                    post_id="post-1",
                    author_handle="alice",
                    created_at="2026-03-21T10:00:00Z",
                    text="AI inference costs are dropping fast.",
                    url="https://x.com/alice/status/post-1",
                )
            ],
        )
    ]
    queue_items = [
        TweetQueueItem(
            tweet_id="thread-1",
            account_handle="alice",
            text="AI inference costs are dropping fast.",
            url="https://x.com/alice/status/post-1",
            created_at="2026-03-21T10:00:00Z",
        )
    ]

    class FakeScaffold:
        def invoke(self, prompt):  # noqa: ANN001, ANN201
            raise RuntimeError("Scaffold agent failed.")

    monkeypatch.setattr(module, "get_twitter_threads", lambda **_: fetched_threads)
    monkeypatch.setattr(module, "build_tweet_queue_items", lambda *, threads: queue_items)
    monkeypatch.setattr(module, "save_tweet_queue", lambda path, items: None)
    monkeypatch.setattr(module, "build_base_agent", lambda **_: FakeScaffold())

    exit_code = module.main([])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Scaffold agent failed." in captured.err


def test_main_passes_reasoning_effort_to_agent_scaffold(
    monkeypatch,
) -> None:  # noqa: ANN001
    calls: dict[str, object] = {}

    class FakeScaffold:
        def invoke(self, prompt):  # noqa: ANN001, ANN201
            return {"status": "completed", "final_output": "done"}

    def fake_build_base_agent(*, model, reasoning_effort, queue_path):  # noqa: ANN001, ANN202
        calls["build_scaffold"] = {
            "model": model,
            "reasoning_effort": reasoning_effort,
            "queue_path": queue_path,
        }
        return FakeScaffold()

    monkeypatch.setattr(
        module,
        "get_twitter_threads",
        lambda **_: [],
    )
    monkeypatch.setattr(module, "build_tweet_queue_items", lambda *, threads: [])
    monkeypatch.setattr(module, "save_tweet_queue", lambda path, items: None)
    monkeypatch.setattr(module, "build_base_agent", fake_build_base_agent)

    exit_code = module.main(["--reasoning", "xhigh"])

    assert exit_code == 0
    assert calls["build_scaffold"]["reasoning_effort"] == "xhigh"
