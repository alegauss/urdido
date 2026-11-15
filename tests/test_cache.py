"""VM55: effective inputs, verified outputs, and resumable production composition."""
import json
import shutil
from pathlib import Path

import pytest

from videomaker import cache, media


def test_partial_failure_retains_only_completed_stages_and_checks_output_bytes(tmp_path):
    source = tmp_path / "source"
    source.write_bytes(b"a")
    first, second = tmp_path / "first", tmp_path / "second"
    calls = []

    def build(file):
        calls.append(file.name)
        file.write_bytes(source.read_bytes())

    def stages(fail=False):
        with cache.configured(tmp_path / "cache.json") as session:
            cache.run("first", [first], {}, lambda: build(first), inputs=[source])
            def last():
                if fail:
                    second.write_bytes(b"partial")
                    raise RuntimeError("late failure")
                build(second)
            cache.run("second", [second], {}, last, inputs=[first])
        return session

    with pytest.raises(RuntimeError, match="late failure"):
        stages(fail=True)
    assert not second.with_name("second.cache.json").exists()
    session = stages()
    assert calls == ["first", "second"]
    assert [e["hit"] for e in session.events] == [True, False]
    first.write_bytes(b"corrupt")
    stages()
    assert calls == ["first", "second", "first"]  # repaired to same bytes; downstream still valid
    source.write_bytes(b"changed")
    stages()
    assert calls[-2:] == ["first", "second"]


def test_reused_input_is_hashed_once_and_context_reaches_workers(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.write_bytes(b"large reused media")
    original = cache.hashlib.file_digest
    count = 0
    def hashed(stream, algorithm):
        nonlocal count
        count += 1
        return original(stream, algorithm)
    monkeypatch.setattr(cache.hashlib, "file_digest", hashed)
    with cache.configured(tmp_path / "cache.json"):
        values = media.pool([lambda: cache.file_hash(source) for _ in range(20)])
    assert len(set(values)) == 1
    assert count == 1


def test_tiny_illustrated_cut_reuses_stages_and_invalidates_visual_audio_fonts(tmp_path, monkeypatch):
    pytest.importorskip("playwright.sync_api")
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg and ffprobe required")
    from videomaker.build import main

    root = Path(__file__).resolve().parents[2]
    fonts = tmp_path / "fonts"
    shutil.copytree(root / "japode/brand/fonts", fonts)
    cards = json.loads((root / "japode/wordpress/cards.json").read_text("utf-8"))
    cards["theme"]["fonts"]["dir"] = str(fonts)
    cards["words"] = {"en": cards["words"]["pt-BR"]}
    def write(name, data):
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    write("cards.json", cards)
    script = {"voice": "test", "model": "test", "intro": {"en": "Hello"}, "outro": {"en": "Goodbye"}, "chapters": {}}
    write("script.json", script)
    (tmp_path / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30"><circle r="10" cx="15" cy="15" fill="green"/></svg>')
    story = {"title": "Fixture", "description": "Cache fixture", "credits": "Test fixture", "logo": "logo.svg", "brand": "Fixture", "series": "Cache",
             "sources": {"own": {"label": "Fixture", "url": "https://example.org"}}, "scenes": {
                 name: [{"title": "Fixture", "kicker": "", "big": "2026", "source": "own", "id": name}]
                 for name in ("intro", "outro")}}
    story["scenes"]["intro"][0]["caption"] = ""
    write("story.json", story)
    voice_dir = tmp_path / "narration/en"
    voice_dir.mkdir(parents=True)
    def audio(name, frequency):
        file = voice_dir / f"{name}.mp3"
        media.ffmpeg(["-f", "lavfi", "-i", f"sine=frequency={frequency}:duration=1.1", "-c:a", "libmp3lame", str(file)])
        file.with_suffix(".words.json").write_text(json.dumps({"sha256": cache.file_hash(file),
            "words": [{"text": script[name]["en"], "start": 0.1, "end": 0.9}]}), encoding="utf-8")
        Path(str(file) + ".prov.json").write_text(json.dumps({"prompt": script[name]["en"], "details": {"voice": "test"}, "engine": {"model": "test"}}), encoding="utf-8")
    audio("intro", 440)
    audio("outro", 550)
    write("highlights.json", {"style": {"font": "Japode Jakarta SemiBold", "color": "#00ff00", "margin": 300}, "lines": {"intro": [{"show": "Hello"}]}})
    declaration = tmp_path / "video.toml"
    declaration.write_text('''[video]
name="cache-test"
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
[music]
bed="missing.mp3"
[audio]
peak=-2.0
margin=3.0
[highlights]
declaration="highlights.json"
fonts="fonts"
[captions.safe_area]
action="off"
''', encoding="utf-8")
    monkeypatch.setenv("STORY_VIDEO_DIR", str(tmp_path / "video"))
    monkeypatch.setenv("STORY_ENCODER", "x264")
    actual = media.ffmpeg
    encoded = []
    def tracked(args):
        if str(args[-1]).endswith((".mp4", ".m4a", ".wav")):
            encoded.append(str(args[-1]))
        actual(args)
    monkeypatch.setattr(media, "ffmpeg", tracked)
    def build():
        encoded.clear()
        assert main([str(declaration), "--language", "en"]) == 0
        return json.loads((tmp_path / "video/parts/cache.en.json").read_text())["stages"]
    first = build()
    assert encoded and not any(e["hit"] for e in first)
    progress_events = [json.loads(line) for line in (tmp_path / "video/parts/progress.en.jsonl").read_text("utf-8").splitlines()]
    assert {"validation", "raster", "source clips", "join", "highlights", "mix", "mux", "verification"} <= {
        e["stage"] for e in progress_events if e["event"] == "finished"}
    assert progress_events[-1]["pending"] == []
    story["scenes"]["intro"][0]["id"] = "identity-only"
    story["scenes"]["outro"][0]["people"] = ["provenance-only"]
    write("story.json", story)
    from playwright.sync_api import BrowserType
    with monkeypatch.context() as unchanged:
        unchanged.setattr(BrowserType, "launch", lambda *args, **kwargs: pytest.fail("unchanged cards launched a browser"))
        assert all(e["hit"] for e in build())
    assert encoded == []
    story["scenes"]["outro"][0]["caption"] = "Edited caption"
    write("story.json", story)
    edited = build()
    assert [e["hit"] for e in edited if e["stage"] == "raster"] == [True, False]
    assert next(e["hit"] for e in edited if e["stage"] == "audio mix")
    audio("intro", 660)
    changed = build()
    assert all(e["hit"] for e in changed if e["stage"] == "raster")
    assert not next(e["hit"] for e in changed if e["stage"] == "audio mix")
    shutil.copyfile(fonts / "JapodeJakarta-ExtraBold.ttf", fonts / "JapodeJakarta-SemiBold.ttf")
    changed_font = build()
    assert not any(e["hit"] for e in changed_font if e["stage"] in {"raster", "highlights"})
    assert next(e["hit"] for e in changed_font if e["stage"] == "audio mix")
