"""UR70: a chaptered video's cold open, cut from its own recording."""

from types import SimpleNamespace

import pytest

from urdido.assemble.video import FullVideo


def chapter(start, end, highlight=None):
    return SimpleNamespace(
        clip=SimpleNamespace(start=start, end=end),
        marks=SimpleNamespace(highlight=highlight),
    )


def video(cold_open):
    made = object.__new__(FullVideo)
    made.chapters = [chapter(10.0, 40.0, highlight=30.0), chapter(40.0, 60.0)]
    made.cold_open = cold_open
    made.shot_seconds = 4
    return made


def test_a_moment_ends_just_past_the_chapters_best_moment():
    moments = video([{"chapter": 1, "seconds": 5}, {"chapter": 2}]).cold_moments()
    # chapter 1: its highlight at 30 s; chapter 2: no highlight, so 0.8 s before its end
    assert moments == [(1, 25.5, 30.5), (2, 55.7, 59.7)]


def test_a_moment_never_starts_before_its_chapter():
    assert video([{"chapter": 1, "seconds": 60}]).cold_moments() == [(1, 10.0, 30.5)]


@pytest.mark.parametrize(
    ("entry", "said"),
    [
        ({"chapter": 3}, "not one of 1 to 2"),
        ({"chapter": 1, "seconds": 0}, "positive seconds"),
    ],
)
def test_a_moment_outside_the_recording_is_refused(entry, said):
    with pytest.raises(ValueError, match=said):
        video([entry]).cold_moments()
