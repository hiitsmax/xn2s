from __future__ import annotations

from xs2n.agents.base_agent import BaseAgent
from xs2n.prompts.manager import load_prompt
from xs2n.schemas.routing import RoutingResult, RoutingTweetRow

from .utils import build_packed_routing_batch, parse_routing_output


TEXT_ROUTER_AGENT_NAME = "text_router_agent"
DEFAULT_TEXT_ROUTER_REASONING = "none"
DEFAULT_TEXT_ROUTER_VERBOSITY = "low"


def route_tweet_rows(*, model: str, rows: list[RoutingTweetRow]) -> RoutingResult:
    """
    Route tweet rows with the strict text-router prompt and parse the grouped ids.
    """
    if not rows:
        return RoutingResult()

    packed_batch = build_packed_routing_batch(rows)
    router = BaseAgent(
        name=TEXT_ROUTER_AGENT_NAME,
        model=model,
        reasoning_effort=DEFAULT_TEXT_ROUTER_REASONING,
        verbosity=DEFAULT_TEXT_ROUTER_VERBOSITY,
        instructions=load_prompt(TEXT_ROUTER_AGENT_NAME),
    )
    result = router.invoke(packed_batch.prompt)
    final_output = result.get("final_output")
    if not isinstance(final_output, str) or not final_output.strip():
        raise RuntimeError("Text router returned no routing output.")
    return parse_routing_output(
        final_output,
        packed_batch=packed_batch,
    )
