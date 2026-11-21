"""VM63: flushed progress, parallel units, cache reuse and failure records."""
import io
import json
import threading
import time

import pytest

from test_preflight import cut  # noqa: F401  (the preflight fixture)
from urdido import cache, media, progress


def rows(file):
    return [json.loads(line) for line in file.read_text("utf-8").splitlines()]


def test_stage_start_is_flushed_before_hashing_and_cache_hits_are_counted(tmp_path, monkeypatch):
    report = tmp_path / "progress.jsonl"
    out = tmp_path / "result.png"
    actual = cache.Session.key
    def key(self, *args, **kwargs):
        assert rows(report)[-1]["event"] in {"started", "cache"}
        assert any(r["stage"] == "raster" and r["event"] == "started" for r in rows(report))
        return actual(self, *args, **kwargs)
    monkeypatch.setattr(cache.Session, "key", key)
    for hit in (False, True):
        with progress.configured(report, mode="off"), cache.configured(tmp_path / "cache.json"):
            progress.plan("raster", 1)
            cache.run("raster", [out], {}, lambda: out.write_bytes(b"png"))
        events = rows(report)
        assert next(e["hit"] for e in events if e["event"] == "cache") is hit
        assert events[-1]["counts"]["raster"]["completed"] == 1
        assert events[-1]["counts"]["raster"]["cache_hits"] == int(hit)
        assert events[-1]["pending"] == []


def test_failure_retains_last_success_and_pending_counts_without_exception_secrets(tmp_path):
    file = tmp_path / "progress.jsonl"
    with pytest.raises(RuntimeError):
        with progress.configured(file, mode="off"):
            progress.plan("source clips", 3)
            progress.run("source clips", "intro-0", lambda: None)
            with progress.unit("source clips", "intro-1"):
                raise RuntimeError("credential=secret encoder-command " * 1000)
    events = rows(file)
    assert events[-1]["event"] == "failed"
    assert events[-1]["last_success"] == {"stage": "source clips", "subject": "intro-0"}
    assert events[-1]["pending"] == ["source clips"]
    failed = next(e for e in events if e["event"] == "failed" and e["stage"] == "source clips")
    assert failed["subject"] == "intro-1" and failed["error_type"] == "RuntimeError"
    assert "credential" not in file.read_text()
    assert progress.CURRENT.get() is None and progress.UNIT.get() is None


def test_parallel_work_emits_heartbeats_and_valid_ordered_json_lines(tmp_path):
    report = tmp_path / "progress.jsonl"
    stream = io.StringIO()
    ready = threading.Event()
    with progress.configured(report, stream=stream, heartbeat=.01) as session:
        progress.plan("source clips", 3)
        def job(index):
            with progress.unit("source clips", f"beat-{index}"):
                ready.set()
                deadline = time.monotonic() + 2
                while not any(e["event"] == "heartbeat" for e in session.events):
                    assert time.monotonic() < deadline
                    session.stop.wait(.005)
        media.pool([lambda n=n: job(n) for n in range(3)], limit=3)
    events = rows(report)
    assert ready.is_set() and any(e["event"] == "heartbeat" and e["active"] for e in events)
    assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
    assert events[-1]["counts"]["source clips"]["completed"] == 3
    assert "source clips" in stream.getvalue()
    assert not session.thread.is_alive()


def test_json_stdout_is_parseable_and_normal_output_moves_to_stderr(tmp_path, capsys):
    with progress.configured(tmp_path / "progress.jsonl", mode="json"):
        print("normal build path")
        progress.run("verification", "movie.mp4", lambda: None)
    captured = capsys.readouterr()
    events = [json.loads(line) for line in captured.out.splitlines()]
    assert events[-1]["event"] == "finished"
    assert "normal build path" in captured.err


def test_cli_cards_and_failure_write_progress_but_do_not_claim_video_was_encoded(cut, capsys):
    from urdido.build import main
    from urdido.preflight import PreflightRefused

    with pytest.warns(UserWarning):
        assert main([str(cut.declaration), "--language", "en", "--cards", "--progress", "json"]) == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert any(e["stage"] == "validation" and e["event"] == "finished" for e in events)
    assert events[-1]["event"] == "finished" and events[-1]["pending"] == []
    assert "mux" in events[-1]["not_observed"]
    cut.story["scenes"]["intro"][0]["caption"] = "Uma hist?ria"
    cut.write("story.json", cut.story)
    with pytest.raises(PreflightRefused):
        main([str(cut.declaration), "--language", "en", "--plan", "--progress", "off"])
    events = rows(cut.folder / "video/parts/progress.en.jsonl")
    assert events[-1]["event"] == "failed" and "validation" in events[-1]["pending"]
