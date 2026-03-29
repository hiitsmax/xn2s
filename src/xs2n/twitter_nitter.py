from __future__ import annotations

from datetime import datetime

from ntscraper import Nitter
import requests

from xs2n.agents.schemas import Post, Thread


class NitterUnavailable(RuntimeError):
    pass


scraper: Nitter | None = None


def _create_scraper() -> Nitter:
    try:
        return Nitter(log_level=1, skip_instance_check=False)
    except requests.RequestException as error:
        raise NitterUnavailable(str(error)) from error
    except ValueError as error:
        if "Could not fetch instances" in str(error):
            raise NitterUnavailable(str(error)) from error
        raise


def _get_scraper() -> Nitter:
    global scraper
    if scraper is None:
        scraper = _create_scraper()
        if not getattr(scraper, "working_instances", []):
            scraper = None
            raise NitterUnavailable("No working Nitter instances available.")
    return scraper


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


def get_nitter_threads(*, handles: list[str], since_date: datetime) -> list[Thread]:
    since_value = since_date.date().isoformat()
    threads: list[Thread] = []
    current_scraper = _get_scraper()
    for handle in handles:
        scraped_timeline = current_scraper.get_tweets(handle, mode="user", since=since_value)
        threads.extend(_build_threads_for_handle(handle, scraped_timeline))
    return threads
