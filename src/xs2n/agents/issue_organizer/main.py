from __future__ import annotations

from xs2n.agents.base_agent import BaseAgent
from xs2n.prompts.manager import load_prompt
from xs2n.schemas.issues import IssueMap, IssueTweetRow

from .utils import build_issue_batch_prompt, parse_issue_map_output


ISSUE_ORGANIZER_AGENT_NAME = "issue_organizer_agent"
DEFAULT_ISSUE_ORGANIZER_REASONING = "medium"
DEFAULT_ISSUE_ORGANIZER_VERBOSITY = "low"


def build_issue_map(*, model: str, rows: list[IssueTweetRow]) -> IssueMap:
    """
    Organize the provided tweet rows into issue records and validate the JSON output.
    """
    if not rows:
        return IssueMap()

    organizer = BaseAgent(
        name=ISSUE_ORGANIZER_AGENT_NAME,
        model=model,
        reasoning_effort=DEFAULT_ISSUE_ORGANIZER_REASONING,
        verbosity=DEFAULT_ISSUE_ORGANIZER_VERBOSITY,
        instructions=load_prompt(ISSUE_ORGANIZER_AGENT_NAME),
    )
    result = organizer.invoke(build_issue_batch_prompt(rows))
    final_output = result.get("final_output")
    if not isinstance(final_output, str) or not final_output.strip():
        raise RuntimeError("Issue organizer returned no JSON output.")
    return parse_issue_map_output(final_output, rows=rows)
