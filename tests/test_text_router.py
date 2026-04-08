from __future__ import annotations

import xs2n.agents.base_agent as base_agent_module
import xs2n.agents.text_router.main as module
from xs2n.agents.text_router.utils import (
    COMPACT_ID_ALPHABET,
    build_packed_routing_batch,
    decode_compact_id,
    encode_compact_id,
    parse_routing_output,
)
from xs2n.schemas.routing import RoutingTweetRow


def test_compact_ids_use_safe_ascii_base_and_expand_to_multiple_digits() -> None:
    assert encode_compact_id(0) == "0"
    assert encode_compact_id(1) == "1"
    assert encode_compact_id(len(COMPACT_ID_ALPHABET) - 1) == COMPACT_ID_ALPHABET[-1]
    assert encode_compact_id(len(COMPACT_ID_ALPHABET)) == "10"
    assert decode_compact_id("10") == len(COMPACT_ID_ALPHABET)
    assert "," not in COMPACT_ID_ALPHABET
    assert "|" not in COMPACT_ID_ALPHABET


def test_build_packed_routing_batch_assigns_short_ids_and_single_line_rows() -> None:
    packed_batch = build_packed_routing_batch(
        [
            RoutingTweetRow(
                tweet_id="tweet-1",
                text="Main text\nwith newline",
                quote_text="Quoted\ttext",
                image_description="chart screenshot",
                url_hint="docs.example.com",
            ),
            RoutingTweetRow(
                tweet_id="tweet-2",
                text="Just text",
            ),
        ]
    )

    assert packed_batch.short_to_tweet_id == {
        "0": "tweet-1",
        "1": "tweet-2",
    }
    assert packed_batch.prompt == (
        "0\tMain text with newline\tQuoted text\tchart screenshot\tdocs.example.com\n"
        "1\tJust text\t\t\t"
    )


def test_parse_routing_output_maps_short_ids_back_to_original_tweet_ids() -> None:
    packed_batch = build_packed_routing_batch(
        [
            RoutingTweetRow(tweet_id="tweet-1", text="plain"),
            RoutingTweetRow(tweet_id="tweet-2", text="ambiguous"),
            RoutingTweetRow(tweet_id="tweet-3", text="image", image_description="diagram"),
            RoutingTweetRow(tweet_id="tweet-4", text="external", url_hint="blog.example.com"),
        ]
    )

    result = parse_routing_output("0|1|2|3", packed_batch=packed_batch)

    assert result.plain_ids == ["tweet-1"]
    assert result.ambiguous_ids == ["tweet-2"]
    assert result.image_ids == ["tweet-3"]
    assert result.external_ids == ["tweet-4"]


def test_parse_routing_output_rejects_missing_or_duplicate_ids() -> None:
    packed_batch = build_packed_routing_batch(
        [
            RoutingTweetRow(tweet_id="tweet-1", text="plain"),
            RoutingTweetRow(tweet_id="tweet-2", text="ambiguous"),
        ]
    )

    try:
        parse_routing_output("0|0||", packed_batch=packed_batch)
    except ValueError as error:
        assert "exactly once" in str(error)
    else:
        raise AssertionError("Expected duplicate ids to be rejected.")


def test_route_tweet_rows_loads_prompt_and_uses_none_reasoning_and_verbosity(
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
                final_output = "0|1||"

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

    result = module.route_tweet_rows(
        model="gpt-5.4-mini",
        rows=[
            RoutingTweetRow(tweet_id="tweet-1", text="plain"),
            RoutingTweetRow(tweet_id="tweet-2", text="ambiguous"),
        ],
    )

    assert result.plain_ids == ["tweet-1"]
    assert result.ambiguous_ids == ["tweet-2"]
    assert result.image_ids == []
    assert result.external_ids == []
    assert captured["build_model"] == {
        "model": "gpt-5.4-mini",
        "api_key": None,
    }
    assert captured["agent_init"]["name"] == "text_router_agent"
    assert "<output_contract>" in captured["agent_init"]["instructions"].lower()
    assert "<output_examples>" in captured["agent_init"]["instructions"].lower()
    assert captured["agent_init"]["tools"] == []
    assert captured["run_streamed"]["input"] == "0\tplain\t\t\t\n1\tambiguous\t\t\t"
    assert captured["run_streamed"]["run_config"].model_settings.store is False
    assert captured["run_streamed"]["run_config"].model_settings.verbosity == "low"
    assert captured["run_streamed"]["run_config"].model_settings.reasoning.effort == "none"
