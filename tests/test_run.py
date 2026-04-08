from __future__ import annotations

import json
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

    class FakeBaseAgent:
        def __init__(
            self,
            *,
            name,
            model,
            reasoning_effort,
            instructions,
            verbosity=None,
        ) -> None:  # noqa: ANN001
            calls["build_scaffold"] = {
                "name": name,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "instructions": instructions,
                "verbosity": verbosity,
            }

        def invoke(self, prompt):  # noqa: ANN001, ANN201
            return FakeScaffold().invoke(prompt)

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

    monkeypatch.setattr(module, "datetime", FixedDateTime)
    monkeypatch.setattr(module, "get_twitter_threads", fake_get_twitter_threads)
    monkeypatch.setattr(module, "build_tweet_queue_items", fake_build_tweet_queue_items)
    monkeypatch.setattr(module, "save_tweet_queue", fake_save_tweet_queue)
    monkeypatch.setattr(module, "BaseAgent", FakeBaseAgent, raising=False)
    monkeypatch.setattr(
        module,
        "load_prompt",
        lambda agent_name: f"prompt for {agent_name}",
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "configure_phoenix_tracing",
        lambda: calls.setdefault("phoenix_tracing_configured", 0) or calls.__setitem__(
            "phoenix_tracing_configured",
            calls.get("phoenix_tracing_configured", 0) + 1,
        ),
        raising=False,
    )

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
        "name": "base_agent",
        "model": module.DEFAULT_MODEL,
        "reasoning_effort": module.DEFAULT_REASONING_EFFORT,
        "instructions": "prompt for base_agent",
        "verbosity": None,
    }
    assert calls["phoenix_tracing_configured"] == 1
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

    class FakeBaseAgent:
        def __init__(
            self,
            *,
            name,
            model,
            reasoning_effort,
            instructions,
            verbosity=None,
        ) -> None:  # noqa: ANN001
            calls["build_scaffold"] = {
                "name": name,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "instructions": instructions,
                "verbosity": verbosity,
            }

        def invoke(self, prompt):  # noqa: ANN001, ANN201
            return FakeScaffold().invoke(prompt)

    def fake_save_tweet_queue(path, items):  # noqa: ANN001, ANN202
        calls["save_queue"] = {
            "path": path,
            "items": items,
        }

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
    monkeypatch.setattr(module, "BaseAgent", FakeBaseAgent, raising=False)
    monkeypatch.setattr(
        module,
        "load_prompt",
        lambda agent_name: f"prompt for {agent_name}",
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "configure_phoenix_tracing",
        lambda: calls.setdefault("phoenix_tracing_configured", 0) or calls.__setitem__(
            "phoenix_tracing_configured",
            calls.get("phoenix_tracing_configured", 0) + 1,
        ),
        raising=False,
    )
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
        "name": "base_agent",
        "model": module.DEFAULT_MODEL,
        "reasoning_effort": module.DEFAULT_REASONING_EFFORT,
        "instructions": "prompt for base_agent",
        "verbosity": None,
    }
    assert calls["phoenix_tracing_configured"] == 1
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
    monkeypatch.setattr(
        module,
        "BaseAgent",
        lambda **_: FakeScaffold(),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "load_prompt",
        lambda agent_name: f"prompt for {agent_name}",
        raising=False,
    )
    monkeypatch.setattr(module, "configure_phoenix_tracing", lambda: True, raising=False)

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

    class FakeBaseAgent:
        def __init__(
            self,
            *,
            name,
            model,
            reasoning_effort,
            instructions,
            verbosity=None,
        ) -> None:  # noqa: ANN001
            assert name == "base_agent"
            assert instructions == "prompt for base_agent"

            calls["build_scaffold"] = {
                "model": model,
                "reasoning_effort": reasoning_effort,
            }

        def invoke(self, prompt):  # noqa: ANN001, ANN201
            return FakeScaffold().invoke(prompt)

    monkeypatch.setattr(
        module,
        "get_twitter_threads",
        lambda **_: [],
    )
    monkeypatch.setattr(module, "build_tweet_queue_items", lambda *, threads: [])
    monkeypatch.setattr(module, "save_tweet_queue", lambda path, items: None)
    monkeypatch.setattr(module, "BaseAgent", FakeBaseAgent, raising=False)
    monkeypatch.setattr(
        module,
        "load_prompt",
        lambda agent_name: f"prompt for {agent_name}",
        raising=False,
    )
    monkeypatch.setattr(module, "configure_phoenix_tracing", lambda: True, raising=False)

    exit_code = module.main(["--reasoning", "xhigh"])

    assert exit_code == 0
    assert calls["build_scaffold"]["reasoning_effort"] == "xhigh"


