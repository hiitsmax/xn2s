from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass(slots=True)
class OnboardResult:
    added: int
    skipped_duplicates: int
    invalid: list[str]


@dataclass(slots=True)
class ProfileEntry:
    handle: str
    added_via: str
    added_at: str






