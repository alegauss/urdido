"""The timeline as OpenTimelineIO carries everything a plan says (VM7, first part).

Each golden plan is composed into an OTIO timeline through the builder, written as `.otio`, read
back, and `plan()` derives the plan from it, which must equal the golden one. The one field that
cannot round-trip exactly is `total`: the JS sums the pieces' unrounded lengths and the plan keeps
them rounded, so a timeline rebuilt from a plan sums rounded lengths. It is held to half a
millisecond per piece.
"""

import json
from pathlib import Path

from urdido import timeline as tl


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))






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
