"""captions.py writes the captions and chapter lists of VM1's six variants (VM4).

Byte for byte, except a narration cue's time may be a millisecond off: see assert_same_captions.

Each golden `*.plan.json` holds the takes as placed (their text included) and the chapter cues;
the chapter titles are the recording's (the fixture beside the goldens) and the narration
script's. The teaser's cues are not in any plan: they are the short cut's rule in
`story-video.mjs`, a 2 s opening and 3 s of each chapter, which the goldens' lengths confirm.
"""

import json
import re
from pathlib import Path

import pytest

from videomaker import captions as c

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


def short_cues(chapters):
    return [{"from": 2 + 3 * i, "to": 5 + 3 * i, "chapter": i} for i in range(len(chapters))]


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
    plan = load(next(folder.glob("*.plan.json")))
    chapters = c.chapters_of(load(GOLDEN / "fixtures" / f"{fixture}.json"))
    script = load(NARRATION / script_file)
    full = "chapter" not in plan

    written = c.caption_files(
        plan,
        chapters,
        script,
        short_cues=short_cues(chapters) if full else None,
        title_languages=WORDPRESS_TITLES,
    )
    expected = expected_captions(folder)
    assert sorted(written) == sorted(expected)
    for name, text in expected.items():
        assert_same_captions(written[name], text, name)


_TIMES = re.compile(r"^(\d\d:\d\d:\d\d[,.]\d{3}) --> (\d\d:\d\d:\d\d[,.]\d{3})$")


def _ms(stamp: str) -> int:
    h, m, rest = stamp.split(":")
    s, ms = re.split(r"[,.]", rest)
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def assert_same_captions(written: str, expected: str, name: str):
    """Equal line for line, except that a cue time may be a millisecond off.

    The plan rounds each take's `at` and `length` to the millisecond, and story-video.mjs cut its
    cues from the unrounded ones, so a boundary can land a millisecond apart (three in the pt-BR
    story). Everything else, the text, the numbering and every other time, must be identical.
    """
    ours, theirs = written.split("\n"), expected.split("\n")
    assert len(ours) == len(theirs), name
    for n, (a, b) in enumerate(zip(ours, theirs), 1):
        if a == b:
            continue
        ta, tb = _TIMES.match(a), _TIMES.match(b)
        assert ta and tb, f"{name}:{n}: {a!r} != {b!r}"
        for x, y in zip(ta.groups(), tb.groups()):
            assert abs(_ms(x) - _ms(y)) <= 1, f"{name}:{n}: {a!r} != {b!r}"


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
