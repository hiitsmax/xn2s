from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Literal

from agents import Agent, ModelSettings, RunConfig, Runner

from xs2n.utils.auth.openai_client import build_openai_responses_model


ReasoningEffort = Literal["none", "low", "medium", "high", "xhigh"]
Verbosity = Literal["low", "medium", "high"]

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_REASONING_EFFORT: ReasoningEffort = "medium"
DEFAULT_MAX_TURNS = 20
BASE_AGENT_NAME = "base_agent"


@dataclass(slots=True)
class BaseAgent:
    """
    AI-generated: This class was created with the assistance of an AI pair programmer.
    Thin Agents SDK wrapper with no tools: model settings plus instructions from ``load_prompt``.

    Purpose: Run a single streaming turn against the configured OpenAI Responses model.
    """

    name: str
    model: str
    reasoning_effort: ReasoningEffort
    instructions: str
    verbosity: Verbosity | None = None

    def invoke(self, prompt: str) -> dict[str, Any]:
        """
        AI-generated: This method was created with the assistance of an AI pair programmer.
        Run the agent synchronously and return status plus final model output string if any.
        """
        result = asyncio.run(self._run_streamed(prompt=prompt))
        return {
            "status": "completed",
            "final_output": getattr(result, "final_output", None),
        }

    async def _run_streamed(self, *, prompt: str) -> object:
        """
        AI-generated: This method was created with the assistance of an AI pair programmer.
        Drain the streamed run and return the SDK result object (for ``final_output``).
        """
        result = Runner.run_streamed(
            Agent(
                name=self.name,
                instructions=self.instructions,
                model=build_openai_responses_model(
                    model=self.model,
                    api_key=None,
                ),
                tools=[],
            ),
            input=prompt,
            max_turns=DEFAULT_MAX_TURNS,
            run_config=RunConfig(
                model_settings=ModelSettings(
                    store=False,
                    reasoning={"effort": self.reasoning_effort},
                    verbosity=self.verbosity,
                ),
            ),
        )
        async for _event in result.stream_events():
            pass
        return result
