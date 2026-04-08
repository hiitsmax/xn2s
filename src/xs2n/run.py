from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

from xs2n.agents import (
    BASE_AGENT_NAME,
    BaseAgent,
    DEFAULT_MODEL,
    DEFAULT_REASONING_EFFORT,
    build_issue_map,
    route_tweet_rows,
)
from xs2n.prompts.manager import load_prompt
from xs2n.tools.cluster_state import load_tweet_queue, save_tweet_queue
from xs2n.agents.issue_organizer.utils import select_non_ambiguous_issue_rows
from xs2n.agents.text_router.utils import (
    build_routing_rows_from_queue_items,
    format_routing_result,
)
from xs2n.utils.tracing import configure_phoenix_tracing
from xs2n.utils.twitter import build_tweet_queue_items, get_twitter_threads


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_HANDLES_PATH = PROJECT_ROOT / "data" / "handles.json"
DEFAULT_QUEUE_PATH = PROJECT_ROOT / "data" / "cluster_builder" / "tweet_queue.json"
DEFAULT_SCAFFOLD_PROMPT = (
    "Inspect the prepared tweet queue, confirm what you can see, and describe the "
    "next pipeline step that a future domain agent should own."
)


def report_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare the tweet queue, then run the base Agents SDK scaffold.",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="How many recent hours of tweets to fetch when no existing tweet list is provided.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Model name used by the base Agents SDK scaffold.",
    )
    parser.add_argument(
        "--reasoning",
        choices=["low", "medium", "high", "xhigh"],
        default=DEFAULT_REASONING_EFFORT,
        help="Reasoning effort used by the base Agents SDK scaffold.",
    )
    parser.add_argument(
        "--queue-file",
        type=Path,
        default=DEFAULT_QUEUE_PATH,
        help="Path where the working tweet queue is written for this run.",
    )
    parser.add_argument(
        "--tweet-list-file",
        type=Path,
        help="Existing tweet-list JSON file to reuse instead of fetching fresh tweets.",
    )
    parser.add_argument(
        "--route-text",
        action="store_true",
        help="Run the strict text router on the prepared queue instead of the base scaffold.",
    )
    parser.add_argument(
        "--build-issues",
        action="store_true",
        help="Route the prepared queue, drop ambiguous tweets, and print validated issue JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        report_progress(f"Using queue file: {args.queue_file}")
        report_progress(f"Using model: {args.model}")
        report_progress(f"Using reasoning effort: {args.reasoning}")

        if args.tweet_list_file is not None:
            report_progress("Skipping fetch because --tweet-list-file was provided.")
            report_progress(f"Using provided tweet list file: {args.tweet_list_file}")
            queue_items = load_tweet_queue(args.tweet_list_file)
        else:
            since_date = datetime.now(UTC) - timedelta(hours=args.hours)
            report_progress(f"Starting run for the last {args.hours} hour(s).")
            report_progress(f"Using handles file: {DEFAULT_HANDLES_PATH}")
            threads = get_twitter_threads(
                handles_path=DEFAULT_HANDLES_PATH,
                since_date=since_date,
                report_progress=report_progress,
            )
            queue_items = build_tweet_queue_items(threads=threads)

        save_tweet_queue(args.queue_file, queue_items)
        report_progress(f"Wrote {len(queue_items)} queue item(s) to {args.queue_file}.")
        configure_phoenix_tracing()

        if args.build_issues:
            routing_rows = build_routing_rows_from_queue_items(queue_items)
            routing_result = route_tweet_rows(
                model=args.model,
                rows=routing_rows,
            )
            issue_rows = select_non_ambiguous_issue_rows(
                queue_items,
                routing_result=routing_result,
            )
            issue_map = build_issue_map(
                model=args.model,
                rows=issue_rows,
            )
        elif args.route_text:
            routing_rows = build_routing_rows_from_queue_items(queue_items)
            routing_result = route_tweet_rows(
                model=args.model,
                rows=routing_rows,
            )
        else:
            scaffold = BaseAgent(
                name=BASE_AGENT_NAME,
                model=args.model,
                reasoning_effort=args.reasoning,
                instructions=load_prompt(BASE_AGENT_NAME),
            )
            scaffold_result = scaffold.invoke(DEFAULT_SCAFFOLD_PROMPT)
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1

    if args.tweet_list_file is not None:
        print(f"Reused {len(queue_items)} queue item(s).", file=sys.stdout)
    else:
        print(f"Fetched {len(threads)} thread(s).", file=sys.stdout)
    print(f"Queue items ready: {len(queue_items)}", file=sys.stdout)
    if args.build_issues:
        print("Issue organizer completed.", file=sys.stdout)
        print(f"Issue JSON: {issue_map.model_dump_json()}", file=sys.stdout)
    elif args.route_text:
        print("Text router completed.", file=sys.stdout)
        print(
            f"Routing output: {format_routing_result(routing_result)}",
            file=sys.stdout,
        )
    else:
        print("Agents SDK scaffold completed.", file=sys.stdout)

        final_output = scaffold_result.get("final_output")
        if isinstance(final_output, str) and final_output.strip():
            print(f"Scaffold output: {final_output.strip()}", file=sys.stdout)
    return 0
