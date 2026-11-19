"""The chaptered recording reads VM1's fixtures into the chapter model, and refuses as the JS does (VM8)."""

import json
import os
from pathlib import Path

import pytest

from urdido.sources import RecordingRefused, chaptered_recording
from marketing import GOLDEN, needs_marketing

FIXTURES = GOLDEN / "fixtures"
COUNTS = {"story": 8, "story-vertical": 8, "developer": 6}


def recorded(tmp_path: Path, fixture: str, **extra) -> tuple[str, str, dict]:
    """The fixture as a recording leaves it: chapters.json beside a WebM."""
    data = json.loads((FIXTURES / f"{fixture}.json").read_text(encoding="utf-8"))
    out = {"record": True, "language": "pt-BR", **data, **extra}
    timeline = tmp_path / "chapters.json"
    timeline.write_text(json.dumps(out), encoding="utf-8")
    webm = tmp_path / "story.webm"
    webm.write_bytes(b"")
    return str(webm), str(timeline), data


@needs_marketing
@pytest.mark.parametrize("fixture", sorted(COUNTS))
def test_fixture_reads_into_chapters_equal_to_its_json(tmp_path, fixture):
    webm, timeline, data = recorded(tmp_path, fixture)
    recording = chaptered_recording(webm, timeline, language="pt-BR", chapters=COUNTS[fixture])

    assert recording.language == "pt-BR"
    assert len(recording.chapters) == len(data["chapters"])
    for n, (chapter, raw) in enumerate(zip(recording.chapters, data["chapters"]), 1):
        assert chapter.n == n
        assert f"{chapter.n}. {chapter.title}" == raw["title"]
        assert (chapter.clip.file, chapter.clip.start, chapter.clip.end) == (webm, raw["start"], raw["end"])
        marks = chapter.marks
        assert marks.highlight == raw.get("highlight")
        for line, key in ((marks.voice, "voice"), (marks.result, "result")):
            assert (line and {"name": line.name, "at": line.at}) == (raw.get(key) or None)
        assert [
            {"at": f.at, "box": vars(f.box)} if f.box else {"at": f.at} for f in marks.focus
        ] == raw.get("focus", [])
        assert [{"from": s.start, "to": s.end} for s in marks.skip] == raw.get("skip", [])
        assert chapter.pacing == {}


@needs_marketing
def test_every_mark_appears_in_some_fixture(tmp_path):
    """So the comparison above is not vacuous for any mark."""
    seen = set()
    for fixture in COUNTS:
        data = json.loads((FIXTURES / f"{fixture}.json").read_text(encoding="utf-8"))
        for chapter in data["chapters"]:
            seen |= set(chapter)
    assert {"voice", "result", "highlight", "focus", "skip"} <= seen


def test_refuses_a_missing_recording(tmp_path):
    with pytest.raises(RecordingRefused, match="no recording yet: run `npm run e2e:story:record`"):
        chaptered_recording(
            str(tmp_path / "story.webm"), str(tmp_path / "chapters.json"),
            language="en", chapters=8, record_command="npm run e2e:story:record",
        )


@needs_marketing
def test_refuses_a_missing_chapter(tmp_path):
    webm, timeline, data = recorded(tmp_path, "story")
    data["chapters"].pop()
    Path(timeline).write_text(json.dumps({"record": True, "language": "en", **data}), encoding="utf-8")
    with pytest.raises(RecordingRefused, match="has 7 of 8 chapters"):
        chaptered_recording(webm, timeline, language="en", chapters=8)


@needs_marketing
def test_refuses_another_language(tmp_path):
    webm, timeline, _ = recorded(tmp_path, "story", language="en")
    with pytest.raises(RecordingRefused, match="is in en, not pt-BR"):
        chaptered_recording(webm, timeline, language="pt-BR", chapters=8)


@needs_marketing
def test_refuses_a_recording_that_does_not_say_its_language(tmp_path):
    webm, timeline, _ = recorded(tmp_path, "story", language=None)
    with pytest.raises(RecordingRefused, match="does not say its language"):
        chaptered_recording(webm, timeline, language="pt-BR", chapters=8)


@needs_marketing
def test_refuses_a_test_run(tmp_path):
    webm, timeline, _ = recorded(tmp_path, "story", record=False)
    with pytest.raises(RecordingRefused, match="the test, not the recording"):
        chaptered_recording(webm, timeline, language="pt-BR", chapters=8)


@needs_marketing
def test_refuses_a_recording_older_than_its_story(tmp_path):
    webm, timeline, _ = recorded(tmp_path, "story")
    story = tmp_path / "story.md"
    story.write_text("changed", encoding="utf-8")
    later = os.path.getmtime(timeline) + 10
    os.utime(story, (later, later))
    with pytest.raises(RecordingRefused, match="story.md changed after the recording"):
        chaptered_recording(webm, timeline, language="pt-BR", chapters=8, sources=[str(story)])
    # and accepts one recorded after it
    os.utime(story, (later - 20, later - 20))
    assert chaptered_recording(webm, timeline, language="pt-BR", chapters=8, sources=[str(story)])
