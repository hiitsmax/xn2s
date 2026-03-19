from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def test_digest_browser_probe_renders_and_saves_screenshot(
    tmp_path: Path,
) -> None:
    run_dir = Path("data/report_runs/20260318T225654Z")
    screenshot_path = tmp_path / "digest-browser.png"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "xs2n.ui.digest_browser_probe",
            "--run-dir",
            str(run_dir),
            "--screenshot",
            str(screenshot_path),
            "--issue-limit",
            "2",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=8,
    )

    payload = json.loads(completed.stdout)

    assert payload["load_run_ms"] < 3000
    assert len(payload["issue_timings_ms"]) == 2
    assert screenshot_path.exists()
    assert payload["screenshot_path"] == str(screenshot_path)
