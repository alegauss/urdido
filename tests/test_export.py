"""The Resolve project is the timeline handed over, with its own media (VM14)."""

import shutil
from pathlib import Path

import opentimelineio as otio
import pytest

from videomaker import media
from videomaker.export.resolve import export_project
from videomaker.timeline import Builder

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not on PATH")


def test_project_holds_the_timeline_its_media_and_finish(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    recording = src / "story.webm"
    media.ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=3", "-c:v", "libvpx", str(recording)])
    card = src / "card-0.png"
    media.ffmpeg(["-f", "lavfi", "-i", "color=c=green:s=320x180", "-frames:v", "1", str(card)])
    take = src / "intro.mp3"
    media.ffmpeg(["-f", "lavfi", "-i", "sine=f=440:d=1", str(take)])
    bed = src / "music.mp3"
    media.ffmpeg(["-f", "lavfi", "-i", "sine=f=220:d=2", str(bed)])
    captions = src / "story.pt-BR.srt"
    captions.write_text("1\n00:00:00,000 --> 00:00:01,000\nOi\n", encoding="utf-8")

    b = Builder("story.pt-BR", "pt-BR", 320, 180)
    b.speaks("pt-BR")
    b.card(str(card), "<video>/card-0.mp4", 2.0)
    b.chapter("<recordings>/story.webm", 0.5, 0, 0.0, "<video>/chapter-1.mp4", 2.0)
    b.say("pt-BR", 0.4, str(take), 1.0, "Oi")
    b.bed({"file": str(bed), "from": 0, "trimDb": -5.0, "volume": 0.2})
    timeline = b.finish()

    project = tmp_path / "story.pt-BR.project"
    otio_file = export_project(
        timeline, str(project), "story.pt-BR", recording="<recordings>/story.webm", captions=str(captions),
        resolve={"event": "Demo", "fairlightPreset": "Voice"}, roots={"recordings": str(src)},
    )

    written = otio.adapters.read_from_file(otio_file)
    assert written.name == "story.pt-BR"
    urls = [c.media_reference.target_url for c in written.find_clips()]
    assert all(u.startswith((project / "media").resolve().as_uri()) for u in urls), urls
    assert (project / "media" / "recording.mp4").exists()  # the WebM transcoded
    assert any(u.endswith("music-bed.m4a") for u in urls)  # the bed, one clip on A2
    ends = {round(t.duration().to_seconds(), 6) for t in written.tracks}
    assert len(ends) == 1
    lua = (project / "finish.lua").read_text(encoding="utf-8")
    for placeholder in ("__NAME__", "__OTIO__", "__SRT__", "__RENDER_DIR__", "__PRESET__"):
        assert placeholder not in lua, placeholder
    assert f"[[{otio_file}]]" in lua and '"Voice"' in lua
    assert (project / "story.pt-BR.srt").exists()
