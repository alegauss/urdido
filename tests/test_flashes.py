"""A cut that flashes for a frame or two is refused by the final verification (UR14)."""

import shutil
import subprocess

import pytest

from urdido.qa import check_flashes, flashes, report

SIZE = 32 * 18


def grey(level: int, half: int | None = None) -> bytes:
    """A frame of one level, or with its right half at another."""
    if half is None:
        return bytes([level]) * SIZE
    row = bytes([level]) * 16 + bytes([half]) * 16
    return row * 18


def test_a_white_frame_between_dark_ones_is_a_flash():
    frames = [grey(30)] * 5 + [grey(234)] + [grey(32)] * 5
    assert flashes(frames, 30) == [
        {"at": 0.167, "frames": 1, "jump": 204.0, "back": 2.0}
    ]


def test_a_different_picture_of_the_same_brightness_is_a_flash_too():
    # the console's loading dashboard: luma 39 against 43, but another picture
    frames = [grey(43, 43)] * 4 + [grey(20, 58)] + [grey(43, 43)] * 4
    found = flashes(frames, 30)
    assert [f["frames"] for f in found] == [1]


def test_two_frames_that_come_back_are_a_flash_and_a_cut_is_not():
    two = [grey(30)] * 4 + [grey(200)] * 2 + [grey(30)] * 4
    assert flashes(two, 30)[0]["frames"] == 2
    cut = [grey(30)] * 4 + [grey(200)] * 6
    assert flashes(cut, 30) == []
    fade = [grey(30 + 3 * k) for k in range(40)]
    assert flashes(fade, 30) == []


def test_a_faint_flash_is_reported_and_a_strong_one_refused_ur45():
    # The published Docker cut holds a stock clip's one-frame light leak (jump 25.8); a
    # white page between dark frames jumps about 190.
    leak = [{"at": 257.367, "frames": 1, "jump": 25.8, "back": 6.4}]
    with pytest.warns(UserWarning, match="look at these frames"):
        check_flashes(leak, [], "error")  # reported, not refused
    white = [{"at": 40.667, "frames": 1, "jump": 190.0, "back": 3.0}]
    with pytest.raises(RuntimeError, match="the cut flashes"):
        check_flashes(white, [], "error")
    with pytest.raises(RuntimeError):
        check_flashes(leak, [], "error", refuse=20)  # a channel can be stricter


def test_a_flash_is_refused_naming_its_second_and_clip():
    found = [{"at": 40.667, "frames": 1, "jump": 190.0, "back": 3.0}]
    clips = [{"file": "parts/chapter-2.webm", "start": 38.0, "end": 60.0}]
    with pytest.raises(RuntimeError, match=r"40\.667 s .* in chapter-2\.webm"):
        check_flashes(found, clips, "error")
    with pytest.warns(UserWarning):
        check_flashes(found, clips, "warn")
    check_flashes(found, clips, "off")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not on PATH")
def test_the_verification_refuses_an_encoded_white_flash(tmp_path):
    dark = tmp_path / "dark.mp4"
    flashed = tmp_path / "flashed.mp4"
    base = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi"]
    subprocess.run(
        [
            *base,
            "-i",
            "color=c=0x202020:s=320x180:r=30:d=2",
            "-pix_fmt",
            "yuv420p",
            str(dark),
        ],
        check=True,
    )
    white = "drawbox=c=white:t=fill:enable='eq(n,30)'"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(dark), "-vf", white, str(flashed)],
        check=True,
    )
    report(dark)
    with pytest.raises(RuntimeError, match=r"flashes: 1\.000 s"):
        report(flashed)
