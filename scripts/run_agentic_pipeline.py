from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from xs2n.agents.pipeline import DEFAULT_MODEL, run_digest_pipeline
from xs2n.twitter import get_twitter_threads


DEFAULT_HANDLES_PATH = PROJECT_ROOT / "data" / "handles.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch recent tweets and run the digest pipeline.",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        type=Path,
        help="Path where the final digest JSON is written.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="OpenAI model name used for the pipeline.",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="How many recent hours of tweets to fetch before running the digest.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        since_date = datetime.now(UTC) - timedelta(hours=args.hours)
        threads = get_twitter_threads(
            handles_path=DEFAULT_HANDLES_PATH,
            since_date=since_date,
        )
        digest = run_digest_pipeline(
            threads=threads,
            output_file=args.output_file,
            model=args.model,
        )
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(
        f"Wrote {digest.issue_count} issues to {args.output_file}.",
        file=sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
