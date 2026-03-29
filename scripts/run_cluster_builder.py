from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from xs2n.cluster_builder.agent import build_cluster_builder_agent
from xs2n.cluster_builder.store import load_cluster_list, load_tweet_queue


RUN_PROMPT = "Process the current tweet queue to completion."

Langfuse = None
CallbackHandler = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the cluster builder over a tweet queue.",
    )
    parser.add_argument(
        "--queue-file",
        required=True,
        type=Path,
        help="Path to the queue JSON file.",
    )
    parser.add_argument(
        "--cluster-file",
        required=True,
        type=Path,
        help="Path to the cluster JSON file.",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.4-mini",
        help="Model name used by the deep agent.",
    )
    return parser


def _get_langfuse_classes():
    global Langfuse, CallbackHandler
    if Langfuse is None or CallbackHandler is None:
        from langfuse import Langfuse as langfuse_class
        from langfuse.langchain import CallbackHandler as callback_handler_class

        Langfuse = langfuse_class
        CallbackHandler = callback_handler_class
    return Langfuse, CallbackHandler


def _build_summary(*, queue_file: Path, cluster_file: Path) -> tuple[int, int, int]:
    queue = load_tweet_queue(queue_file)
    clusters = load_cluster_list(cluster_file)
    done_count = sum(item.status == "done" for item in queue)
    deferred_count = sum(item.status == "deferred" for item in queue)
    return done_count, deferred_count, len(clusters)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        langfuse_class, callback_handler_class = _get_langfuse_classes()
        langfuse_class()
        handler = callback_handler_class()
        agent = build_cluster_builder_agent(
            model=args.model,
            queue_path=args.queue_file,
            cluster_path=args.cluster_file,
        )
        agent.invoke(
            {"messages": [{"role": "user", "content": RUN_PROMPT}]},
            config={"callbacks": [handler]},
        )
        done_count, deferred_count, cluster_count = _build_summary(
            queue_file=args.queue_file,
            cluster_file=args.cluster_file,
        )
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1

    print("Cluster builder completed.", file=sys.stdout)
    print(f"Tweets done: {done_count}", file=sys.stdout)
    print(f"Tweets deferred: {deferred_count}", file=sys.stdout)
    print(f"Clusters written: {cluster_count}", file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
