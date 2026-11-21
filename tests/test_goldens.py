"""VM1's goldens load as data: the oracle every Python port is compared against (VM23)."""

import json
from pathlib import Path

import pytest
from marketing import GOLDEN, needs_marketing

PLANS = sorted((GOLDEN / "expected").glob("*/*.plan.json"))
FIXTURES = sorted((Path(__file__).parent / "fixtures" / "recordings").glob("*.json"))


@needs_marketing
def test_the_goldens_are_there():
    assert len(PLANS) >= 5
    assert len(FIXTURES) >= 3


@pytest.mark.parametrize("plan", PLANS, ids=lambda p: p.parent.name)
def test_plan_loads_with_its_captions(plan):
    data = json.loads(plan.read_text(encoding="utf-8"))
    assert {"video", "language", "size", "pieces"} <= data.keys()
    assert data["size"]["width"] > 0
    assert data["size"]["height"] > 0
    for piece in data["pieces"]:
        # every piece has a file and a length; placed ones also carry track and at
        assert {"file", "length"} <= piece.keys()
    # the captions a caption port is compared against sit beside the plan
    assert plan.with_name(f"{data['video']}.srt").exists()


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.stem)
def test_recording_fixture_loads(fixture):
    data = json.loads(fixture.read_text(encoding="utf-8"))
    assert data["chapters"]
    for chapter in data["chapters"]:
        assert chapter["end"] > chapter["start"]
