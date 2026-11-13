import hashlib
import json

import pytest

from videomaker.keywords import cues
from videomaker.sources.model import RecordingRefused


def fixture(tmp_path):
    take = tmp_path / "intro.mp3"
    take.write_bytes(b"current spoken take")
    take.with_suffix(".words.json").write_text(json.dumps({
        "sha256": hashlib.sha256(take.read_bytes()).hexdigest(),
        "words": [{"text": "Em", "start": 0, "end": 0.2},
                  {"text": "2003,", "start": 0.3, "end": 0.7},
                  {"text": "Mike", "start": 1.0, "end": 1.3},
                  {"text": "Little", "start": 1.4, "end": 1.7}],
    }), encoding="utf-8")
    return take, [{"file": str(take), "at": 10, "length": 4}]


def test_names_and_dates_follow_the_spoken_word_not_the_shot_boundary(tmp_path):
    _, placed = fixture(tmp_path)
    timed = cues(placed, {"intro": [{"show": "2003"}, {"show": "Mike Little"}]})
    assert [c["at"] for c in timed] == [10.3, 11.0]
    assert timed[0]["end"] == pytest.approx(10.92)
    assert timed[1]["end"] == pytest.approx(13.8)


def test_replaced_audio_refuses_stale_word_times(tmp_path):
    take, placed = fixture(tmp_path)
    take.write_bytes(b"replacement take")
    with pytest.raises(RecordingRefused, match="stale word times"):
        cues(placed, {"intro": [{"show": "Mike Little"}]})


def test_missing_name_does_not_get_a_guessed_time(tmp_path):
    _, placed = fixture(tmp_path)
    with pytest.raises(RecordingRefused, match="not heard"):
        cues(placed, {"intro": [{"show": "Matt Mullenweg"}]})
