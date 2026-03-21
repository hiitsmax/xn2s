from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from xs2n.pipeline import DEFAULT_MODEL, run_digest_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the minimal agentic digest pipeline.",
    )
    parser.add_argument(
        "--input-file",
        required=True,
        type=Path,
        help="Path to a JSON file containing preassembled threads.",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        digest = run_digest_pipeline(
            input_file=args.input_file,
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
