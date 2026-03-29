import json
from datetime import datetime
from pathlib import Path

from xs2n.agents.schemas import Thread
from xs2n.twitter_nitter import NitterUnavailable, get_nitter_threads
from xs2n.twitter_twscrape import get_twscrape_threads


def get_twitter_handles(path: str | Path) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["handles"]


def get_twitter_threads_from_handles(handles: list[str], since_date: datetime) -> list[Thread]:
    try:
        return get_nitter_threads(handles=handles, since_date=since_date)
    except NitterUnavailable:
        return get_twscrape_threads(handles=handles, since_date=since_date)


def get_twitter_threads(handles_path: str | Path, since_date: datetime) -> list[Thread]:
    handles = get_twitter_handles(handles_path)
    return get_twitter_threads_from_handles(handles, since_date)
