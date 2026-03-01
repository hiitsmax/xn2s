from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from xs2n.cli.helpers import collect_multiline_paste
from xs2n.profile.helpers import build_entries_from_handles, parse_handles
from xs2n.profile.types import OnboardResult
from xs2n.storage import merge_profiles


def process_paste_parameters(parameters: dict[str, Any]) -> tuple[OnboardResult, list[str]]:
    raw = collect_multiline_paste()
    handles, invalid = parse_handles(raw)
    if not handles:
        typer.echo("No valid handles found.")
        if invalid:
            typer.echo(f"Invalid tokens: {', '.join(invalid)}")
        raise typer.Exit(code=1)

    sources_file = Path(parameters["sources_file"])
    result = merge_profiles(
        build_entries_from_handles(handles, source="paste"),
        path=sources_file,
    )
    typer.echo(f"Added {result.added} profiles, skipped {result.skipped_duplicates} duplicates.")
    return result, invalid
