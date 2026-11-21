"""A scene video's contact sheet, each moment found from its takes (UR12)."""

import json
import shutil
import subprocess

import pytest

from urdido.review import scene_moments, scene_sheet

SCRIPT = {
    "introTitle": {"pt-BR": "Abertura"},
    "chapters": {
        "1": {"title": {"pt-BR": "Instalar"}},
        "2": {"title": {"pt-BR": "Buscar"}},
    },
}
PLACED = [
    {"file": "t/intro.mp3", "at": 0.5, "length": 2.0, "text": "O Shio em minutos."},
    {"file": "t/chapter-1.mp3", "at": 4.0, "length": 2.0, "text": "Instale o plugin."},
    {"file": "t/chapter-2.mp3", "at": 10.0, "length": 2.0, "text": "Busque no site."},
    {"file": "t/outro.mp3", "at": 16.0, "length": 2.0, "text": "Até logo."},
]


def test_the_moments_come_from_the_takes_not_a_hand_picked_second():
    moments = scene_moments(PLACED, SCRIPT, "pt-BR", 20.0)
    assert [(m["label"], m["at"]) for m in moments] == [
        ("cold open", 2.0),
        ("chapter 1 start", 4.5),
        ("chapter 1 middle", 7.0),
        ("chapter 1 end", 9.5),
        ("chapter 2 start", 10.5),
        ("chapter 2 middle", 13.0),
        ("chapter 2 end", 15.5),
        ("closing card", 19.5),
    ]
    assert moments[1]["title"] == "Instalar"
    assert moments[1]["spoken"] == "Instale o plugin."
    assert moments[0]["title"] == "Abertura"


def test_a_moment_never_falls_past_the_end_of_the_video():
    moments = scene_moments(PLACED[:2], SCRIPT, "pt-BR", 5.0)
    assert all(m["at"] < 5.0 for m in moments)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not on PATH")
def test_the_sheet_holds_each_moment_and_the_thumbnail_at_feed_sizes(tmp_path):
    video = tmp_path / "promo.pt-BR.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=s=320x180:r=10:d=20",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    thumbnail = tmp_path / "thumbnail.jpg"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:s=1280x720",
            "-frames:v",
            "1",
            str(thumbnail),
        ],
        check=True,
    )
    page = scene_sheet(video, PLACED, SCRIPT, "pt-BR", tmp_path, thumbnail)
    data = json.loads((tmp_path / "review" / "scenes.json").read_text(encoding="utf-8"))
    assert len(data["moments"]) == 8
    assert all((tmp_path / "review" / m["image"]).is_file() for m in data["moments"])
    assert data["thumbnail"] == ["thumbnail-320x180.png", "thumbnail-168x94.png"]
    assert "chapter 2 middle" in page.read_text(encoding="utf-8")