def test_main_can_route_queue_items_with_text_router(
    monkeypatch,
    capsys,
) -> None:  # noqa: ANN001
    calls: dict[str, object] = {}
    existing_queue = [
        TweetQueueItem(
            tweet_id="thread-1",
            account_handle="alice",
            text="plain tweet",
            quote_text="",
            image_description="",
            url_hint="",
            url="https://x.com/alice/status/post-1",
            created_at="2026-03-21T10:00:00Z",
            status="pending",
        ),
        TweetQueueItem(
            tweet_id="thread-2",
            account_handle="bob",
            text="look at this",
            quote_text="",
            image_description="bar chart screenshot",
            url_hint="",
            url="https://x.com/bob/status/post-2",
            created_at="2026-03-21T11:00:00Z",
            status="pending",
        ),
    ]
    provided_tweet_list_path = Path("/tmp/provided_tweet_list.json")

    class FakeRoutingResult:
        plain_ids = ["thread-1"]
        ambiguous_ids = []
        image_ids = ["thread-2"]
        external_ids = []

    def fake_route_tweet_rows(*, model, rows):  # noqa: ANN001, ANN202
        calls["route_tweet_rows"] = {
            "model": model,
            "rows": rows,
        }
        return FakeRoutingResult()

    monkeypatch.setattr(module, "load_tweet_queue", lambda path: existing_queue)
    monkeypatch.setattr(module, "save_tweet_queue", lambda path, items: None)
    monkeypatch.setattr(
        module,
        "BaseAgent",
        lambda **_: (_ for _ in ()).throw(AssertionError("scaffold should not run")),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "route_tweet_rows",
        fake_route_tweet_rows,
        raising=False,
    )
    monkeypatch.setattr(module, "configure_phoenix_tracing", lambda: True, raising=False)
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

    exit_code = module.main(
        [
            "--tweet-list-file",
            str(provided_tweet_list_path),
            "--route-text",
        ]
    )

    captured = capsys.readouterr()
    stdout = captured.out.strip().splitlines()

    assert exit_code == 0
    assert calls["route_tweet_rows"]["model"] == module.DEFAULT_MODEL
    assert [row.tweet_id for row in calls["route_tweet_rows"]["rows"]] == ["thread-1", "thread-2"]
    assert calls["route_tweet_rows"]["rows"][1].image_description == "bar chart screenshot"
    assert stdout == [
        "Reused 2 queue item(s).",
        "Queue items ready: 2",
        "Text router completed.",
        "Routing output: thread-1||thread-2|",
    ]


def test_main_can_build_issue_json_from_non_ambiguous_tweets(
    monkeypatch,
    capsys,
) -> None:  # noqa: ANN001
    calls: dict[str, object] = {}
    existing_queue = [
        TweetQueueItem(
            tweet_id="thread-1",
            account_handle="alice",
            text="plain tweet",
            quote_text="",
            image_description="",
            url_hint="",
            url="https://x.com/alice/status/post-1",
            created_at="2026-03-21T10:00:00Z",
            status="pending",
        ),
        TweetQueueItem(
            tweet_id="thread-2",
            account_handle="bob",
            text="unclear tweet",
            quote_text="",
            image_description="",
            url_hint="",
            url="https://x.com/bob/status/post-2",
            created_at="2026-03-21T11:00:00Z",
            status="pending",
        ),
        TweetQueueItem(
            tweet_id="thread-3",
            account_handle="carol",
            text="external link tweet",
            quote_text="",
            image_description="",
            url_hint="docs.example.com",
            url="https://x.com/carol/status/post-3",
            created_at="2026-03-21T12:00:00Z",
            status="pending",
        ),
    ]
    provided_tweet_list_path = Path("/tmp/provided_tweet_list.json")

    class FakeRoutingResult:
        plain_ids = ["thread-1"]
        ambiguous_ids = ["thread-2"]
        image_ids = []
        external_ids = ["thread-3"]

    class FakeIssueMap:
        def model_dump_json(self, **kwargs):  # noqa: ANN001, ANN201
            calls["issue_json_kwargs"] = kwargs
            return json.dumps(
                {
                    "issues": [
                        {
                            "issue_id": "issue_001",
                            "title": "One issue",
                            "description": "Groups non-ambiguous tweets.",
                            "tweet_links": [
                                {"tweet_id": "thread-1", "why": "reason one"},
                                {"tweet_id": "thread-3", "why": "reason two"},
                            ],
                        }
                    ]
                }
            )

    def fake_route_tweet_rows(*, model, rows):  # noqa: ANN001, ANN202
        calls["route_tweet_rows"] = {
            "model": model,
            "rows": rows,
        }
        return FakeRoutingResult()

    def fake_build_issue_map(*, model, rows):  # noqa: ANN001, ANN202
        calls["build_issue_map"] = {
            "model": model,
            "rows": rows,
        }
        return FakeIssueMap()

    monkeypatch.setattr(module, "load_tweet_queue", lambda path: existing_queue)
    monkeypatch.setattr(module, "save_tweet_queue", lambda path, items: None)
    monkeypatch.setattr(
        module,
        "BaseAgent",
        lambda **_: (_ for _ in ()).throw(AssertionError("scaffold should not run")),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "route_tweet_rows",
        fake_route_tweet_rows,
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "build_issue_map",
        fake_build_issue_map,
        raising=False,
    )
    monkeypatch.setattr(module, "configure_phoenix_tracing", lambda: True, raising=False)
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

    exit_code = module.main(
        [
            "--tweet-list-file",
            str(provided_tweet_list_path),
            "--build-issues",
        ]
    )

    captured = capsys.readouterr()
    stdout = captured.out.strip().splitlines()

    assert exit_code == 0
    assert calls["route_tweet_rows"]["model"] == module.DEFAULT_MODEL
    assert [row.tweet_id for row in calls["build_issue_map"]["rows"]] == ["thread-1", "thread-3"]
    assert calls["build_issue_map"]["rows"][1].url_hint == "docs.example.com"
    assert calls["issue_json_kwargs"] == {}
    assert stdout == [
        "Reused 3 queue item(s).",
        "Queue items ready: 3",
        "Issue organizer completed.",
        'Issue JSON: {"issues": [{"issue_id": "issue_001", "title": "One issue", "description": "Groups non-ambiguous tweets.", "tweet_links": [{"tweet_id": "thread-1", "why": "reason one"}, {"tweet_id": "thread-3", "why": "reason two"}]}]}',
    ]
