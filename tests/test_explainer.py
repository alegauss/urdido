"""The explainer plans its lines, shots and callouts as the Japode build did (UR4)."""

from pathlib import Path

import pytest

from urdido import declaration, pipelines
from urdido.errors import DeclarationError, Refused
from urdido.pipelines import explainer

SCRIPT = {
    "intro": {"pt-BR": "Olá."},
    "chapters": {
        "1": {"card": {"pt-BR": "O Git cresceu."}, "result": {"pt-BR": "Mudou."}}
    },
    "outro": {"pt-BR": "Tchau."},
}
VOICE = {"intro": 3.0, "chapter-1": 3.0, "chapter-1-result": 1.5, "outro": 1.0}
SHOTS = {
    "title": "Fixture: a test",
    "segments": [
        {"take": "intro", "shots": [{"src": "a", "at": 0}, {"src": "b", "at": 5}]},
        {"take": "chapter-1", "shots": [{"src": "terminal:git", "at": 0, "dur": 3.5}]},
        {"take": "chapter-1-result", "shots": [{"src": "a", "at": 99}]},
        {"take": "outro", "shots": [{"src": "b", "at": 0}, {"src": "a", "at": 2}]},
    ],
    "callouts": {"chapter-1": [{"show": "Git", "def": "a version control system"}]},
}


def planned(tmp_path, shots=SHOTS):
    for take in VOICE:
        (tmp_path / f"{take}.mp3").write_bytes(b"take")
    lengths = {
        **{str(tmp_path / f"{t}.mp3"): v for t, v in VOICE.items()},
        "a.mp4": 10.0,
        "b.mp4": 30.0,
        "git.webm": 20.0,
    }
    return explainer.plan(
        SCRIPT,
        shots,
        "pt-BR",
        take_file=lambda name: tmp_path / f"{name}.mp3",
        seconds=lambda path: lengths[
            str(path) if str(path) in lengths else Path(path).name
        ],
        source_file=lambda src: Path(
            src.split(":")[-1] + (".webm" if ":" in src else ".mp4")
        ),
        words_of=lambda seg: [
            {"text": "O", "start": 0.2},
            {"text": "Git", "start": 0.6},
        ],
    )


def test_lines_follow_the_lead_and_the_breaths(tmp_path):
    made = planned(tmp_path)
    starts = [
        (s["take"], s["start"], s["voice_at"], s["length"]) for s in made["segments"]
    ]
    assert starts == [
        ("intro", 0.0, 0.4, 3.9),
        ("chapter-1", 3.9, 3.9, 3.5),
        ("chapter-1-result", 7.4, 7.4, 2.0),
        ("outro", 9.4, 9.4, 5.5),
    ]
    assert made["length"] == 14.9


def test_free_shots_share_the_line_and_a_late_start_is_pulled_back(tmp_path):
    made = planned(tmp_path)
    intro = [s for s in made["shots"] if s["start"] < 3.9]
    assert [s["dur"] for s in intro] == [1.95, 1.95] and intro[1]["start"] == 1.95
    result = next(s for s in made["shots"] if s["start"] == 7.4)
    assert result["at"] == round(10.0 - 2.0 - 0.05, 3)  # 99 s is past the clip's end
    terminal = next(s for s in made["shots"] if s["src"] == "terminal:git")
    assert terminal["still"] is True


def test_a_keyword_pops_in_when_said_with_its_definition(tmp_path):
    made = planned(tmp_path)
    assert made["callouts"] == [[4.5, 7.2, "Git", "a version control system"]]


def test_shots_that_cannot_fill_their_line_are_refused(tmp_path):
    short = {
        **SHOTS,
        "segments": [
            {**SHOTS["segments"][0], "shots": [{"src": "a", "at": 0, "dur": 1.0}]},
            *SHOTS["segments"][1:],
        ],
    }
    with pytest.raises(DeclarationError, match="shots last 1.00 s, the line 3.90 s"):
        planned(tmp_path, short)
    missing = {**SHOTS, "segments": SHOTS["segments"][1:]}
    with pytest.raises(DeclarationError, match="nothing for intro"):
        planned(tmp_path, missing)


def test_a_keyword_the_take_never_says_is_refused(tmp_path):
    shots = {**SHOTS, "callouts": {"chapter-1": [{"show": "Mercurial"}]}}
    with pytest.raises(Refused, match='"Mercurial" is not heard'):
        planned(tmp_path, shots)


def test_the_explainer_is_a_declared_kind_that_needs_its_shots():
    assert "explainer" in pipelines.kinds()
    document = {
        "video": {"name": "x", "languages": {"pt-BR": "por"}},
        "source": {"kind": "explainer"},
    }
    assert declaration.check(document) == [
        "video.toml [source]: a explainer source needs shots"
    ]
