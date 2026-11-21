"""VM62: continuous interaction, internal freezes and explicit cursor policy."""
import subprocess

import pytest

from test_preflight import cut  # noqa: F401  (the preflight fixture)
from urdido import cache, pauses
from urdido.sources.illustrated import beat_frames
from urdido.sources.model import RecordingRefused


def test_active_drag_longer_than_card_cap_is_not_a_pause():
    spec = pauses.settings({"sample_fps": 5})
    frames = [bytes([0] * i + [255] * 20 + [0] * (100 - i)) for i in range(50)]
    assert pauses.intervals(frames, 10, spec)["intervals"] == []
    assert beat_frames([{"title": "Drag", "layout": "footage"}], 300, 3) == [300]
    for layout in ("date", "picture"):
        with pytest.raises(RecordingRefused, match="exceeds"):
            beat_frames([{"title": "Still", "layout": layout, "static": False}], 300, 3)


def test_frozen_stretch_inside_moving_clip_and_trailing_hold_are_measured():
    spec = pauses.settings({"sample_fps": 2})
    frames = [bytes([v] * 100) for v in [0, 50, 100, 100, 100, 100, 100, 100, 150, 200, 200, 200]]
    result = pauses.intervals(frames, 6, spec)
    assert result["intervals"] == [{"start": 1, "end": 3.5, "seconds": 2.5}, {"start": 4.5, "end": 6, "seconds": 1.5}]


def test_cursor_sized_motion_is_explicitly_counted_or_ignored():
    frames = [bytes([0] * i + [255] + [0] * (999 - i)) for i in range(20)]
    spec = pauses.settings({"sample_fps": 5, "min_changed_share": .01})
    assert pauses.intervals(frames, 4, spec)["longest_seconds"] == 4
    assert pauses.intervals(frames, 4, {**spec, "cursor_motion": "count"})["longest_seconds"] == 0
    with pytest.raises(RecordingRefused, match="too few"):
        pauses.intervals([bytes(100)], 10, spec)


def test_actual_decoder_accepts_continuous_drag_and_finds_internal_freeze(tmp_path):
    width, height, fps = 64, 36, 10
    def frame(x):
        return bytes(255 if x <= col < x + 12 else 0 for row in range(height) for col in range(width))
    frames = [frame(i % 40) for i in range(80)]
    file = tmp_path / "drag.mp4"
    def encode():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", "64x36",
                        "-r", str(fps), "-i", "pipe:0", "-c:v", "libx264", "-crf", "0", str(file)],
                       input=b"".join(frames), check=True, capture_output=True)
    encode()
    spec = pauses.settings({"width": width, "height": height, "sample_fps": fps})
    assert pauses.measure(file, 0, 8, spec)["longest_seconds"] == 0
    frames[20:60] = [frame(20)] * 40
    encode()
    result = pauses.measure(file, 1, 6, spec)
    assert result["sha256"] == cache.file_hash(file)
    assert 3.8 <= result["longest_seconds"] <= 4.1
    assert result["intervals"][0]["start"] == pytest.approx(1, abs=.1)


def document(tmp_path):
    file = tmp_path / "screen.mp4"
    file.write_bytes(b"recording")
    return {"pauses": {"action": "error"}, "media": {"screen": {"file": file.name, "screen_recording": True}},
            "scenes": {"intro": [{"id": "drag", "layout": "footage", "asset": "screen", "at": 7}]}}, \
           {"beats": [{"beat": "intro-0", "at": 5, "seconds": 10}]}


def measured(file, *args):
    return {"samples": 50, "sha256": cache.file_hash(file), "longest_seconds": 4,
            "intervals": [{"start": 2, "end": 6, "seconds": 4}]}


def test_source_and_cut_intervals_and_reviewed_holds_bind_to_source_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(pauses, "measure", measured)
    story, edit = document(tmp_path)
    report = pauses.inspect(story, edit, tmp_path, opening=3)
    finding = report["findings"][0]
    assert (finding["source_start"], finding["source_end"]) == (9, 13)
    assert (finding["timeline_start"], finding["timeline_end"]) == (10, 14)
    with pytest.raises(RecordingRefused, match=r"source 9.000..13.000s; timeline 10.000..14.000s"):
        pauses.enforce(report)
    story["pauses"]["exceptions"] = [{"beat": "drag", "start": 9, "end": 13, "reviewer": "Owner",
                                        "date": "2026-11-14", "reason": "Deliberate result review", "sha256": finding["sha256"]}]
    pauses.enforce(pauses.inspect(story, edit, tmp_path, 3))
    (tmp_path / "screen.mp4").write_bytes(b"changed")
    with pytest.raises(RecordingRefused):
        pauses.enforce(pauses.inspect(story, edit, tmp_path, 3))
    story["pauses"]["exceptions"][0]["reviewer"] = ""
    with pytest.raises(ValueError, match="reviewer"):
        pauses.inspect(story, edit, tmp_path)


def test_unconfigured_or_non_screen_media_is_never_measured(tmp_path, monkeypatch):
    monkeypatch.setattr(pauses, "measure", lambda *args: pytest.fail("undeclared media measured"))
    story, edit = document(tmp_path)
    story.pop("pauses")
    assert pauses.inspect(story, edit, tmp_path)["shots"] == []
    story["pauses"] = {"action": "warn"}
    story["media"]["screen"]["screen_recording"] = False
    assert pauses.inspect(story, edit, tmp_path)["shots"] == []


@pytest.mark.parametrize("field,value", [("sample_fps", 0), ("pixel_delta", 2.5), ("cursor_motion", "detect"),
                                        ("min_changed_share", float("nan")), ("all_footage", "yes")])
def test_invalid_measurement_settings_are_refused(field, value):
    with pytest.raises(ValueError):
        pauses.settings({field: value})


def test_pause_failure_precedes_card_rasterization_and_encoding(cut, monkeypatch):
    from urdido import media
    from urdido.build import main
    from urdido.preflight import PreflightRefused

    (cut.folder / "screen.mp4").write_bytes(b"recording")
    cut.story["media"] = {"screen": {"file": "screen.mp4", "license": "Own", "author": "Fixture",
                                     "url": "https://example.org", "screen_recording": True}}
    cut.story["scenes"]["intro"][0].update(layout="footage", asset="screen", at=0)
    cut.story["pauses"] = {"action": "error", "max_pause_seconds": 1}
    cut.write("story.json", cut.story)
    monkeypatch.setattr(pauses, "measure", measured)
    monkeypatch.setattr(media, "seconds", lambda file: 10 if str(file).endswith("screen.mp4") else 3)
    with pytest.raises(PreflightRefused) as failure:
        main([str(cut.declaration), "--language", "en", "--plan"])
    assert any(f["field"] == "pauses" and "timeline" in f["message"] for f in failure.value.findings)
    assert not (cut.folder / "video/parts/illustrated").exists()
