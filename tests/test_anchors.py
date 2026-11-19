"""VM87: a scene's moments pinned to the words that say them."""

import json
import shutil
import subprocess

import pytest

from videomaker.edit.pacing import warp, warp_setpts


def test_each_moment_lands_on_its_word():
    points = warp(37.5, 18.3, [(15.2, 10.5, "console"), (8.1, 6.4, "setup")])
    assert points == [(0.0, 0.0), (8.1, 6.4), (15.2, 10.5), (37.5, 18.3)]


@pytest.mark.parametrize("pins, words", [
    ([(8.1, 6.4, "a"), (15.2, 5.0, "b")], "before the previous"),
    ([(40.0, 6.4, "a")], "outside the scene"),
    ([(8.1, 0.5, "a")], "would play at"),
    ([(30.0, 18.2, "a")], "would play at"),
])
def test_a_pin_the_edit_cannot_honour_refuses(pins, words):
    with pytest.raises(ValueError, match=words):
        warp(37.5, 18.3, pins)


def test_the_expression_is_the_points():
    expr = warp_setpts([(0.0, 0.0), (8.0, 4.0), (20.0, 10.0)])
    assert expr.startswith("setpts='(") and expr.endswith(")/TB'")
    assert "if(lt(T,8.0000),0.0000+(T-0.0000)*0.500000," in expr


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not on PATH")
def test_ffmpeg_plays_the_warp(tmp_path):
    # a 20 s clip whose second 8 must show at 2 s and its end at 10 s
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=64x36:rate=25:duration=20",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    out = tmp_path / "warped.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf",
                    warp_setpts([(0.0, 0.0), (8.0, 2.0), (20.0, 10.0)]) + ",fps=25", str(out)], check=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(out)],
                           capture_output=True, text=True, check=True)
    assert abs(float(json.loads(probe.stdout)["format"]["duration"]) - 10.0) < 0.2
