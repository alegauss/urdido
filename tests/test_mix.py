"""mix.py builds the ducking the goldens record, and mixes to the loudness target (VM5)."""

import json
from pathlib import Path

import pytest

from urdido.audio import mix as m


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def duck_of(music) -> m.Duck:
    return m.Duck(music["duck"]["between"], music["volume"], music["duck"]["ramp"])






def test_gain_follows_the_duck():
    takes = [m.Take("a", 10.0, 5.0)]
    duck = m.Duck(0.4, 0.2, 0.4)
    assert m.music_gain(takes, 0.0, duck) == pytest.approx(0.4)
    assert m.music_gain(takes, 9.8, duck) == pytest.approx(0.3)
    assert m.music_gain(takes, 12.0, duck) == pytest.approx(0.2)
    assert m.music_gain(takes, 16.0, duck) == pytest.approx(0.4)
    assert m.duck_expression([], duck) == "0.4-0.200*(0)"






def test_sounds_come_before_the_bed():
    built = m.mix_graph(
        [m.Take("take.mp3", 7.0, 3.0)],
        20.0,
        sounds=[m.Sound("intro.mp4", 3.45, 0.0, 6.566)],
        bed=m.Bed("bed.mp3", 6.566),
        trim_db=-5.28,
    )
    assert built.inputs[2:8] == ["-ss", "3.450", "-t", "6.566", "-i", "intro.mp4"]
    assert built.filters[1] == "[1:a]afade=t=out:st=5.966:d=0.6,adelay=0:all=1[s0]"
    assert "(t-0.034)" in built.filters[2]  # the take, in the bed's own time
    assert built.filters[2].endswith("adelay=6566:all=1[m]")
    assert built.filters[3].startswith("[d0][s0][m]amix=inputs=3")








def test_a_bed_ending_in_silence_loops_from_where_its_music_stops():
    log = ("[silencedetect] silence_start: 40.2\n[silencedetect] silence_end: 41.0 | silence_duration: 0.8\n"
           "[silencedetect] silence_start: 211.978\n[silencedetect] silence_end: 220.055 | silence_duration: 8.08\n")
    assert m.audible_end(log, 220.055) == pytest.approx(211.978)


def test_a_bed_without_a_silent_tail_keeps_its_whole_length():
    log = "[silencedetect] silence_start: 40.2\n[silencedetect] silence_end: 41.0 | silence_duration: 0.8\n"
    assert m.audible_end(log, 220.0) == 220.0
