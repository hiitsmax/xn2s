from __future__ import annotations

from pathlib import Path

from xs2n.profile.helpers import build_entries_from_handles as build_entries, parse_handles
from xs2n.storage import load_sources, merge_profiles


def test_parse_handles_accepts_handles_and_urls() -> None:
    text = "@Alice bob https://x.com/Charlie\ninvalid-handle, twitter.com/dora"
    handles, invalid = parse_handles(text)

    assert handles == ["alice", "bob", "charlie", "dora"]
    assert invalid == ["invalid-handle"]


def test_parse_handles_deduplicates_case_insensitive() -> None:
    text = "@Alpha alpha ALPHA"
    handles, invalid = parse_handles(text)

    assert handles == ["alpha"]
    assert invalid == []


def test_merge_profiles_adds_and_skips_duplicates(tmp_path: Path) -> None:
    sources_file = tmp_path / "sources.yaml"

    first_result = merge_profiles(
        build_entries(["alpha", "beta"], source="paste"),
        path=sources_file,
    )
    assert first_result.added == 2
    assert first_result.skipped_duplicates == 0

    second_result = merge_profiles(
        build_entries(["beta", "gamma"], source="paste"),
        path=sources_file,
    )
    assert second_result.added == 1
    assert second_result.skipped_duplicates == 1

    doc = load_sources(sources_file)
    handles = [item["handle"] for item in doc["profiles"]]
    assert handles == ["alpha", "beta", "gamma"]
