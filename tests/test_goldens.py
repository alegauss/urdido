"""VM1's goldens load as data: the oracle every Python port is compared against (VM23)."""

import json
from pathlib import Path

import pytest

FIXTURES = sorted((Path(__file__).parent / "fixtures" / "recordings").glob("*.json"))


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.stem)
def test_recording_fixture_loads(fixture):
    data = json.loads(fixture.read_text(encoding="utf-8"))
    assert data["chapters"]
    for chapter in data["chapters"]:
        assert chapter["end"] > chapter["start"]
