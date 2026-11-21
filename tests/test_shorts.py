"""Shorts cut by the framework from a built video's plan (UR2)."""

import json
import shutil
import subprocess

import pytest

from urdido import shorts

PLAN = {
    "length": 40.0,
    "segments": [
        {"take": "intro", "start": 0.0, "voice_at": 0.5, "voice": 4.0},
        {"take": "chapter-1", "start": 5.0, "voice_at": 5.4, "voice": 8.0},
        {"take": "chapter-1-result", "start": 14.0, "voice_at": 14.2, "voice": 6.0},
        {"take": "chapter-2", "start": 21.0, "voice_at": 21.3, "voice": 9.0},
    ],
    "shots": [
        {"src": "intro.mp4", "start": 0.0},
        {"src": "origin", "start": 5.0},
        {"src": "terminal:git", "start": 9.0},
        {"src": "talk", "start": 15.0},
        {"src": "card:end", "start": 21.0},
    ],
    "callouts": [
        [6.0, 8.0, "monorepo", "um só repositório"],
        [16.0, 30.0, "30 mil"],
        [25.0, 27.0, "late"],
    ],
}
CUT = shorts.Cut(
    1,
    ("chapter-1", "chapter-1-result"),
    ("A Anthropic faz", "30 mil merges por dia"),
    "30 mil merges por dia: o Git não aguentou #shorts",
    "Texto.",
)
LOOK = shorts.Look("#0b1410", "#2BCB6B", "#111111", "Title Font", "Text Font")
WORDS = [
    {"text": "Em", "start": 0.0, "end": 0.2},
    {"text": "maio", "start": 0.2, "end": 0.6},
    {"text": "eram", "start": 0.6, "end": 0.9},
    {"text": "2500", "start": 0.9, "end": 1.5},
    {"text": "merges.", "start": 1.5, "end": 2.0},
    {"text": "Hoje", "start": 3.0, "end": 3.4},
]


def test_a_short_spans_its_takes_and_ends_its_tail_after_the_last_word():
    rules = shorts.Rules()
    cut = shorts.span(PLAN, CUT, rules)
    assert (cut.start, cut.voice_end) == (5.0, 20.2)
    assert cut.clip == pytest.approx(15.2 + rules.tail)
    assert cut.length == pytest.approx(cut.clip / 1.1)
    with pytest.raises(ValueError, match="takes the plan does not have"):
        shorts.span(PLAN, shorts.Cut(9, ("chapter-9",), ("a", "b"), "t", "x"), rules)


def test_long_shots_are_punched_in_at_their_middle_but_never_a_terminal():
    spans = shorts.punches(PLAN, 5.0, 20.55, shorts.Rules())
    # origin 5-9 and talk 15-20.55 are long; the terminal 9-15 is left whole
    assert spans == [pytest.approx((2.0, 4.0)), pytest.approx((12.775, 15.55))]


def test_captions_follow_the_words_with_the_scripts_spelling_and_hold_until_the_next():
    lines = shorts.word_lines(WORDS, 10.0, 20, {"2500": "2.500"})
    assert [text for *_, text in lines] == ["Em maio eram 2.500", "merges.", "Hoje"]
    assert lines[0][:2] == (10.0, pytest.approx(11.5))
    assert lines[1][1] == pytest.approx(
        12.6
    )  # held 0.6 s past its word, not until 13.0


def test_the_subtitles_loop_back_to_the_hook_with_the_pointer_over_the_last_seconds():
    rules = shorts.Rules()
    cut = shorts.span(PLAN, CUT, rules)
    words = {"chapter-1": WORDS, "chapter-1-result": WORDS[:2]}
    ass = shorts.subtitles(
        PLAN, CUT, cut, words, LOOK, rules, ("A história completa", "tá no canal")
    )
    swap = shorts.stamp(cut.length - rules.pointer)
    assert "Hook,,0,0,0,,{\\an2\\pos(540,330)}A Anthropic faz" in ass
    assert f"{swap},{shorts.stamp(cut.length)},HookKey" in ass and "tá no canal" in ass
    assert "\\c&H6BCB2B&}2500" in ass  # numbers in the accent, as ASS's BGR
    assert "monorepo" in ass and "um só repositório" in ass and "30 mil" in ass
    assert "}late" not in ass  # a callout after the last word stays out
    assert "Style: Hook,Title Font" in ass and "Style: Def,Text Font" in ass


