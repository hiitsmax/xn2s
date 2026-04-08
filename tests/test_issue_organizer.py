from __future__ import annotations

import xs2n.agents.base_agent as base_agent_module
import xs2n.agents.issue_organizer.main as module
from xs2n.agents.issue_organizer.utils import (
    build_issue_rows_from_queue_items,
    parse_issue_map_output,
    select_non_ambiguous_issue_rows,
)
from xs2n.schemas.clustering import TweetQueueItem
from xs2n.schemas.issues import IssueMap, IssueTweetRow
from xs2n.schemas.routing import RoutingResult


def test_build_issue_rows_from_queue_items_preserves_supported_fields() -> None:
    rows = build_issue_rows_from_queue_items(
        [
            TweetQueueItem(
                tweet_id="tweet-1",
                account_handle="alice",
                text="Main text",
                quote_text="Quoted text",
                image_description="chart screenshot",
                url_hint="blog.example.com",
                url="https://x.com/alice/status/1",
                created_at="2026-03-21T10:00:00Z",
            )
        ]
    )

    assert rows == [
        IssueTweetRow(
            tweet_id="tweet-1",
            account_handle="alice",
            text="Main text",
            quote_text="Quoted text",
            image_description="chart screenshot",
            url_hint="blog.example.com",
        )
    ]


def test_select_non_ambiguous_issue_rows_excludes_ambiguous_ids_and_keeps_queue_order() -> None:
    items = [
        TweetQueueItem(
            tweet_id="tweet-1",
            account_handle="alice",
            text="first",
            url="https://x.com/alice/status/1",
            created_at="2026-03-21T10:00:00Z",
        ),
        TweetQueueItem(
            tweet_id="tweet-2",
            account_handle="bob",
            text="second",
            url="https://x.com/bob/status/2",
            created_at="2026-03-21T11:00:00Z",
        ),
        TweetQueueItem(
            tweet_id="tweet-3",
            account_handle="carol",
            text="third",
            url="https://x.com/carol/status/3",
            created_at="2026-03-21T12:00:00Z",
        ),
    ]

    rows = select_non_ambiguous_issue_rows(
        items,
        routing_result=RoutingResult(
            plain_ids=["tweet-3"],
            ambiguous_ids=["tweet-2"],
            image_ids=["tweet-1"],
            external_ids=[],
        ),
    )

    assert [row.tweet_id for row in rows] == ["tweet-1", "tweet-3"]


def test_parse_issue_map_output_rejects_duplicate_or_missing_tweet_coverage() -> None:
    rows = [
        IssueTweetRow(tweet_id="tweet-1", account_handle="alice", text="first"),
        IssueTweetRow(tweet_id="tweet-2", account_handle="bob", text="second"),
    ]

    duplicate_output = """
    {
      "issues": [
        {
          "issue_id": "issue_001",
          "title": "One issue",
          "description": "Groups both tweets incorrectly.",
          "tweet_links": [
            {"tweet_id": "tweet-1", "why": "reason one"},
            {"tweet_id": "tweet-1", "why": "reason duplicate"}
          ]
        }
      ]
    }
    """

    try:
        parse_issue_map_output(duplicate_output, rows=rows)
    except ValueError as error:
        assert "exactly once" in str(error)
    else:
        raise AssertionError("Expected duplicate tweet coverage to be rejected.")


def test_parse_issue_map_output_returns_validated_issue_map() -> None:
    rows = [
        IssueTweetRow(tweet_id="tweet-1", account_handle="alice", text="first"),
        IssueTweetRow(tweet_id="tweet-2", account_handle="bob", text="second"),
    ]

    result = parse_issue_map_output(
        """
        {
          "issues": [
            {
              "issue_id": "issue_001",
              "title": "One issue",
              "description": "Groups both tweets.",
              "tweet_links": [
                {"tweet_id": "tweet-1", "why": "reason one"},
                {"tweet_id": "tweet-2", "why": "reason two"}
              ]
            }
          ]
        }
        """,
        rows=rows,
    )

    assert isinstance(result, IssueMap)
    assert result.issues[0].issue_id == "issue_001"
    assert [link.tweet_id for link in result.issues[0].tweet_links] == ["tweet-1", "tweet-2"]


def test_build_issue_map_loads_prompt_and_uses_medium_reasoning_and_low_verbosity(
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
                final_output = """
                {
                  "issues": [
                    {
                      "issue_id": "issue_001",
                      "title": "Inference costs",
                      "description": "Tweets about cheaper inference.",
                      "tweet_links": [
                        {"tweet_id": "tweet-1", "why": "Main announcement"},
                        {"tweet_id": "tweet-2", "why": "Follow-up data point"}
                      ]
                    }
                  ]
                }
                """

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

    monkeypatch.setattr(base_agent_module, "Agent", FakeAgent, raising=False)
    monkeypatch.setattr(base_agent_module, "Runner", FakeRunner, raising=False)
    monkeypatch.setattr(
        base_agent_module,
        "build_openai_responses_model",
        fake_build_openai_responses_model,
    )

    result = module.build_issue_map(
        model="gpt-5.4-mini",
        rows=[
            IssueTweetRow(tweet_id="tweet-1", account_handle="alice", text="first"),
            IssueTweetRow(tweet_id="tweet-2", account_handle="bob", text="second"),
        ],
    )

    assert result.issues[0].issue_id == "issue_001"
    assert captured["build_model"] == {
        "model": "gpt-5.4-mini",
        "api_key": None,
    }
    assert captured["agent_init"]["name"] == "issue_organizer_agent"
    assert "<output_contract>" in captured["agent_init"]["instructions"].lower()
    assert "<completion_contract>" in captured["agent_init"]["instructions"].lower()
    assert captured["agent_init"]["tools"] == []
    assert '"tweet_id":"tweet-1"' in captured["run_streamed"]["input"]
    assert captured["run_streamed"]["run_config"].model_settings.store is False
    assert captured["run_streamed"]["run_config"].model_settings.verbosity == "low"
    assert captured["run_streamed"]["run_config"].model_settings.reasoning.effort == "medium"
