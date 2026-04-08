from __future__ import annotations

import json

from xs2n.schemas.clustering import TweetQueueItem
from xs2n.schemas.issues import IssueMap, IssueTweetRow
from xs2n.schemas.routing import RoutingResult


def build_issue_rows_from_queue_items(items: list[TweetQueueItem]) -> list[IssueTweetRow]:
    return [
        IssueTweetRow(
            tweet_id=item.tweet_id,
            account_handle=item.account_handle,
            text=item.text,
            quote_text=item.quote_text,
            image_description=item.image_description,
            url_hint=item.url_hint,
        )
        for item in items
    ]


def select_non_ambiguous_issue_rows(
    items: list[TweetQueueItem],
    *,
    routing_result: RoutingResult,
) -> list[IssueTweetRow]:
    ambiguous_ids = set(routing_result.ambiguous_ids)
    selected_items = [item for item in items if item.tweet_id not in ambiguous_ids]
    return build_issue_rows_from_queue_items(selected_items)


def build_issue_batch_prompt(rows: list[IssueTweetRow]) -> str:
    return json.dumps(
        {
            "tweets": [row.model_dump(mode="json") for row in rows],
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )


def parse_issue_map_output(output: str, *, rows: list[IssueTweetRow]) -> IssueMap:
    try:
        parsed_output = json.loads(output)
    except json.JSONDecodeError as error:
        raise ValueError("Issue organizer output must be valid JSON.") from error

    issue_map = IssueMap.model_validate(parsed_output)
    _validate_issue_map_coverage(issue_map, rows=rows)
    return issue_map


def _validate_issue_map_coverage(issue_map: IssueMap, *, rows: list[IssueTweetRow]) -> None:
    expected_ids = {row.tweet_id for row in rows}
    seen_ids: set[str] = set()

    for issue in issue_map.issues:
        if not issue.tweet_links:
            raise ValueError("Each issue must include at least one linked tweet.")
        for tweet_link in issue.tweet_links:
            if tweet_link.tweet_id not in expected_ids:
                raise ValueError(f"Unknown tweet id in issue output: {tweet_link.tweet_id!r}")
            if tweet_link.tweet_id in seen_ids:
                raise ValueError("Each input tweet id must appear exactly once in the issue output.")
            seen_ids.add(tweet_link.tweet_id)

    if seen_ids != expected_ids:
        raise ValueError("Each input tweet id must appear exactly once in the issue output.")