def test_the_graph_speeds_both_streams_normalises_loudness_and_rules_the_picture(
    tmp_path,
):
    rules = shorts.Rules()
    cut = shorts.span(PLAN, CUT, rules)
    built = shorts.graph(cut, [(2.0, 4.0)], LOOK, rules, tmp_path / "a.ass", None)
    assert "between(it,2.00,4.00)" in built and "setpts=(PTS-STARTPTS)/1.1" in built
    assert "atempo=1.1" in built and "loudnorm=I=-14.0:TP=-1.5" in built
    assert built.count("0x2BCB6B") == 2 and "fontsdir" not in built


def test_a_short_is_refused_for_a_long_title_wrong_hashtags_or_past_a_minute():
    rules = shorts.Rules()
    long = shorts.Cut(2, ("chapter-1",), ("sem número", "aqui"), "x" * 61, "")
    found = shorts.check(long, shorts.Span(0, 0, 70, 70 / 1.1), rules, ["#a", "#b"])
    assert {row["rule"]: row["severity"] for row in found} == {
        "title.length": "refuse",
        "tags.count": "refuse",
        "hook.number": "advise",
        "length.hard": "refuse",
    }
    ok = shorts.check(CUT, shorts.span(PLAN, CUT, rules), rules, ["#a", "#b", "#c"])
    assert [row["rule"] for row in ok] == ["length.feed"]  # 14 s: advised, not refused
    with pytest.raises(ValueError, match="title.length"):
        shorts.enforce(found)


def test_rules_look_and_cuts_refuse_what_they_do_not_know():
    assert shorts.rules_of({"speed": 1.2, "seconds": [15, 50]}).seconds == (15, 50)
    with pytest.raises(ValueError, match="has no sped"):
        shorts.rules_of({"sped": 1.2})
    with pytest.raises(ValueError, match="needs night"):
        shorts.look_of({"accent": "#ffffff"})
    with pytest.raises(ValueError, match="#RRGGBB"):
        shorts.look_of(
            {
                "night": "green",
                "accent": "#fff",
                "ink": "#000000",
                "title_font": "a",
                "text_font": "b",
            }
        )
    with pytest.raises(ValueError, match="two lines"):
        shorts.cuts_of(
            [{"n": 1, "takes": [], "hook": ["only"], "title": "", "text": ""}]
        )


def test_the_description_names_title_length_link_credits_notes_and_tags():
    text = shorts.description(
        CUT,
        "pt-BR",
        "https://youtu.be/x",
        ["#git", "#ia", "#dev"],
        ['- "Talk", Someone (https://y), CC BY'],
        "Narração gerada.",
    )
    assert text.startswith(
        f"Título ({len(CUT.title)} caracteres)\n{CUT.title}\n\nDescrição\nTexto."
    )
    assert "O vídeo completo: https://youtu.be/x" in text and text.endswith(
        "#git #ia #dev\n"
    )
    assert shorts.description(CUT, "en", "", ["#a"], [], "").startswith("Title (")
    assert shorts.used_sources(PLAN, shorts.span(PLAN, CUT, shorts.Rules())) == [
        "origin",
        "talk",
    ]


def test_the_encoded_short_is_held_to_length_loudness_peak_and_a_moving_end():
    spec = shorts.spec_text("demo", shorts.Rules())
    assert spec.startswith('asset = "demo"\n')
    assert 'measure = "video_loudness"\nmin = -15\nmax = -13' in spec
    assert 'measure = "video_frozen_end"\nmax = 0.5' in spec
    assert 'measure = "video_seconds"\nmax = 60' in spec


def test_a_short_past_its_measures_is_refused_naming_each_miss(tmp_path, monkeypatch):
    from urdido import extras, library

    asked = {}

    def answer(operation, root, **parameters):
        asked.update(operation=operation, **parameters)
        return {
            "passed": False,
            "predicates": [
                {"measure": "video_seconds", "value": 30.0, "max": 60, "passed": True},
                {
                    "measure": "video_loudness",
                    "value": -19.2,
                    "min": -15,
                    "max": -13,
                    "passed": False,
                },
            ],
        }

    monkeypatch.setattr(extras, "require", lambda *a, **k: None)
    monkeypatch.setattr(library, "delegate", answer)
    video = tmp_path / "shorts" / "demo-1.mp4"
    (video.parent / "work").mkdir(parents=True)
    with pytest.raises(ValueError, match="video_loudness is -19.2, held to -15 to -13"):
        shorts.measures(video, tmp_path, shorts.Rules())
    assert asked == {
        "operation": "accept.check",
        "spec": "shorts/work/demo-1.spec.toml",
        "subject": "shorts/demo-1.mp4",
    }


