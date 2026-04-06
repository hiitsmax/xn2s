from __future__ import annotations

from pathlib import Path


def load_prompt(agent_name: str) -> str:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.
    Load the UTF-8 prompt text for a named agent from the packaged prompts directory.

    Purpose: Centralize prompt file resolution so agents refer to a stable name instead of paths.
    Pre-conditions: ``agent_name`` is non-empty and a file ``{agent_name}_prompt.txt`` exists under
    ``xs2n.prompts`` (installed as package data).
    Post-conditions: Returns stripped prompt text on success; raises if the file is missing.
    Side effects: Reads from disk only.

    :param agent_name: Logical agent id (e.g. ``"base_agent"`` → ``base_agent_prompt.txt``).
    :returns: File contents with leading/trailing whitespace stripped.
    :raises FileNotFoundError: If the matching ``*_prompt.txt`` file does not exist.
    :raises OSError: If the file cannot be read.
    """
    path = Path(__file__).resolve().parent / f"{agent_name}_prompt.txt"
    return path.read_text(encoding="utf-8").strip()
