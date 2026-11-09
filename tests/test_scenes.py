"""A video filmed scene by scene assembles with every line over its own scene (VM10).

The Viglet Shio promo's Portuguese recordings are this machine's (media is not versioned); the
tests that read them are skipped without them.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from videomaker import media
from videomaker.assemble.scenes import ScenesVideo
from videomaker.cards import html
from videomaker.edit.pacing import fit_to_line
from videomaker.narration import Takes
from videomaker.sources import RecordingRefused
from videomaker.sources.scenes import scene_clips

PROMO = Path(__file__).parent.parent.parent / "shio" / "promo"
CENAS = PROMO / "recordings" / "pt" / "cenas.json"
SHIO = Path(os.environ.get("SHIO_REPO", r"D:\Git\viglet\shio\latest"))

needs_promo = pytest.mark.skipif(
    not (shutil.which("ffprobe") and (PROMO / "recordings" / "pt" / "chapter-1.webm").exists()
         and (PROMO / "demo" / "narration" / "pt-BR" / "intro.mp3").exists()
         and (SHIO / "marketplace" / "quilhara" / "assets" / "fonts").exists()),
    reason="the Viglet Shio promo's recordings, takes or fonts are not on this machine",
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_fit_holds_a_short_clip_and_speeds_a_long_one():
    short = fit_to_line(6.0, 10.0)
    assert (short.speed, short.hold) == (1.0, 4.0)
    assert short.length(6.0) == 10.0
    long = fit_to_line(30.0, 12.0)
    assert long.speed == 2.5 and long.hold == 0.0
    assert long.length(30.0) == pytest.approx(12.0)


def test_a_listed_clip_missing_from_disk_is_refused(tmp_path):
    (tmp_path / "pt").mkdir()
    cenas = tmp_path / "pt" / "cenas.json"
    cenas.write_text(json.dumps({"scenes": [{"scene": "intro", "file": "pt/intro.webm", "seconds": 3}]}),
                     encoding="utf-8")
    with pytest.raises(RecordingRefused, match="not on disk"):
        scene_clips(str(cenas))


@needs_promo
def test_cenas_reads_filmed_scenes_measured_and_unfilmed_as_such():
    scenes = scene_clips(str(CENAS))
    listed = load(CENAS)["scenes"]
    assert [s.name for s in scenes] == [e["scene"] for e in listed]
    for scene, entry in zip(scenes, listed):
        assert scene.filmed == (entry.get("filmed") is not False and bool(entry.get("file")))
        if scene.filmed:
            assert scene.seconds == pytest.approx(media.seconds(scene.file))
    assert {s.source for s in scenes if s.filmed} >= {"terminal"}


def promo_video(parts: Path) -> ScenesVideo:
    declaration = load(PROMO / "demo" / "cards.json")
    script = load(PROMO / "demo" / "narration" / "script.json")
    return ScenesVideo(
        name="promo", language="pt-BR", frame=html.Frame(1920, 1080), scenes=scene_clips(str(CENAS)),
        takes=Takes(script, str(PROMO / "demo" / "narration")), script=script,
        theme=html.Theme.load(declaration["theme"], {"shio": str(SHIO)}),
        words=declaration["words"]["pt-BR"], parts=str(parts), encoder="x264",
    )


def assert_every_line_over_its_scene(video: ScenesVideo, tolerance: float = 0.0):
    assert video.placed
    for scene, kind, start, length, takes in video.placed:
        assert kind == ("scene" if scene.filmed else "card"), scene.name
        assert takes, f"{scene.name}: no current take"
        first, last = takes[0], takes[-1]
        heard_from = start + video.voice_lead
        heard_until = heard_from + sum(t.length for t in takes) + video.line_gap * (len(takes) - 1)
        assert start <= heard_from and heard_until <= start + length + tolerance, scene.name


@needs_promo
def test_the_portuguese_promo_assembles_every_line_over_its_scene(tmp_path):
    video = promo_video(tmp_path)
    timeline = video.compose()
    assert_every_line_over_its_scene(video)
    filmed = [p for p in video.placed if p[1] == "scene"]
    cards = [p for p in video.placed if p[1] == "card"]
    assert filmed and cards  # some scenes are filmed, some wait on Viglet Shio's fixes
    warps = [e for t in timeline.video_tracks() for c in t if hasattr(c, "effects") for e in c.effects
             if e.schema_name() == "LinearTimeWarp"]
    assert len(warps) == len(filmed)


@needs_promo
@pytest.mark.skipif(os.environ.get("VIDEO_MAKER_FULL") != "1", reason="set VIDEO_MAKER_FULL=1 to render")
@pytest.mark.parametrize("cut", ["c1", "c2", "c3"])
def test_the_short_cuts_build_from_the_long_cuts_scenes(cut, tmp_path):
    """VM12: each short is its chapters' scenes, upright, with its voice and burned captions."""
    from videomaker.cuts.selection import chapter_of, selection

    declared = load(PROMO / "demo" / "shorts.json")
    video = promo_video(tmp_path / "parts")
    out = tmp_path / "video"
    out.mkdir()
    short = selection(video, cut, declared["cuts"][cut]["chapters"], str(PROMO / declared["music"]),
                      str(out), limit=declared["limit"])
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", short.file],
        capture_output=True, text=True, check=True,
    ).stdout
    streams = json.loads(probe)["streams"]
    assert {"codec_type": "video", "width": 1080, "height": 1920} in streams
    assert any(s["codec_type"] == "audio" for s in streams)
    assert {chapter_of(s) for s in short.scenes} == set(declared["cuts"][cut]["chapters"])
    print(f"{cut}: {short.length:.1f} s (limit {short.limit:g}, over by {short.over:.1f})")


@needs_promo
@pytest.mark.skipif(os.environ.get("VIDEO_MAKER_FULL") != "1", reason="set VIDEO_MAKER_FULL=1 to render")
def test_the_portuguese_promo_renders_each_piece_to_its_lines(tmp_path):
    video = promo_video(tmp_path)
    video.compose(render=True)
    # encoded at 30 fps, a piece lands within a frame or two of its fit
    assert_every_line_over_its_scene(video, tolerance=0.1)
    pieces = [video.part(f"scene-{n}-{s.name}.mp4") for n, (s, *_) in enumerate(video.placed)]
    joined = video.media.concat(pieces, "joined.mp4")
    assert media.seconds(joined) == pytest.approx(sum(p[3] for p in video.placed), abs=0.2)
