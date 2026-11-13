"""Illustrated cuts must refuse an incomplete story instead of silently losing narration."""
from types import SimpleNamespace

import pytest

from videomaker.sources.illustrated import validate
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
