from __future__ import annotations

import argparse
from pathlib import Path
import sys
import json
from datetime import UTC, datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = PROJECT_ROOT / "src"
DATA_PATH = PROJECT_ROOT / "data"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import xs2n.twitter as twitter

handles = json.load(open(DATA_PATH / "handles.json", "r"))
threads = twitter.get_twitter_threads_from_handles(handles["handles"], datetime.now(UTC) - timedelta(hours=24))
print(threads)
