import json
from datetime import datetime
from pathlib import Path

from ntscraper import Nitter

from xs2n.agents.schemas import Post, Thread


scraper: Nitter | None = None


def _get_scraper() -> Nitter:
    global scraper
    if scraper is None:
        scraper = Nitter(log_level=1, skip_instance_check=False)
    return scraper


def get_twitter_handles(path: str | Path) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["handles"]


def _build_post(raw_post: dict) -> Post:
    user = raw_post.get("user", {})
    return Post(
        post_id=str(raw_post["id"]),
        author_handle=user.get("username", ""),
        created_at=raw_post["date"],
        text=raw_post.get("text", ""),
        url=raw_post.get("link", ""),
    )


def _build_thread(account_handle: str, raw_posts: list[dict]) -> Thread | None:
    if not raw_posts:
        return None
    posts = [_build_post(raw_post) for raw_post in raw_posts]
    return Thread(
        thread_id=posts[0].post_id,
        account_handle=posts[0].author_handle or account_handle,
        posts=posts,
    )


def _build_threads_for_handle(account_handle: str, scraped_timeline: dict) -> list[Thread]:
    threads: list[Thread] = []

    for raw_post in scraped_timeline.get("tweets", []):
        thread = _build_thread(account_handle, [raw_post])
        if thread is not None:
            threads.append(thread)

    for raw_thread in scraped_timeline.get("threads", []):
        thread = _build_thread(account_handle, raw_thread)
        if thread is not None:
            threads.append(thread)

    return threads


def get_twitter_threads_from_handles(handles: list[str], since_date: datetime) -> list[Thread]:
    since_value = since_date.date().isoformat()
    threads: list[Thread] = []
    current_scraper = _get_scraper()
    for handle in handles:
        scraped_timeline = current_scraper.get_tweets(handle, mode="user", since=since_value)
        threads.extend(_build_threads_for_handle(handle, scraped_timeline))
    return threads


def get_twitter_threads(handles_path: str | Path, since_date: datetime) -> list[Thread]:
    handles = get_twitter_handles(handles_path)
    return get_twitter_threads_from_handles(handles, since_date)
