"""An explainer renders end to end from its declaration (UR4), on generated media."""

import json
import shutil
import subprocess

import pytest

from urdido import cache
from urdido.pipelines import explainer

pytestmark = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg is not here",
)


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def project(folder):
    script = {
        "voice": "v",
        "model": "m",
        "intro": {"pt-BR": "Olá Git."},
        "chapters": {},
        "outro": {"pt-BR": "Tchau."},
    }
    (folder / "script.json").write_text(json.dumps(script), encoding="utf-8")
    takes = folder / "narration" / "pt-BR"
    takes.mkdir(parents=True)
    for name, seconds in (("intro", 1.6), ("outro", 1.2)):
        take = takes / f"{name}.mp3"
        ffmpeg("-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", str(take))
        words = [
            {"text": "Olá", "start": 0.1, "end": 0.4},
            {"text": "Git", "start": 0.5, "end": 0.9},
        ]
        take.with_suffix(".words.json").write_text(
            json.dumps({"sha256": cache.file_hash(take), "words": words}),
            encoding="utf-8",
        )
    (folder / "footage" / "src").mkdir(parents=True)
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=640x480:rate=30:duration=8",
        "-pix_fmt",
        "yuv420p",
        str(folder / "footage" / "src" / "a.mp4"),
    )
    shots = {
        "title": "Fixture: an explainer",
        "segments": [
            {"take": "intro", "shots": [{"src": "a", "at": 0}]},
            {"take": "outro", "shots": [{"src": "a", "at": 3}]},
        ],
        "callouts": {"intro": [{"show": "Git", "def": "version control"}]},
    }
    (folder / "shots.json").write_text(json.dumps(shots), encoding="utf-8")
    toml = folder / "video.toml"
    toml.write_text(
        '[video]\nname = "demo"\nlanguages = { "pt-BR" = "por" }\n'
        '[source]\nkind = "explainer"\nshots = "shots.json"\nend = 1.5\n'
        '[source.closing.pt-BR]\ntitle = "Até a próxima!"\n'
        '[narration]\nscript = "script.json"\ntakes = "narration"\n'
        "[audio]\npeak = -1.0\n",
        encoding="utf-8",
    )
    return toml


def test_an_explainer_renders_with_titles_callouts_captions_and_mix(
    tmp_path, monkeypatch
):
    from urdido.build import main

    monkeypatch.delenv("STORY_VIDEO_DIR", raising=False)
    toml = project(tmp_path)
    assert main([str(toml), "--language", "pt-BR"]) == 0
    video = tmp_path / "video" / "demo.pt-BR.mp4"
    probe = json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(video),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    kinds = sorted(s["codec_type"] for s in probe["streams"])
    assert kinds == ["audio", "video"]
    assert float(probe["format"]["duration"]) == pytest.approx(
        0.4 + 1.6 + 0.5 + 1.2 + 1.5, abs=0.15
    )
    srt = (tmp_path / "video" / "demo.pt-BR.srt").read_text(encoding="utf-8")
    assert "Olá Git." in srt and "Tchau." in srt
    ass = (tmp_path / "video" / "parts" / "explainer" / "titles.ass").read_text("utf-8")
    assert "Fixture" in ass and "an explainer" in ass and "Até a próxima!" in ass
    assert "version control" in ass
    assert (tmp_path / "video" / "demo.pt-BR.qa.json").exists()


def test_the_titles_follow_the_plan_and_the_declared_closing():
    made = {
        "title": "One: two",
        "length": 10.0,
        "callouts": [[1.0, 3.0, "Git", ""], [4.0, 6.0, "Scion", "a cache"]],
    }
    ass = explainer.titles(made, explainer.DEFAULT_STYLES, {"sub": "Bye"}, end=2.0)
    assert ",Title,,0,0,0,,{\\fad(400,500)\\pos(960,450)}One" in ass
    assert (
        "\\pos(960,968)" in ass and "\\pos(960,900)" in ass
    )  # a defined word sits higher
    assert "0:00:08.50,0:00:10.00,Sub" in ass and "Bye" in ass
