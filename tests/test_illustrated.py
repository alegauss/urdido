"""Illustrated cuts must refuse an incomplete story instead of silently losing narration."""
from types import SimpleNamespace

import pytest

from videomaker.sources.illustrated import validate
from videomaker.sources.illustrated import beat_frames
from videomaker.sources.illustrated import description
from videomaker.sources.model import RecordingRefused


class Voices:
    lines = {"intro": {}, "outro": {}}

    def __init__(self, stale=None):
        self.stale = stale

    def takes(self, name, languages, current_language):
        return [] if name == self.stale else [SimpleNamespace(length=9)]


def story():
    beat = {"title": "A contribution", "source": "original"}
    return {"sources": {"original": {}}, "scenes": {"intro": [beat], "outro": [beat]}}


def test_a_stale_take_cannot_turn_a_narrated_scene_into_a_silent_card():
    with pytest.raises(RecordingRefused, match="outro: missing or stale narration"):
        validate(story(), Voices(stale="outro"), "pt-BR")


def test_missing_and_reordered_scenes_are_refused():
    document = story()
    document["scenes"].pop("outro")
    with pytest.raises(RecordingRefused, match="every narration take"):
        validate(document, Voices(), "pt-BR")
    document["scenes"] = dict(reversed(list(story()["scenes"].items())))
    with pytest.raises(RecordingRefused, match="script order"):
        validate(document, Voices(), "pt-BR")


def test_a_fact_without_its_declared_source_is_refused():
    document = story()
    document["sources"].clear()
    with pytest.raises(RecordingRefused, match="unknown source original"):
        validate(document, Voices(), "pt-BR")


def test_validated_order_and_voice_lengths_are_kept():
    rows = validate(story(), Voices(), "pt-BR")
    assert [(name, take.length) for name, beats, take in rows] == [("intro", 9), ("outro", 9)]


def test_a_short_card_leaves_the_narration_time_to_footage():
    beats = [{"title": "2003", "layout": "date", "seconds": 2.5},
             {"title": "Interview", "layout": "footage"}]
    assert beat_frames(beats, 600, 3) == [75, 525]


def test_the_three_second_limit_includes_photos_and_filmed_static_pages():
    for beat in [{"title": "Photo", "layout": "picture"},
                 {"title": "Page", "layout": "footage", "static": True}]:
        with pytest.raises(RecordingRefused, match="exceeds 3 seconds"):
            beat_frames([beat], 91, 3)


def test_licensed_music_is_not_credited_as_generated(tmp_path):
    document = {**story(), "title": "T", "description": "D", "credits": "C", "media": {},
                "sources": {"original": {"label": "L", "url": "U"}}}
    script = {"chapters": {}}
    plan = {"spoken": {"pt-BR": [{"at": 0}]}}
    description(document, script, plan, "pt-BR", tmp_path, "v")
    assert "Narração e trilha geradas com ElevenLabs." in (tmp_path / "v.pt-BR.description.txt").read_text("utf-8")
    document["generated"] = "Narração gerada com ElevenLabs."
    description(document, script, plan, "pt-BR", tmp_path, "v")
    text = (tmp_path / "v.pt-BR.description.txt").read_text("utf-8")
    assert "Narração gerada com ElevenLabs." in text
    assert "trilha geradas" not in text


def test_an_alias_cannot_bypass_the_footage_reuse_limit():
    document = story()
    document['media'] = {'a': {'file': 'same.mp4'}, 'alias': {'file': 'same.mp4'}}
    document['max_asset_uses'] = 1
    document['scenes']['intro'][0] = {**document['scenes']['intro'][0], 'asset': 'a', 'layout': 'footage'}
    document['scenes']['outro'][0] = {**document['scenes']['outro'][0], 'asset': 'alias', 'layout': 'footage'}
    with pytest.raises(RecordingRefused, match='reuse exceeds 1'):
        validate(document, Voices(), 'pt-BR')
