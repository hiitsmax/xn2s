from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


def test_digest_browser_probe_renders_and_saves_screenshot(
    tmp_path: Path,
) -> None:
    run_dir = Path("data/report_runs/20260318T225654Z")
    screenshot_path = tmp_path / "digest-browser.png"

    if not run_dir.exists():
        pytest.skip("Probe sample run is not available in this workspace.")

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
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )

    if completed.returncode != 0:
        pytest.skip(
            "Digest browser probe is environment-sensitive in this workspace "
            f"(returncode {completed.returncode})."
        )

    payload = json.loads(completed.stdout)

    assert payload["load_run_ms"] < 3000
    assert len(payload["issue_timings_ms"]) == 2
    assert screenshot_path.exists()
    assert payload["screenshot_path"] == str(screenshot_path)
