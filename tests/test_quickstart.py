"""The quickstart builds the first video from generated media alone (UR35)."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "first-video"


@pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg is not on PATH",
)
def test_the_first_video_builds_as_the_quickstart_says(tmp_path, monkeypatch):
    from urdido.build import main
    from urdido.declaration import main as check

    monkeypatch.delenv("STORY_VIDEO_DIR", raising=False)
    folder = tmp_path / "first-video"
    shutil.copytree(
        EXAMPLE, folder, ignore=shutil.ignore_patterns("video", "narration", "footage")
    )
    spec = importlib.util.spec_from_file_location(
        "make_media", folder / "make_media.py"
    )
    make_media = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(make_media)
    assert make_media.main(folder) == 0
    assert check([str(folder / "video.toml")]) == 0
    assert main([str(folder / "video.toml"), "--language", "en"]) == 0
    out = folder / "video"
    for name in ("first-video.en.mp4", "first-video.en.srt", "first-video.en.qa.json"):
        assert (out / name).is_file(), name
    probe = json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-of",
                "json",
                str(out / "first-video.en.mp4"),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    assert float(probe["format"]["duration"]) > 6


def test_the_quickstart_names_the_files_the_example_has():
    guide = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")
    for name in ("make_media.py", "video.toml", "script.json", "shots.json"):
        assert (EXAMPLE / name).is_file(), name
        assert name in guide, name
