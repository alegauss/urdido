"""captions.py writes the captions and chapter lists of VM1's six variants, byte for byte (VM4, VM25).

Each golden `*.plan.json` holds the takes as placed (their text included) and the chapter cues,
and the teaser's own `<base>-30s.*.plan.json` holds its cues; the chapter titles are the
recording's (the fixture beside the goldens) and the narration script's. story-video.mjs cuts
the narration's cues from the takes' times as the plan keeps them, so every file is an exact
oracle.
"""

import json
from pathlib import Path

import pytest

from videomaker import captions as c
from golden_plans import main_plan

VIDEO_MAKER = Path(__file__).parent.parent
GOLDEN = VIDEO_MAKER / "test" / "golden"
NARRATION = VIDEO_MAKER.parent / "turing" / "wordpress" / "demo" / "narration"

# The WordPress build captions its silent cuts in these two (`finish` in story-video.mjs).
WORDPRESS_TITLES = ["en", "pt-BR"]

VARIANTS = {
    "story-en": ("story", "script.json"),
    "story-pt-BR": ("story", "script.json"),
    "developer": ("developer", "developer.json"),
    "chapter-2": ("story", "script.json"),
    "vertical-chapter-2": ("story-vertical", "script.json"),
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def teaser_cues(folder: Path):
    """The teaser's cues, from its own plan; None for a variant with no teaser."""
    plans = [p for p in folder.glob("*-30s.*.plan.json")]
    return load(plans[0])["cues"] if plans else None


def expected_captions(folder: Path) -> dict[str, str]:
    return {
        f.name: f.read_bytes().decode("utf-8")
        for f in folder.iterdir()
        if f.suffix in {".srt", ".vtt"} or f.name.endswith(".chapters.txt")
    }


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_variant_captions_equal_the_goldens(variant):
    fixture, script_file = VARIANTS[variant]
    folder = GOLDEN / "expected" / variant
    plan = load(main_plan(folder))
    chapters = c.chapters_of(load(GOLDEN / "fixtures" / f"{fixture}.json"))
    script = load(NARRATION / script_file)

    written = c.caption_files(
        plan, chapters, script, short_cues=teaser_cues(folder), title_languages=WORDPRESS_TITLES,
    )
    expected = expected_captions(folder)
    assert sorted(written) == sorted(expected)
    for name, text in expected.items():
        assert_same_captions(written[name], text, name)


def assert_same_captions(written: str, expected: str, name: str):
    """Equal, byte for byte."""
    assert written == expected, name


def test_stamp_rounds_halves_up():
    assert c.stamp(0) == "00:00:00,000"
    assert c.stamp(3723.0045) == "01:02:03,005"
    assert c.stamp(59.9996) == "00:01:00,000"


def test_cues_drop_stage_directions_and_wrap_two_lines():
    cues = c.caption_cues(
        {"at": 1.0, "length": 4.0, "text": "[excited] Oi! Eu sou a Ana, e essa é a Recanto da Serra."},
        width=12,
    )
    assert all("[" not in cue.text for cue in cues)
    assert all(len(cue.text.split("\n")) <= 2 for cue in cues)
    assert all(len(row) <= 12 for cue in cues for row in cue.text.split("\n"))
    assert cues[0].start == 1.0
    assert cues[-1].end == pytest.approx(5.0)


def test_script_title_wins_over_the_recording():
    chapter = c.Chapter.parse("3. Asks the Site assistant")
    script = {"chapters": {"3": {"title": {"pt-BR": "Pergunta"}}}, "introTitle": {"pt-BR": "Abertura"}}
    assert c.chapter_title(script, chapter, "pt-BR") == "Pergunta"
    assert c.chapter_title(script, chapter, "en") == "Asks the Site assistant"
    assert c.intro_title(script, "pt-BR") == "Abertura"
    assert c.intro_title(script, "en") == "Intro"


def test_a_third_language_needs_no_code():
    chapters = [c.Chapter("1", "Arrives")]
    script = {
        "intro": {"en": "", "pt-BR": "", "es": ""},
        "introTitle": {"es": "Apertura"},
        "chapters": {"1": {"title": {"es": "Llega"}}},
    }
    plan = {
        "video": "story.es", "language": "es", "size": {"width": 1920, "height": 1080},
        "spoken": {"es": []}, "cues": [{"from": 61.5, "to": 70, "chapter": 0}],
    }
    files = c.caption_files(plan, chapters, script)
    assert files["story.es.chapters.txt"] == "0:00 Apertura\n1:01 1. Llega\n"
    assert "1. Llega" in files["story.es.srt"]
    assert "1. Arrives" in files["story.en.srt"]
