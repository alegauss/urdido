"""VM39: QA measures encoded media and cannot preserve a stale report after failure."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from videomaker import qa


def test_opening_reports_cadence_and_repeats_separately_vm39():
    data = qa.opening_frames("#tb 0: 1/30\n0,0,0,1,2,aaa\n0,1,1,1,2,aaa\n0,3,3,1,2,bbb\n")
    assert data["decoded_frames"] == 3
    assert data["intervals"] == [0.033333333, 0.066666667]
    assert data["identical_frame_runs"] == [{"from": 0, "to": 1 / 30, "frames": 2}]
    with pytest.raises(RuntimeError, match="no time base"):
        qa.opening_frames("")


@pytest.fixture
def movie(tmp_path):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg and ffprobe are required")
    file = tmp_path / "cut.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=red:s=64x64:r=30:d=1",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "libx264",
                    "-c:a", "aac", "-shortest", str(file)], check=True)
    return file


def test_report_uses_actual_video_and_binds_its_image_vm39(movie):
    text = movie.with_suffix(".srt")
    text.write_text("Verificação em português", encoding="utf-8")
    edit = {"beats": [{"seconds": 1, "static": True, "asset": "original"}]}
    data = json.loads(qa.report(movie, edit=edit, text_files=[text]).read_text(encoding="utf-8"))
    assert data["sha256"] == qa.sha256(movie)
    assert data["first_frame"]["video_sha256"] == data["sha256"]
    assert data["first_frame"]["sha256"] == qa.sha256(movie.with_suffix(".first.png"))
    assert 0.9 <= data["duration"] <= 1.2
    assert {s["codec_type"] for s in data["streams"]} == {"audio", "video"}
    assert float(data["loudness"][0]["measurement"]["input_i"]) < 0
    assert data["opening"]["decoded_frames"] == 30
    assert data["editorial"] == {"shots": 1, "assets": 1, "source_files": 1, "static_seconds": 1, "highlights": 0}
    assert data["texts"][0]["utf8"] is True


def test_invalid_utf8_clears_stale_report_and_preview_vm39(movie):
    qa.report(movie)
    text = movie.with_suffix(".srt")
    text.write_bytes(b"\xff")
    with pytest.raises(UnicodeDecodeError):
        qa.report(movie, text_files=[text])
    assert not movie.with_suffix(".qa.json").exists()
    assert not movie.with_suffix(".first.png").exists()


def test_editorial_counts_shared_source_once_vm39():
    edit = {"beats": [{"asset": "a", "seconds": 2, "static": False},
                      {"asset": "b", "seconds": 1, "static": True}]}
    assets = {"a": {"file": "same.mp4"}, "b": {"file": "same.mp4"}}
    data = qa.editorial(edit, {"lines": {"intro": [{"show": "one"}]}}, assets)
    assert data == {"shots": 2, "assets": 2, "source_files": 1, "static_seconds": 1, "highlights": 1}


def test_changed_output_is_refused_vm39(movie, monkeypatch):
    actual = qa.sha256
    calls = 0

    def changed(path):
        nonlocal calls
        if path == movie:
            calls += 1
            if calls > 1:
                return "changed"
        return actual(path)

    monkeypatch.setattr(qa, "sha256", changed)
    with pytest.raises(RuntimeError, match="changed during measurement"):
        qa.report(movie)
    assert not movie.with_suffix(".qa.json").exists()


def test_build_loads_illustrated_edit_report_vm66(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from videomaker.build import Build

    (tmp_path / "video.toml").write_text(
        '[video]\nname="test"\nlanguages={en="eng"}\n'
        '[source]\ndeclaration="storyboard.json"\n'
        '[narration]\nscript="script.json"\n', encoding="utf-8")
    (tmp_path / "script.json").write_text('{}', encoding="utf-8")
    (tmp_path / "storyboard.json").write_text('{"media":{}}', encoding="utf-8")
    monkeypatch.setenv("STORY_VIDEO_DIR", str(tmp_path / "video"))
    build = Build(tmp_path / "video.toml", SimpleNamespace(language="en"))
    folder = build.parts / "illustrated"
    folder.mkdir()
    edit = {"beats": [{"asset": "clip", "static": False, "seconds": 2}]}
    (folder / "edit.json").write_text(json.dumps(edit), encoding="utf-8")
    file = build.out / "test.en.mp4"
    captions = file.with_suffix(".srt")
    captions.write_text("Captions", encoding="utf-8")
    seen = {}

    def capture(output, **kwargs):
        seen.update(kwargs)
        assert output == str(file)

    monkeypatch.setattr(qa, "report", capture)
    assert build.checked_output(str(file), illustrated=True) == str(file)
    assert seen["edit"] == edit
    assert captions in seen["text_files"]
    assert seen["peak_ceiling"] == -1.0


def test_encoded_true_peak_is_enforced_and_failed_report_is_removed_vm47(movie):
    data = json.loads(qa.report(movie, peak_ceiling=0).read_text(encoding="utf-8"))
    measured = float(data["loudness"][0]["measurement"]["input_tp"])
    assert measured <= data["peak_ceiling"] == 0
    with pytest.raises(RuntimeError, match="encoded true peak.*increase.*margin"):
        qa.report(movie, peak_ceiling=measured - 0.5)
    assert not movie.with_suffix(".qa.json").exists()
    assert not movie.with_suffix(".first.png").exists()


def test_every_audio_stream_is_checked_and_silence_is_valid_vm47():
    levels = [{"stream": 1, "language": "por", "measurement": {"input_tp": "-3.00"}},
              {"stream": 2, "language": "eng", "measurement": {"input_tp": "-0.87"}}]
    with pytest.raises(RuntimeError, match=r"stream 2 \(eng\).*-0.87.*-2.00"):
        qa.check_true_peak(levels, -2)
    qa.check_true_peak([{"stream": 1, "measurement": {"input_tp": "-inf"}}], -2)
    with pytest.raises(RuntimeError, match="valid encoded true-peak"):
        qa.check_true_peak([{"stream": 1, "measurement": {"input_tp": "NaN"}}], -2)
    with pytest.raises(ValueError, match="finite"):
        qa.check_true_peak([], float("nan"))
