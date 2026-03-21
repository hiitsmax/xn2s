from __future__ import annotations

from pathlib import Path

import typer

from xs2n.cli.helpers import collect_multiline_paste
from xs2n.profile.helpers import build_entries_from_handles, parse_handles
from xs2n.profile.types import OnboardResult
from xs2n.storage import merge_profiles


def process_paste_parameters(*, sources_file: Path) -> tuple[OnboardResult, list[str]]:
    raw = collect_multiline_paste()
    handles, invalid = parse_handles(raw)
    if not handles:
        typer.echo("No valid handles found.")
        if invalid:
            typer.echo(f"Invalid tokens: {', '.join(invalid)}")
        raise typer.Exit(code=1)

    result = merge_profiles(
        build_entries_from_handles(handles, source="paste"),
        path=sources_file,
    )
    typer.echo(f"Added {result.added} profiles, skipped {result.skipped_duplicates} duplicates.")
    return result, invalid
