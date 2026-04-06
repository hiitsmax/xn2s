from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from agents import Agent, ModelSettings, RunConfig, Runner, function_tool

from xs2n.prompts.manager import load_prompt
from xs2n.tools.cluster_state import load_tweet_queue
from xs2n.utils.auth.openai_client import build_openai_responses_model
from xs2n.utils.tracing import configure_phoenix_tracing


ReasoningEffort = Literal["low", "medium", "high", "xhigh"]

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_REASONING_EFFORT: ReasoningEffort = "medium"
DEFAULT_MAX_TURNS = 20
BASE_AGENT_PROMPT_NAME = "base_agent"


def _build_queue_preview_tool(*, queue_path: Path) -> object:
    def read_queue_preview() -> dict[str, object]:
        """Return a small preview of the prepared tweet queue."""

        queue = load_tweet_queue(queue_path)
        return {
            "queue_path": str(queue_path),
            "tweet_count": len(queue),
            "tweet_ids": [item.tweet_id for item in queue[:5]],
        }

    read_queue_preview.__name__ = "read_queue_preview"
    return function_tool(read_queue_preview)


@dataclass(slots=True)
class BaseAgent:
    model: str
    reasoning_effort: ReasoningEffort
    queue_path: Path
    instructions: str

    def invoke(self, prompt: str) -> dict[str, Any]:
        result = asyncio.run(self._run_streamed(prompt=prompt))
        return {
            "status": "completed",
            "final_output": getattr(result, "final_output", None),
        }

    async def _run_streamed(self, *, prompt: str) -> object:
        result = Runner.run_streamed(
            Agent(
                name="base_agent",
                instructions=self.instructions,
                model=build_openai_responses_model(
                    model=self.model,
                    api_key=None,
                ),
                tools=[_build_queue_preview_tool(queue_path=self.queue_path)],
            ),
            input=prompt,
            max_turns=DEFAULT_MAX_TURNS,
            run_config=RunConfig(
                model_settings=ModelSettings(
                    store=False,
                    reasoning={"effort": self.reasoning_effort},
                ),
            ),
        )
        async for _event in result.stream_events():
            pass
        return result


def build_base_agent(
    *,
    model: str,
    reasoning_effort: ReasoningEffort,
    queue_path: str | Path,
) -> BaseAgent:
    configure_phoenix_tracing()
    return BaseAgent(
        model=model,
        reasoning_effort=reasoning_effort,
        queue_path=Path(queue_path),
        instructions=load_prompt(BASE_AGENT_PROMPT_NAME),
    )
