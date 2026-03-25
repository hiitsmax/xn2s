from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

from xs2n.agents.schemas import DigestOutput, Post, Thread


def load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_agentic_pipeline.py"
    spec = importlib.util.spec_from_file_location("run_agentic_pipeline_script", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_main_fetches_tweets_before_running_pipeline(tmp_path: Path, monkeypatch, capsys) -> None:  # noqa: ANN001
    module = load_script_module()
    output_path = tmp_path / "digest.json"
    fetched_threads = [
        Thread(
            thread_id="thread-1",
            account_handle="alice",
            posts=[
                Post(
                    post_id="post-1",
                    author_handle="alice",
                    created_at="2026-03-21T10:00:00Z",
                    text="AI inference costs are dropping fast.",
                    url="https://x.com/alice/status/post-1",
                )
            ],
        )
    ]
    expected_since_date = datetime(2026, 3, 21, 18, 0, tzinfo=UTC)
    calls: dict[str, object] = {}

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ANN206
            return cls(2026, 3, 22, 0, 0, tzinfo=tz or UTC)

    def fake_get_twitter_threads(*, handles_path, since_date):  # noqa: ANN001, ANN202
        calls["fetch"] = {
            "handles_path": handles_path,
            "since_date": since_date,
        }
        return fetched_threads

    def fake_run_digest_pipeline(*, threads, output_file, model):  # noqa: ANN001, ANN202
        calls["pipeline"] = {
            "threads": threads,
            "output_file": output_file,
            "model": model,
        }
        return DigestOutput(
            generated_at="2026-03-21T10:00:00Z",
            issue_count=1,
            issues=[],
        )

    monkeypatch.setattr(module, "datetime", FixedDateTime)
    monkeypatch.setattr(module, "get_twitter_threads", fake_get_twitter_threads)
    monkeypatch.setattr(module, "run_digest_pipeline", fake_run_digest_pipeline)

    exit_code = module.main(
        [
            "--output-file",
            str(output_path),
            "--hours",
            "6",
        ]
    )

    assert exit_code == 0
    assert calls["fetch"] == {
        "handles_path": module.PROJECT_ROOT / "data" / "handles.json",
        "since_date": expected_since_date,
    }
    assert calls["pipeline"] == {
        "threads": fetched_threads,
        "output_file": output_path,
        "model": module.DEFAULT_MODEL,
    }
    assert capsys.readouterr().out.strip() == f"Wrote 1 issues to {output_path}."
