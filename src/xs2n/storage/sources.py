from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from xs2n.profile.types import OnboardResult, ProfileEntry


DEFAULT_SOURCES_PATH = Path("data/sources.json")
LEGACY_SOURCES_PATH = Path("data/sources.yaml")


def _empty_doc() -> dict[str, Any]:
    return {"profiles": []}


def _load_json_doc(path: Path, *, default_factory: Callable[[], Any]) -> Any:
    if not path.exists():
        return default_factory()

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_factory()


def _save_json_doc(doc: Any, path: Path, *, sort_keys: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    # Write atomically through a sibling temp file to avoid partial updates.
    temp_path.write_text(
        f"{json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=sort_keys)}\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def load_sources(path: Path | None = None) -> dict[str, Any]:
    storage_path = path or DEFAULT_SOURCES_PATH
    data = _load_json_doc(storage_path, default_factory=_empty_doc)

    if not isinstance(data, dict):
        return _empty_doc()
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        data["profiles"] = []
    return data


def save_sources(doc: dict[str, Any], path: Path | None = None) -> None:
    storage_path = path or DEFAULT_SOURCES_PATH
    _save_json_doc(doc, storage_path)


def _strip_yaml_scalar(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        quote = stripped[0]
        inner = stripped[1:-1]
        if quote == "'":
            return inner.replace("''", "'")
        return inner
    return stripped


def _parse_legacy_sources_yaml(text: str) -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped == "profiles:":
            continue

        if stripped.startswith("- "):
            if current is not None and current.get("handle"):
                profiles.append(current)
            current = {}
            stripped = stripped[2:].strip()
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                current[key.strip()] = _strip_yaml_scalar(value)
            continue

        if current is None or ":" not in stripped:
            continue

        key, value = stripped.split(":", 1)
        current[key.strip()] = _strip_yaml_scalar(value)

    if current is not None and current.get("handle"):
        profiles.append(current)
    return profiles


def migrate_legacy_sources_yaml(
    yaml_path: Path | None = None,
    json_path: Path | None = None,
) -> int:
    legacy_path = yaml_path or LEGACY_SOURCES_PATH
    storage_path = json_path or DEFAULT_SOURCES_PATH
    if not legacy_path.exists():
        return 0

    profiles = _parse_legacy_sources_yaml(legacy_path.read_text(encoding="utf-8"))
    if not profiles:
        _save_json_doc(_empty_doc(), storage_path)
        return 0

    deduped_profiles: list[dict[str, str]] = []
    seen_handles: set[str] = set()
    for profile in profiles:
        handle = str(profile.get("handle", "")).strip().lstrip("@").lower()
        if not handle or handle in seen_handles:
            continue
        seen_handles.add(handle)
        deduped_profiles.append(
            {
                "handle": handle,
                "added_via": (
                    str(profile.get("added_via", "legacy_migration")).strip()
                    or "legacy_migration"
                ),
                "added_at": str(profile.get("added_at", "")).strip(),
            }
        )

    _save_json_doc({"profiles": deduped_profiles}, storage_path)
    return len(deduped_profiles)


def merge_profiles(
    new_entries: list[ProfileEntry],
    path: Path | None = None,
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


def replace_profiles(
    new_entries: list[ProfileEntry],
    path: Path | None = None,
) -> OnboardResult:
    deduped_profiles: list[dict[str, str]] = []
    seen_handles: set[str] = set()
    skipped = 0

    for entry in new_entries:
        if entry.handle in seen_handles:
            skipped += 1
            continue

        seen_handles.add(entry.handle)
        deduped_profiles.append(
            {
                "handle": entry.handle,
                "added_via": entry.added_via,
                "added_at": entry.added_at,
            }
        )

    save_sources({"profiles": deduped_profiles}, path)
    return OnboardResult(
        added=len(deduped_profiles),
        skipped_duplicates=skipped,
        invalid=[],
    )
