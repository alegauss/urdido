"""VM57: production interval selection, cue clocks and real decoded preview frames."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from fonts import TEXT, card_theme
from urdido import cache, captions, media
from urdido.preview import clip_cues, select
from urdido.sources.model import RecordingRefused


def test_take_beat_context_and_intervals_snap_to_production_frames():
    shots = [{"take": "intro", "beat": "intro-0", "id": "stable", "start": 0, "end": 2},
             {"take": "outro", "beat": "outro-0", "id": "end", "start": 2, "end": 4}]
    assert select("beat:stable", shots, [], 4) == (0, 2)
    assert select("take:outro", shots, [], 4, before=.1, after=10) == (1.9, 4)
    assert select("time:1.01:2.01", shots, [], 4) == (1, 61 / 30)
    for selector in ("time:nan:2", "time:2:1", "time:1:5", "beat:missing"):
        with pytest.raises(RecordingRefused):
            select(selector, shots, [], 4)
    cues = clip_cues([captions.Cue(.5, 1.5, "words")], 1, 2)
    assert cues == [captions.Cue(0, .5, "words")]


def test_spoken_cue_refuses_ambiguity_and_selects_declared_occurrence(tmp_path):
    audio = tmp_path / "intro.mp3"
    audio.write_bytes(b"fixture")
    audio.with_suffix(".words.json").write_text(json.dumps({"sha256": cache.file_hash(audio), "words": [
        {"text": "Hello", "start": .2, "end": .4}, {"text": "Hello", "start": 1.2, "end": 1.4}]}))
    placed = [{"file": str(audio), "at": .4}]
    with pytest.raises(RecordingRefused, match="specify occurrence"):
        select("cue:intro:Hello", [], placed, 3)
    assert select("cue:intro:Hello", [], placed, 3, occurrence=2) == (1.6, 1.8)


def test_preview_uses_only_selected_clips_and_matches_full_cut_frames_and_cues(tmp_path, monkeypatch):
    pytest.importorskip("playwright.sync_api")
    pytest.importorskip("fontTools")
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg and ffprobe required")
    from urdido.build import main

    def write(name, data):
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    script = {"voice": "fixture", "model": "fixture", "intro": {"en": "Hello"}, "outro": {"en": "Goodbye"}, "chapters": {}}
    write("script.json", script)
    fonts = tmp_path / "fonts"
    theme, words = card_theme(fonts)
    write("cards.json", {"theme": theme, "words": {"en": words}})
    (tmp_path / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
    media.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=4", "-c:v", "libx264", str(tmp_path / "asset.mp4")])
    for name, frequency in (("intro", 440), ("outro", 550)):
        folder = tmp_path / "narration/en"
        folder.mkdir(parents=True, exist_ok=True)
        audio = folder / f"{name}.mp3"
        media.ffmpeg(["-f", "lavfi", "-i", f"sine=frequency={frequency}:duration=1.3", "-c:a", "libmp3lame", str(audio)])
        Path(str(audio) + ".prov.json").write_text(json.dumps({"prompt": script[name]["en"], "details": {"voice": "fixture"}, "engine": {"model": "fixture"}}))
        audio.with_suffix(".words.json").write_text(json.dumps({"sha256": cache.file_hash(audio), "words": [{"text": script[name]["en"], "start": .1, "end": .9}]}))
    write("story.json", {"title": "Fixture", "description": "Preview fixture", "credits": "Test media", "logo": "logo.svg", "brand": "Fixture", "series": "Test", "brand_mark": "none",
        "sources": {"own": {"label": "Fixture", "url": "https://example.org"}},
        "media": {"motion": {"file": "asset.mp4", "title": "Test motion", "license": "Own fixture", "author": "Test", "url": "https://example.org"}},
        "scenes": {name: [{"id": name + "-stable", "title": "Motion", "caption": "", "kicker": "", "source": "own", "layout": "footage", "asset": "motion", "at": .7 if name == "outro" else 0}] for name in ("intro", "outro")}})
    write("highlights.json", {"style": {"font": TEXT, "color": "#00ff00", "margin": 300}, "lines": {"intro": [{"show": "Hello"}]}})
    write("translations.json", {"intro": ["Olá"], "outro": ["Tchau"]})
    declaration = tmp_path / "video.toml"
    declaration.write_text('''[video]
name="fixture"
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
[captions.translations.pt]
file="translations.json"
track="por"
[captions.safe_area]
action="off"
''', encoding="utf-8")
    out = tmp_path / "video"
    monkeypatch.setenv("STORY_VIDEO_DIR", str(out))
    monkeypatch.setenv("STORY_ENCODER", "x264")
    args = [str(declaration), "--language", "en"]
    assert main([*args, "--preview", "beat:outro-stable"]) == 0
    assert not (out / "parts/illustrated/intro-0.mp4").exists()
    assert not (out / "fixture.en.mp4").exists()
    first_metadata = next((out / "previews").rglob("*.preview.json"))
    first_preview = first_metadata.with_name("fixture.en.mp4")
    first = json.loads(first_metadata.read_text("utf-8"))
    assert main(args) == 0
    full = out / "fixture.en.mp4"
    full_hash = cache.file_hash(full)
    # The full cut and preview must use the same normalized production mix.
    events = json.loads((out / "parts/cache.en.json").read_text())["stages"]
    assert next(e["hit"] for e in events if e["stage"] == "audio mix")

    def compare(preview, report):
        count = report["end_frame_exclusive"] - report["first_frame"]
        graph = (f"[0:v]trim=start_frame={report['first_frame']}:end_frame={report['end_frame_exclusive']},setpts=PTS-STARTPTS[a];"
                 "[1:v]setpts=PTS-STARTPTS[b];[a][b]ssim")
        measured = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(full), "-i", str(preview), "-filter_complex", graph,
                                   "-frames:v", str(count), "-an", "-f", "null", "-"], capture_output=True, text=True, check=True)
        assert float(re.findall(r"All:([0-9.]+)", measured.stderr)[-1]) > .97
        probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=nb_frames", "-of", "json", str(preview)], capture_output=True, text=True, check=True).stdout)
        assert int(probe["streams"][0]["nb_frames"]) == count
    compare(first_preview, first)
    assert main([*args, "--preview", "time:0.7:1.5"]) == 0
    metadata = next(p for p in (out / "previews").rglob("*.preview.json") if p != first_metadata)
    report = json.loads(metadata.read_text("utf-8"))
    assert report["highlights"][0]["at"] == pytest.approx(-.2)
    assert {c["language"] for c in report["captions"]} == {"en", "pt"}
    assert all(c["preview_start"] == pytest.approx(max(c["production_start"], .7) - .7) for c in report["captions"])
    compare(metadata.with_name("fixture.en.mp4"), report)
    assert cache.file_hash(full) == full_hash
    assert main([*args, "--preview", "beat:outro-stable", "--revision", "review1"]) == 0
    pointer = next(out.glob("fixture.en.preview-*.current.json"))
    package = json.loads(pointer.read_text())
    revision = out / package["folder"]
    assert (revision / "fixture.en.mp4").is_file()
    assert "[fixture.en.mp4](fixture.en.mp4)" in (revision / "index.md").read_text()
    assert not (out / "fixture.en.full.current.json").exists()
