"""A full video composed on the timeline gives the golden plan (VM7, full videos).

Built as the golden runner builds the story in English and in Portuguese and the developer
walkthrough: the synthetic WebM, the fixture's chapters, the cards, this machine's takes, bed,
opening animation and footage, x264, and no store pages (the runner points STORE_URL at
nothing). Each build encodes for minutes, as the JS build does, so it runs only with
URDIDO_FULL=1; the chapter clips (test_assemble_clip.py) prove the same pieces by default.
"""

import json
import os
from pathlib import Path

import pytest

from golden_plans import main_plan
from test_assemble_clip import (
    GOLDEN,
    NARRATION,
    TURING,
    WORDPRESS,
    _ready,
    load,
    portable,
    synthetic_recording,
)
from urdido import captions
from urdido.assemble.video import FullVideo, Intro
from urdido.audio import mix
from urdido.cards import html
from urdido.narration import Takes
from urdido.sources import chaptered_recording
from urdido.timeline import plan

VARIANTS = {
    # variant: (fixture, story, language, recording folder, webm, script, takes folder, chapters)
    "story-en": ("story", "story", "en", "story", "story.webm", "script.json", NARRATION, 8),
    "story-pt-BR": ("story", "story", "pt-BR", "story", "story.webm", "script.json", NARRATION, 8),
    "developer": ("developer", "developer", "en", "developer", "walkthrough.webm", "developer.json",
                  NARRATION / "developer", 6),
}

pytestmark = [
    pytest.mark.skipif(not _ready(), reason="the takes, the bed, Turing's fonts or a browser are missing"),
    pytest.mark.skipif(os.environ.get("URDIDO_FULL") != "1", reason="set URDIDO_FULL=1 to build the full videos"),
]


def wordpress_broll(developer: bool) -> tuple[list[str], list[str]]:
    """The footage, then a photo, in turn, as story-video.mjs lists them (no store pages here)."""
    if developer:
        return [], []
    footage = sorted(str(p) for p in (WORDPRESS / "demo" / "broll").glob("*.mp4"))
    photos = [
        str(p) for kind in ("guide", "product") for p in sorted((TURING / "demo" / "photos" / kind).glob("*.webp"))
    ]
    broll = []
    for n in range(max(len(footage), len(photos))):
        broll += [s for s in (footage[n] if n < len(footage) else None, photos[n] if n < len(photos) else None) if s]
    return broll, footage


def compose_full(variant: str, tmp_path: Path):
    """Full video `variant` composed as the golden runner builds it: (builder, video, script,
    golden plan, out folder)."""
    from urdido.cards.render import render

    fixture, story, language, folder, webm_name, script_file, takes_dir, count = VARIANTS[variant]
    golden = load(main_plan(GOLDEN / "expected" / variant))
    frame = html.Frame(1920, 1080)
    video = tmp_path / "video"
    parts = video / "parts"
    parts.mkdir(parents=True)
    recorded = tmp_path / "recordings" / folder
    recorded.mkdir(parents=True)
    webm = recorded / webm_name
    synthetic_recording(fixture, False, tmp_path).replace(webm)
    timeline = recorded / "chapters.json"
    timeline.write_text(
        json.dumps({"record": True, "language": language, **load((Path(__file__).parent / "fixtures" / "recordings") / f"{fixture}.json")}),
        encoding="utf-8",
    )
    recording = chaptered_recording(str(webm), str(timeline), language=language, chapters=count)

    declaration = load(WORDPRESS / "demo" / "cards.json")
    theme = html.Theme.load(declaration["theme"], {"turing": str(TURING)})
    script = load(NARRATION / script_file)
    words = declaration["words"][story]
    pages = html.pages(
        theme, frame, words.get(language, words["en"]),
        [captions.Chapter(str(c.n), c.title) for c in recording.chapters], script, language,
    )
    render(pages, frame, str(parts))

    developer = story == "developer"
    broll, footage = wordpress_broll(developer)
    intro = None
    if not developer:
        meta = load(WORDPRESS / "demo" / "intro" / "intro.json")
        intro = Intro(str(WORDPRESS / "demo" / "intro" / "intro.mp4"), meta.get("from", 0))
    built_video = FullVideo(
        name=story, language=language, voices=[language], frame=frame, vertical=False, webm=str(webm),
        chapters=recording.chapters, takes=Takes(script, str(takes_dir)), theme=theme,
        card_count=sum(1 for name in pages if name.startswith("card-") and name[5:].isdigit()),
        parts=str(parts), bed=mix.Bed(str(NARRATION / "music.mp3")),
        intro=intro, broll=broll, footage=footage,
    )
    return built_video.compose(), built_video, script, golden, video


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_full_video_plan_equals_the_golden(variant, tmp_path):
    builder, _, _, golden, video = compose_full(variant, tmp_path)
    built = portable(
        plan(builder.timeline),
        [(str(video), "<video>"), (str(tmp_path / "recordings"), "<recordings>"), (str(WORDPRESS), "<root>")],
    )
    for key in golden:
        if key == "pieces":
            for n, (a, b) in enumerate(zip(built[key], golden[key], strict=True)):
                assert a == b, f"piece {n}"
        assert built[key] == golden[key], key
    assert list(built) == list(golden)

    # the push-ins and the time maps ride on the chapter clips as effects, for an export to read
    effects = {
        e.effect_name
        for track in builder.timeline.video_tracks() for c in track if hasattr(c, "effects") for e in c.effects
    }
    assert "urdido.push-in" in effects
