"""A video filmed scene by scene assembles with every line over its own scene (VM10).

The promo's own scenes are checked in marketing, beside it (UR39).
"""

import json
from pathlib import Path

import pytest

from urdido.assemble.scenes import ScenesVideo
from urdido.edit.pacing import fit_to_line
from urdido.sources import RecordingRefused
from urdido.sources.scenes import scene_clips


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_fit_holds_a_short_clip_and_speeds_a_long_one():
    short = fit_to_line(6.0, 10.0)
    assert (short.speed, short.hold) == (1.0, 4.0)
    assert short.length(6.0) == 10.0
    long = fit_to_line(30.0, 12.0)
    assert long.speed == 2.5 and long.hold == 0.0
    assert long.length(30.0) == pytest.approx(12.0)


def test_a_listed_clip_missing_from_disk_is_refused(tmp_path):
    (tmp_path / "pt").mkdir()
    cenas = tmp_path / "pt" / "cenas.json"
    cenas.write_text(json.dumps({"scenes": [{"scene": "intro", "file": "pt/intro.webm", "seconds": 3}]}),
                     encoding="utf-8")
    with pytest.raises(RecordingRefused, match="not on disk"):
        scene_clips(str(cenas))






def assert_every_line_over_its_scene(video: ScenesVideo, tolerance: float = 0.0):
    assert video.placed
    for scene, kind, start, length, takes in video.placed:
        assert kind == ("scene" if scene.filmed else "card"), scene.name
        assert takes, f"{scene.name}: no current take"
        first, last = takes[0], takes[-1]
        heard_from = start + video.voice_lead
        heard_until = heard_from + sum(t.length for t in takes) + video.line_gap * (len(takes) - 1)
        assert start <= heard_from and heard_until <= start + length + tolerance, scene.name








