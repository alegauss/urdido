"""The opening gate in Python, case for case with the JavaScript one (UR30)."""

import copy

import pytest

from urdido import opening
from urdido.sources.model import RecordingRefused


def make(intro="one two three four"):
    return {
        "intro": {"en": intro},
        "chapters": {"1": {"card": {"en": "proof here"}, "result": {"en": "done"}}},
        "outro": {"en": "bye"},
        "opening": {
            "words_per_minute": {"en": 12},
            "proof": {"en": {"take": "chapter-1", "before_word": 0}},
        },
    }


def test_a_proof_at_20_seconds_passes_and_one_word_later_fails():
    assert opening.check(make())[0]["seconds"] == 20
    with pytest.raises(RecordingRefused, match=r"25\.0 s"):
        opening.check(make("one two three four five"))


def test_a_proof_inside_the_intro_and_directions_that_are_not_words():
    script = make("[happy] one two three four")
    script["opening"]["proof"]["en"] = {"take": "intro", "before_word": 1}
    assert opening.check(script)[0]["seconds"] == 5


def test_unicode_words_and_pronunciations_set_the_estimate():
    script = make("[happy] Olá, CMS!")
    script["pronounce"] = {"en": {"CMS": "content management system"}}
    assert opening.check(script)[0]["words"] == 4
    assert opening.check(script)[0]["seconds"] == 20


def test_a_missing_translation_cannot_shorten_the_estimate():
    script = make()
    script["opening"]["proof"]["en"] = {"take": "chapter-1-result", "before_word": 0}
    del script["chapters"]["1"]["card"]["en"]
    with pytest.raises(RecordingRefused, match="missing text for chapter-1"):
        opening.check(script)


@pytest.mark.parametrize(
    "proof",
    [
        None,
        {"take": "missing", "before_word": 0},
        {"take": "intro", "before_word": -1},
        {"take": "intro", "before_word": 4},
        {"take": "intro", "before_word": 0.5},
    ],
)
def test_a_missing_or_invalid_proof_is_refused(proof):
    script = make()
    script["opening"]["proof"]["en"] = proof
    with pytest.raises(RecordingRefused, match="proof"):
        opening.check(script)


@pytest.mark.parametrize("pace", [0, -1, float("nan"), float("inf"), "120", True])
def test_a_pace_that_is_not_a_positive_number_is_refused(pace):
    script = make()
    script["opening"]["words_per_minute"]["en"] = pace
    with pytest.raises(RecordingRefused, match="positive words_per_minute"):
        opening.check(script)


def test_a_locale_checks_only_its_own_translation():
    script = make()
    script["intro"]["pt-BR"] = "Hoje eu quero te contar uma história."
    assert len(opening.check(script, "en")) == 1
    with pytest.raises(RecordingRefused, match="preamble"):
        opening.check(script)
    with pytest.raises(RecordingRefused, match="no intro text"):
        opening.check(script, "fr")


def test_a_script_without_timing_still_refuses_preambles():
    for intro in (
        "Hoje eu quero te contar, com calma. Vem comigo!",
        "Today we will explain the product.",
        "Subscribe to our channel.",
    ):
        script = make(intro)
        del script["opening"]
        with pytest.raises(RecordingRefused, match="preamble"):
            opening.check(script)
    script = make("The product finds the answer.")
    del script["opening"]
    assert opening.check(script) == []


def test_prepare_runs_the_gate_without_node(tmp_path, monkeypatch):
    import json

    from urdido import prepare

    monkeypatch.setattr("shutil.which", lambda name: None)
    file = tmp_path / "script.json"
    file.write_text(json.dumps(make("Vem comigo!")), encoding="utf-8")
    with pytest.raises(RecordingRefused, match="preamble"):
        prepare.opening(file, "en")
    file.write_text(json.dumps(copy.deepcopy(make())), encoding="utf-8")
    prepare.opening(file, "en")
