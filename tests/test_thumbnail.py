"""A thumbnail's pictures are crops of the video's own sources, declared by box (VM51)."""
import pytest

from videomaker.thumbnail import crop_filter


def test_a_box_of_fractions_becomes_an_ffmpeg_crop():
    assert crop_filter([0.25, 0.0, 0.75, 0.5]) == "crop=iw*0.5000:ih*0.5000:iw*0.2500:ih*0.0000"


def test_a_box_outside_the_frame_is_refused():
    with pytest.raises(ValueError, match="between 0 and 1"):
        crop_filter([0.5, 0.0, 0.4, 1.0])
