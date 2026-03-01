from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable

from xs2n.profile.types import ProfileEntry, OnboardResult

URL_HANDLE_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:x\.com|twitter\.com)/([A-Za-z0-9_]{1,15})(?:\b|/)")
HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")

def normalize_handle(raw: str) -> str | None:
    token = raw.strip()
    if not token:
        return None

    url_match = URL_HANDLE_RE.search(token)
    if url_match:
        token = url_match.group(1)

    token = token.strip().lstrip("@").split("/")[0].strip()
    if not token:
        return None

    if not HANDLE_RE.fullmatch(token):
        return None

    return token.lower()


def parse_handles(text: str) -> tuple[list[str], list[str]]:
    candidates = re.split(r"[\s,;]+", text)
    valid: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        normalized = normalize_handle(candidate)
        if normalized is None:
            invalid.append(candidate)
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        valid.append(normalized)

    return valid, invalid


def build_entries_from_handles(handles: Iterable[str], source: str) -> list[ProfileEntry]:
    timestamp = datetime.now(timezone.utc).isoformat()
    return [
        ProfileEntry(handle=handle, added_via=source, added_at=timestamp)
        for handle in handles
    ]