from __future__ import annotations

from pathlib import Path


def load_prompt(agent_name: str) -> str:
    """
    AI-generated: This method was created with the assistance of an AI pair programmer.
    Load the UTF-8 prompt text for a named agent from the packaged prompts directory.

    Purpose: Centralize prompt file resolution so agents refer to a stable name instead of paths.
    Pre-conditions: ``agent_name`` is non-empty and matches a ``{agent_name}.txt`` file under
    ``xs2n.prompts`` (installed as package data).
    Post-conditions: Returns stripped prompt text on success; raises if the file is missing.
    Side effects: Reads from disk only.

    :param agent_name: Basename of the prompt file without ``.txt`` (e.g. ``"base_agent"``).
    :returns: File contents with leading/trailing whitespace stripped.
    :raises FileNotFoundError: If no ``{agent_name}.txt`` exists next to this module.
    :raises OSError: If the file cannot be read.
    """
    # Resolve sibling to this module so it works when the package is installed from wheel
    path = Path(__file__).resolve().parent / f"{agent_name}.txt"
    return path.read_text(encoding="utf-8").strip()
