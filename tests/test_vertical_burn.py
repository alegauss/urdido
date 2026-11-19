"""VM74: an illustrated video in a declared frame; VM75: its narration burned into the picture."""
import pytest

from urdido.captions import burned_cues
from urdido.cards.html import Frame
from urdido.keywords import burn_style, write_ass

WORDS = [{"text": t, "start": s, "end": s + 0.3} for t, s in [
    ("Esse", 0.0), ("é", 0.4), ("o", 0.6), ("primeiro", 0.8), ("bug.", 1.3),
    ("Era", 2.0), ("um", 2.3), ("inseto", 2.5), ("de", 2.9), ("verdade.", 3.1)]]
TAKE = {"at": 10.0, "length": 3.6, "file": "x.mp3",
        "text": "[excited] Esse é o primeiro bug. Era um inseto de verdade."}


def test_burned_captions_use_the_written_words_in_short_groups_that_never_cross_a_sentence():
    cues = burned_cues(TAKE, WORDS, 3)
    assert [c.text for c in cues] == ["Esse é o", "primeiro bug.", "Era um inseto", "de verdade."]
    assert cues[0].start == pytest.approx(10.0)
    assert cues[2].start == pytest.approx(12.0)  # the second sentence starts on its first word
    assert all(a.end == pytest.approx(b.start) for a, b in zip(cues, cues[1:]))


def test_a_lone_last_word_joins_the_group_before_it():
    take = {**TAKE, "text": "Esse é o primeiro bug. Era um inseto de verdade."}
    cues = burned_cues(take, WORDS, 4)
    assert [c.text for c in cues] == ["Esse é o primeiro bug.", "Era um inseto de verdade."]


def test_the_transcripts_spelling_never_reaches_the_picture():
    words = [{**w, "text": "Malenueg"} if w["text"] == "inseto" else w for w in WORDS]
    assert "inseto" in " ".join(c.text for c in burned_cues(TAKE, words, 3))


def test_a_vertical_ass_is_drawn_in_its_frame_with_captions_in_the_shorts_safe_area(tmp_path):
    ass = tmp_path / "k.ass"
    write_ass(ass, [], {"font": "F", "color": "#2BCB6B"}, frame=Frame(1080, 1920),
              burned=burned_cues(TAKE, WORDS, 3), burn={"words": 3})
    text = ass.read_text("utf-8")
    assert "PlayResX: 1080" in text and "PlayResY: 1920" in text
    cap = next(line for line in text.splitlines() if line.startswith("Style: Cap,"))
    assert cap.endswith(",60,140,520,1")
    assert text.count("Dialogue: 0,") == 4 and "{\\q0}Esse é o" in text


def test_a_wide_ass_without_burn_is_unchanged(tmp_path):
    ass = tmp_path / "k.ass"
    write_ass(ass, [{"at": 1, "end": 2, "show": "2003"}], {"font": "F", "color": "#2BCB6B"})
    text = ass.read_text("utf-8")
    assert "PlayResX: 1920" in text and "Style: Cap" not in text
    assert ",0,2,130,130,85,1" in text


def test_a_picture_beat_can_show_part_of_its_image():
    from urdido.sources.illustrated import picture_crop
    from urdido.sources.model import RecordingRefused

    assert picture_crop({"layout": "picture"}) == ""
    assert picture_crop({"layout": "picture", "crop": [0.25, 0.1, 0.75, 0.9]}) == \
        "crop=iw*0.5000:ih*0.8000:iw*0.2500:ih*0.1000,"
    for bad in ([0.5, 0, 0.4, 1], [0, 0, 1], "x", [0, 0, 1.2, 1]):
        with pytest.raises(RecordingRefused):
            picture_crop({"layout": "picture", "crop": bad})
    with pytest.raises(RecordingRefused, match="picture beats only"):
        picture_crop({"layout": "footage", "crop": [0, 0, 1, 1]})


def test_a_meme_line_is_drawn_apart_from_the_callouts(tmp_path):
    ass = tmp_path / "k.ass"
    timed = [{"at": 1, "end": 2, "show": "1947"},
             {"at": 3, "end": 6, "show": "QUANDO O BUG É LITERAL", "look": "meme"}]
    write_ass(ass, timed, {"font": "F", "color": "#2BCB6B"}, frame=Frame(1080, 1920))
    text = ass.read_text("utf-8")
    assert "Style: Meme,F,124,&H00FFFFFF" in text
    assert "Meme,,0,0,0,,{\\q0}QUANDO O BUG É LITERAL" in text
    assert "Key,,0,0,0,,{\\fad(100,150)}1947" in text


def test_a_wide_video_without_memes_has_no_meme_style(tmp_path):
    ass = tmp_path / "k.ass"
    write_ass(ass, [{"at": 1, "end": 2, "show": "2003"}], {"font": "F", "color": "#2BCB6B"})
    assert "Style: Meme" not in ass.read_text("utf-8")


def test_an_unknown_highlight_look_is_refused(monkeypatch):
    from urdido import keywords
    from urdido.sources.model import RecordingRefused

    monkeypatch.setattr(keywords, "word_record", lambda f: [{"text": "bug", "start": 0.1, "end": 0.4}])
    with pytest.raises(RecordingRefused, match="look"):
        keywords.cues([{"file": "x.mp3", "at": 0, "length": 1}], {"x": [{"show": "BUG", "look": "gif"}]})


def test_an_unknown_burn_setting_is_refused():
    with pytest.raises(ValueError, match="unknown keys"):
        burn_style({"colour": "#fff"}, Frame(1080, 1920))
