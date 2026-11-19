import hashlib
import json

import pytest

from urdido.keywords import cues
from urdido.keywords import write_ass
from urdido.keywords import anchor
from urdido.sources.model import RecordingRefused


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


def test_highlights_can_be_lifted_above_the_player_captions(tmp_path):
    style = {"font": "F", "color": "#2BCB6B"}
    write_ass(tmp_path / "a.ass", [], style)
    assert ",2,130,130,85,1" in (tmp_path / "a.ass").read_text("utf-8")
    write_ass(tmp_path / "b.ass", [], {**style, "margin": 260})
    assert ",2,130,130,260,1" in (tmp_path / "b.ass").read_text("utf-8")


def test_missing_name_does_not_get_a_guessed_time(tmp_path):
    _, placed = fixture(tmp_path)
    with pytest.raises(RecordingRefused, match="not heard"):
        cues(placed, {"intro": [{"show": "Matt Mullenweg"}]})


def test_word_anchor_resolves_context_and_occurrence_without_guessing_vm42(tmp_path):
    take, _ = fixture(tmp_path)
    path = take.with_suffix(".words.json")
    data = json.loads(path.read_text())
    data["words"] += [{"text": "Mike", "start": 2, "end": 2.2},
                      {"text": "again", "start": 2.3, "end": 2.7}]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RecordingRefused, match="2 matches"):
        anchor(take, "Mike")
    assert anchor(take, {"text": "Mike", "occurrence": 2}) == 2
    assert anchor(take, {"text": "Mike", "context": "Mike Little"}) == 1
    with pytest.raises(RecordingRefused, match="0 matches"):
        anchor(take, "Gutenberg")
    with pytest.raises(RecordingRefused, match="positive integer"):
        anchor(take, {"text": "Mike", "occurrence": 0})


def test_word_anchor_rejects_stale_transcript_vm42(tmp_path):
    take, _ = fixture(tmp_path)
    take.write_bytes(b"retake")
    with pytest.raises(RecordingRefused, match="stale"):
        anchor(take, "Mike Little")