def test_without_polyweave_the_short_says_it_went_unmeasured(tmp_path, capsys):
    pytest.importorskip("PIL")
    try:
        import polyweave  # noqa: F401
    except ImportError:
        assert shorts.measures(tmp_path / "a.mp4", tmp_path, shorts.Rules()) is None
        assert "unmeasured" in capsys.readouterr().err
    else:
        pytest.skip("polyweave is installed here")


def declaration(folder, plan=PLAN, title=CUT.title):
    (folder / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (folder / "words").mkdir(exist_ok=True)
    for take in ("chapter-1", "chapter-1-result"):
        (folder / "words" / f"{take}.words.json").write_text(
            json.dumps({"words": WORDS}), encoding="utf-8"
        )
    (folder / "sources.json").write_text(
        json.dumps({"origin": {"title": "Origin", "url": "https://o"}}),
        encoding="utf-8",
    )
    file = folder / "video.toml"
    file.write_text(
        f"""
[shorts]
plan = "plan.json"
picture = "picture.mp4"
mix = "mix.wav"
words = "words/{{take}}.words.json"
out = "shorts/demo-short-{{n}}-{{language}}"
link = "https://youtu.be/full"
tags = ["#git", "#ia", "#dev"]
sources = "sources.json"
credit = "- {{title}} ({{url}})"
[shorts.rules]
seconds = [5, 55]
[shorts.look]
night = "#0b1410"
accent = "#2BCB6B"
ink = "#111111"
title_font = "Arial"
text_font = "Arial"
[shorts.notes]
pt-BR = "Narração gerada."
[[shorts.cut]]
n = 1
takes = ["chapter-1", "chapter-1-result"]
hook = ["A Anthropic faz", "30 mil merges por dia"]
title = "{title}"
text = "Texto."
""",
        encoding="utf-8",
    )
    return file


def test_the_cli_check_reads_the_declaration_without_encoding(tmp_path, capsys):
    file = declaration(tmp_path)
    assert shorts.main([str(file), "--language", "pt-BR", "--check"]) == 0
    assert "1 pass" in capsys.readouterr().out
    assert shorts.main([str(file), "7", "--language", "pt-BR", "--check"]) == 1
    file = declaration(tmp_path, title="y" * 70)
    assert shorts.main([str(file), "--language", "pt-BR", "--check"]) == 1
    assert "title.length" in capsys.readouterr().err


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not on PATH")
def test_a_short_is_encoded_vertical_with_sound_and_its_description(tmp_path):
    pytest.importorskip("PIL")
    plan = {
        **PLAN,
        "length": 9.0,
        "segments": [
            {"take": "chapter-1", "start": 1.0, "voice_at": 1.2, "voice": 2.0},
            {"take": "chapter-1-result", "start": 3.2, "voice_at": 3.3, "voice": 1.5},
        ],
        "shots": [{"src": "origin", "start": 0.0}],
        "callouts": [],
    }
    file = declaration(tmp_path, plan)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=s=640x360:r=30:d=6",
            "-pix_fmt",
            "yuv420p",
            str(tmp_path / "picture.mp4"),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=f=440:d=6",
            str(tmp_path / "mix.wav"),
        ],
        check=True,
    )
    assert shorts.main([str(file), "--language", "pt-BR"]) == 0
    video = tmp_path / "shorts" / "demo-short-1-pt-BR.mp4"
    probe = json.loads(
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(video),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    picture = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (picture["width"], picture["height"]) == (1080, 1920)
    assert any(s["codec_type"] == "audio" for s in probe["streams"])
    assert float(probe["format"]["duration"]) == pytest.approx(
        (4.8 + 0.35 - 1.0) / 1.1, abs=0.1
    )
    text = (tmp_path / "shorts" / "demo-short-1-pt-BR.txt").read_text(encoding="utf-8")
    assert "- Origin (https://o)" in text and "Narração gerada." in text
