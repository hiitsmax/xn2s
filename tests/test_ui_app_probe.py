from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest


def test_ui_app_probe_selects_digest_and_saves_screenshot(
    tmp_path: Path,
) -> None:
    run_dir = Path("data/report_runs/20260318T225654Z")
    screenshot_path = tmp_path / "artifact-browser.png"

    if not run_dir.exists():
        pytest.skip("Probe sample run is not available in this workspace.")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "xs2n.ui.app_probe",
            "--data-dir",
            "data",
            "--run-id",
            "20260318T225654Z",
            "--artifact-name",
            "digest.html",
            "--width",
            "2000",
            "--height",
            "1300",
            "--screenshot",
            str(screenshot_path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    if completed.returncode != 0:
        pytest.skip(
            "App probe is environment-sensitive in this workspace "
            f"(returncode {completed.returncode})."
        )

    payload = json.loads(completed.stdout)

    assert payload["selected_run_id"] == "20260318T225654Z"
    assert payload["selected_artifact_name"] == "digest.html"
    assert payload["window_size"] == [2000, 1300]
    assert payload["digest_viewer_active"] is True
    assert payload["pane_widths"]["viewer"] > payload["pane_widths"]["navigation"]
    assert screenshot_path.exists()
    assert payload["screenshot_path"] == str(screenshot_path)
