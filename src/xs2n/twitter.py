import json
from datetime import UTC, datetime, timedelta

from ntscraper import Nitter

scraper = Nitter(log_level=1, skip_instance_check=False)

def get_twitter_handles(path: str):
    with open(path, "r") as f:
        return json.load(f)["handles"]

def get_twitter_threads_from_handles(handles: list[str], since_date: datetime):
    return [scraper.get_tweets(handle, mode="user", since=since_date) for handle in handles]

def get_twitter_threads(handles_path: str, since_date: datetime):
    handles = get_twitter_handles(handles_path)
    return get_twitter_threads_from_handles(handles, since_date)