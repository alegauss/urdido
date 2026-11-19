"""The timeline as OpenTimelineIO carries everything a plan says (VM7, first part).

Each golden plan is composed into an OTIO timeline through the builder, written as `.otio`, read
back, and `plan()` derives the plan from it, which must equal the golden one. The one field that
cannot round-trip exactly is `total`: the JS sums the pieces' unrounded lengths and the plan keeps
them rounded, so a timeline rebuilt from a plan sums rounded lengths. It is held to half a
millisecond per piece.
"""

import json
from pathlib import Path

import opentimelineio as otio
import pytest

from urdido import timeline as tl
from golden_plans import main_plans
from marketing import GOLDEN, needs_marketing

GOLDEN = GOLDEN / "expected"
PLANS = main_plans(GOLDEN)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("plan_file", PLANS, ids=lambda p: p.parent.name)
def test_plan_round_trips_through_an_otio_file(plan_file, tmp_path):
    golden = load(plan_file)
    otio_file = tmp_path / f"{golden['video']}.otio"
    tl.write(tl.from_plan(golden), str(otio_file))
    back = tl.plan(tl.read(str(otio_file)))

    assert list(back) == list(golden)  # the keys, in writePlan's order
    if "total" in golden:
        assert abs(back.pop("total") - golden["total"]) <= 0.0005 * len(golden["pieces"])
        golden = {k: v for k, v in golden.items() if k != "total"}
    assert back == golden


@needs_marketing
def test_lanes_and_markers_are_otio():
    golden = load(GOLDEN / "story-pt-BR" / "story.pt-BR.plan.json")
    timeline = tl.from_plan(golden)
    names = [track.name for track in timeline.tracks]
    assert names[:3] == ["V1", "V2", "V3"]
    assert "A1 pt-BR" in names and "A3" in names
    clips = [c for track in timeline.video_tracks() for c in track if isinstance(c, otio.schema.Clip)]
    assert len(clips) == len(golden["pieces"])
    assert len(timeline.tracks.markers) == len(golden["cues"])
    # every track, picture and sound, ends where the video ends (OTIO sums each track's items in
    # its own order, so the ends agree to float precision rather than bit for bit)
    ends = [track.duration().to_seconds() for track in timeline.tracks]
    assert max(ends) - min(ends) < 1e-6
    assert max(ends) == pytest.approx(golden["total"], abs=0.01)


def test_a_piece_plays_where_the_last_ended():
    b = tl.Builder("v", "en", 1920, 1080)
    b.card("card-0.png", "card-0.mp4", 2.5)
    b.chapter("rec.webm", 10.0, 0, 0.0, "chapter-1.mp4", 20.0)
    b.card("card-1.png", "card-1.mp4", 2.5)
    v1, v2 = b.lanes["V1"], b.lanes["V2"]
    assert [type(i).__name__ for i in v1] == ["Gap", "Clip"]
    assert v1[0].duration().to_seconds() == 2.5
    assert [type(i).__name__ for i in v2] == ["Clip", "Gap", "Clip"]
    assert v2[1].duration().to_seconds() == 20.0
    assert v1[1].source_range.start_time.to_seconds() == 10.0
