"""VM56: all independent declaration failures precede every render subprocess."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from urdido import cache, media
from urdido.build import Build, main
from urdido.preflight import PreflightRefused, illustrated
from marketing import MARKETING


@pytest.fixture
def cut(tmp_path, monkeypatch):
    monkeypatch.setenv("STORY_VIDEO_DIR", str(tmp_path / "video"))
    monkeypatch.setattr(media, "seconds", lambda file: 3.0)
    monkeypatch.setattr(media, "detect_encoder", lambda: pytest.fail("encoder detection ran before validation"))
    monkeypatch.setattr(media, "ffmpeg", lambda args: pytest.fail("render subprocess started"))
    def write(name, data):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    script = {"voice": "test", "model": "test", "intro": {"en": "Hello"}, "outro": {"en": "Goodbye"}, "chapters": {}}
    write("script.json", script)
    for name in ("intro", "outro"):
        path = tmp_path / f"narration/en/{name}.mp3"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
        write(f"narration/en/{name}.mp3.prov.json", {"prompt": script[name]["en"], "details": {"voice": "test"}, "engine": {"model": "test"}})
        write(f"narration/en/{name}.words.json", {"sha256": cache.file_hash(path), "words": [{"text": script[name]["en"], "start": 0.1, "end": 1.0}]})
    font = MARKETING / "japode/brand/fonts/JapodeJakarta-ExtraBold.ttf"
    if not font.is_file():
        pytest.skip(f"needs the Japode font from the marketing checkout ({font})")
    (tmp_path / "font.ttf").write_bytes(font.read_bytes())
    (tmp_path / "logo.svg").write_text("logo fixture")
    cards = {"theme": {"fonts": {"dir": str(tmp_path), "display": {"files": {"800": "font.ttf"}}, "text": {"file": "font.ttf"}},
                       "colors": {"text": "#fff", "muted": "#ccc", "accent": "#0f0"}, "background": "#000"}}
    write("cards.json", cards)
    story = {"logo": "logo.svg", "brand": "Fixture", "series": "Test", "sources": {"own": {"label": "Fixture", "url": "https://example.org"}},
             "scenes": {name: [{"id": name, "title": name, "kicker": "", "source": "own"}] for name in ("intro", "outro")}}
    story["scenes"]["intro"][0]["caption"] = ""
    write("story.json", story)
    write("highlights.json", {"style": {"font": "Fixture", "color": "#00ff00"}, "lines": {"intro": [{"show": "Hello"}]}})
    write("translations.json", {"intro": ["Olá"], "outro": ["Tchau"]})
    declaration = tmp_path / "video.toml"
    declaration.write_text('''[video]
name="test"
languages={en="eng"}
folders={en="en"}
[source]
kind="illustrated"
declaration="story.json"
[narration]
script="script.json"
takes="narration"
[cards]
declaration="cards.json"
[highlights]
declaration="highlights.json"
fonts="."
[captions.translations.pt]
file="translations.json"
''', encoding="utf-8")
    return SimpleNamespace(folder=tmp_path, declaration=declaration, write=write, story=story, script=script, cards=cards)


def test_valid_preflight_is_read_only_and_returns_production_declarations(cut):
    build = Build(cut.declaration, SimpleNamespace(language="en"))
    before = {str(p): p.read_bytes() for p in cut.folder.rglob("*") if p.is_file()}
    script, cards, story = illustrated(build)
    assert script == cut.script and cards == cut.cards and story == cut.story
    assert before == {str(p): p.read_bytes() for p in cut.folder.rglob("*") if p.is_file()}


@pytest.mark.parametrize("plan", [False, True])
def test_all_missing_anchors_and_stale_words_fail_before_render_for_plan_and_build(cut, plan):
    cut.write("highlights.json", {"style": {"font": "Fixture", "color": "#00ff00"}, "lines": {
        "intro": [{"show": "missing article"}, {"show": "another typo"}], "unknown": []}})
    cut.write("narration/en/outro.words.json", {"sha256": "stale", "words": []})
    cut.write("translations.json", {"outro": ["Tchau"]})
    (cut.folder / "font.ttf").unlink()
    with pytest.raises(PreflightRefused) as failure:
        main([str(cut.declaration), "--language", "en", *(["--plan"] if plan else [])])
    findings = failure.value.findings
    assert len([f for f in findings if "not heard" in f["message"]]) == 2
    assert any("stale word times" in f["message"] and f["take"] == "outro" for f in findings)
    assert any("missing take translation" in f["message"] for f in findings)
    assert any(f["field"] == "theme.fonts" for f in findings)
    assert any("unknown narration take" in f["message"] for f in findings)
    assert all(set(f) == {"file", "field", "take", "beat", "message"} for f in findings)
    assert not (cut.folder / "video/parts/illustrated").exists()


def test_source_bounds_beat_anchors_and_translation_mismatch_are_collected(cut):
    (cut.folder / "clip.mp4").write_bytes(b"probed by fixture")
    cut.story["media"] = {"clip": {"file": "clip.mp4", "license": "Own", "author": "Fixture", "url": "https://example.org"}}
    cut.story["scenes"]["intro"] = [{"id": "short-shot", "title": "Clip", "source": "own", "asset": "clip", "layout": "footage", "at": 2}]
    cut.story["scenes"]["outro"] = [{"id": "before", "title": "A", "source": "missing"},
                                    {"id": "anchored", "title": "B", "source": "own", "from_word": "unheard"}]
    cut.write("story.json", cut.story)
    cut.write("translations.json", {"intro": [], "outro": ["Tchau"]})
    with pytest.raises(PreflightRefused) as failure:
        illustrated(Build(cut.declaration, SimpleNamespace(language="en")))
    findings = failure.value.findings
    assert any("shorter" in f["message"] and f["beat"] == "short-shot" for f in findings)
    assert any("unknown source" in f["message"] and f["beat"] == "before" for f in findings)
    assert any(f["field"].endswith("from_word") and f["beat"] == "anchored" for f in findings)
    assert any("translated sentences" in f["message"] for f in findings)


def test_unordered_word_times_cannot_reach_anchor_resolution(cut):
    file = cut.folder / "narration/en/intro.mp3"
    cut.write("narration/en/intro.words.json", {"sha256": cache.file_hash(file), "words": [
        {"text": "Hello", "start": 1, "end": 2}, {"text": "again", "start": 0, "end": 1}]})
    with pytest.raises(PreflightRefused, match="unordered word times"):
        illustrated(Build(cut.declaration, SimpleNamespace(language="en")))


def test_editorial_label_conflict_fails_before_render(cut):
    cut.story["scenes"]["intro"][0]["caption"] = "A competing label"
    cut.write("story.json", cut.story)
    with pytest.raises(PreflightRefused, match="label conflicts"):
        main([str(cut.declaration), "--language", "en"])
