"""VM78: a take's scene may pause after its line, and a footage beat may play its own sound."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from videomaker.build import Build
from videomaker.sources.illustrated import paced, scene_frames
from videomaker.sources.model import RecordingRefused


def test_a_pause_lengthens_only_its_own_take():
    document = {"pauses": {"intro": 1.5}}
    assert scene_frames(document, "intro", 4.0) == 192   # (0.4 + 4 + 0.5 + 1.5) * 30
    assert scene_frames(document, "outro", 4.0) == 147   # no pause declared
    assert scene_frames({}, "intro", 4.0) == 147


def test_a_bad_pause_is_refused():
    for bad in (-1, "2", True):
        with pytest.raises(RecordingRefused, match="pause"):
            scene_frames({"pauses": {"intro": bad}}, "intro", 4.0)


def test_a_beat_with_its_own_sound_keeps_its_real_seconds_under_a_tempo():
    beats = [{"seconds": 2.4}, {"seconds": 2.4, "sound": True}]
    assert [b["seconds"] for b in paced(beats, 1.2)] == [2.0, 2.4]


def test_the_mix_hears_each_sounding_beat_where_it_sits(tmp_path):
    parts = tmp_path / "parts"
    (parts / "illustrated").mkdir(parents=True)
    (parts / "illustrated" / "edit.json").write_text(json.dumps({"beats": [
        {"beat": "intro-0", "at": 0.0, "seconds": 3.0},
        {"beat": "intro-1", "at": 3.0, "seconds": 1.6, "sound": {"file": "meme.mp4", "source_at": 2.0}},
    ]}), "utf-8")
    sounds = Build.beat_sounds(SimpleNamespace(parts=parts), opening=1.0)
    assert len(sounds) == 1
    sound = sounds[0]
    assert (sound.file, sound.source_at, sound.at, sound.length) == ("meme.mp4", 2.0, 4.0, 1.6)


def test_a_loud_clip_can_be_brought_down_in_the_mix():
    from videomaker.audio.mix import Sound, mix_graph
    from videomaker.sources.illustrated import sound_gain

    assert sound_gain({"sound": True}) == 0.0
    assert sound_gain({"sound": {"gain_db": -6}}) == -6.0
    for bad in ({"gain_db": "loud"}, {"volume": 1}, {"gain_db": -99}):
        with pytest.raises(RecordingRefused):
            sound_gain({"sound": bad})
    graph = mix_graph([], 10.0, [Sound("meme.mp4", 0.0, 2.0, 1.5, -6.0)]).filter_complex
    assert "volume=-6dB,afade" in graph


def test_a_video_without_an_illustrated_edit_has_no_beat_sounds(tmp_path):
    assert Build.beat_sounds(SimpleNamespace(parts=Path(tmp_path)), opening=0) == []
