from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from xs2n.profile.types import OnboardResult, ProfileEntry


DEFAULT_SOURCES_PATH = Path("data/sources.json")


def _empty_doc() -> dict[str, Any]:
    return {"profiles": []}


def load_sources(path: Path = DEFAULT_SOURCES_PATH) -> dict[str, Any]:
    if not path.exists():
        return _empty_doc()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _empty_doc()

    if not isinstance(data, dict):
        return _empty_doc()
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        data["profiles"] = []
    return data


def save_sources(doc: dict[str, Any], path: Path = DEFAULT_SOURCES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"{json.dumps(doc, ensure_ascii=False, indent=2)}\n",
        encoding="utf-8",
    )


def merge_profiles(
    new_entries: list[ProfileEntry],
    path: Path = DEFAULT_SOURCES_PATH,
) -> OnboardResult:
    doc = load_sources(path)
    profiles = doc.setdefault("profiles", [])

    existing = {
        str(item.get("handle", "")).lower()
        for item in profiles
        if isinstance(item, dict)
    }

    added = 0
    skipped = 0
    for entry in new_entries:
        if entry.handle in existing:
            skipped += 1
            continue
        profiles.append(
            {
                "handle": entry.handle,
                "added_via": entry.added_via,
                "added_at": entry.added_at,
            }
        )
        existing.add(entry.handle)
        added += 1

    save_sources(doc, path)
    return OnboardResult(added=added, skipped_duplicates=skipped, invalid=[])
