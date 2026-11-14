"""Illustrated cuts must refuse an incomplete story instead of silently losing narration."""
from types import SimpleNamespace

import pytest

from videomaker.sources.illustrated import validate
from videomaker.sources.illustrated import beat_frames
from videomaker.sources.illustrated import description
from videomaker.sources.illustrated import anchored_frames
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


def test_a_timed_caption_leaves_the_brand_mark_on_screen():
    from videomaker.cards.html import Frame
    from videomaker.sources.illustrated import page

    theme = SimpleNamespace(colors={"text": "#fff", "muted": "#ccc", "accent": "#2BCB6B"},
                            fonts={"display-800": "d.woff2", "text": "t.woff2"}, data={"background": "#000"})
    document = {**story(), "brand": "JAPODE", "series": "S", "sources": {"original": {"label": "L", "url": "U"}}}
    beat = {"kicker": "", "title": "Matt", "caption": "WordPress", "layout": "footage", "source": "original"}
    mark = page({**beat, "caption": "", "title": "", "mark_only": True}, document, theme, Frame(1920, 1080), "logo", 1)
    assert "<b>JAPODE</b>" in mark
    assert "WordPress" not in mark
    assert ".full:before{display:none}" in mark


def test_word_anchor_includes_voice_lead_and_rounds_frames_vm42(tmp_path):
    import hashlib
    import json

    audio = tmp_path / "intro.mp3"
    audio.write_bytes(b"audio")
    words = audio.with_suffix(".words.json")
    data = {"sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
            "words": [{"text": "Gutenberg", "start": 1.21, "end": 1.8}]}
    words.write_text(json.dumps(data), encoding="utf-8")
    beats = [{"title": "before"}, {"title": "portrait", "from_word": "Gutenberg", "at": 27}]
    assert anchored_frames(beats, 120, str(audio)) == [48, 72]
    assert beats[1]["at"] == 27  # Source trim never becomes a timeline start.
    audio.write_bytes(b"retake")
    data["sha256"] = hashlib.sha256(audio.read_bytes()).hexdigest()
    data["words"][0]["start"] = 2.01
    words.write_text(json.dumps(data), encoding="utf-8")
    assert anchored_frames(beats, 120, str(audio)) == [72, 48]


def test_anchor_constraints_refuse_short_beats_and_reverse_time_vm42(tmp_path, monkeypatch):
    monkeypatch.setattr("videomaker.keywords.anchor", lambda file, spec: spec)
    with pytest.raises(RecordingRefused, match="first beat"):
        anchored_frames([{"title": "one", "from_word": 1}], 120, "unused")
    with pytest.raises(RecordingRefused, match="one second"):
        anchored_frames([{"title": "one"}, {"title": "two", "from_word": 0.1}], 120, "unused")
    with pytest.raises(RecordingRefused, match="increase"):
        anchored_frames([{"title": "one"}, {"title": "two", "from_word": 2},
                         {"title": "three", "from_word": 1}], 150, "unused")
