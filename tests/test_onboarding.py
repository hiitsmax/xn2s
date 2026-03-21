from __future__ import annotations

from pathlib import Path

from xs2n.profile.helpers import build_entries_from_handles as build_entries, parse_handles
from xs2n.storage import (
    load_onboard_state,
    load_sources,
    merge_profiles,
    replace_profiles,
    save_onboard_state,
)


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
    sources_file = tmp_path / "sources.json"

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


def test_replace_profiles_overwrites_stale_entries(tmp_path: Path) -> None:
    sources_file = tmp_path / "sources.json"

    merge_profiles(
        build_entries(["alpha", "beta"], source="paste"),
        path=sources_file,
    )

    result = replace_profiles(
        build_entries(["beta", "gamma"], source="following_refresh"),
        path=sources_file,
    )

    assert result.added == 2
    assert result.skipped_duplicates == 0

    doc = load_sources(sources_file)
    assert doc["profiles"] == [
        {
            "handle": "beta",
            "added_via": "following_refresh",
            "added_at": doc["profiles"][0]["added_at"],
        },
        {
            "handle": "gamma",
            "added_via": "following_refresh",
            "added_at": doc["profiles"][1]["added_at"],
        },
    ]


def test_save_onboard_state_roundtrips(tmp_path: Path) -> None:
    state_file = tmp_path / "onboard_state.json"

    save_onboard_state(
        {
            "step": "completed",
            "handle": "alpha",
        },
        state_file,
    )

    assert load_onboard_state(state_file) == {
        "step": "completed",
        "handle": "alpha",
    }


def test_load_onboard_state_defaults_to_empty_for_invalid_json(tmp_path: Path) -> None:
    state_file = tmp_path / "onboard_state.json"
    state_file.write_text("{not json", encoding="utf-8")

    assert load_onboard_state(state_file) == {}
