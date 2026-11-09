"""A chapter clip composed on the timeline gives the golden plan (VM7, chapter clips).

Built as the golden runner builds it (test/golden/run.mjs): the same synthetic WebM for the
fixture, its chapters, the cards drawn from the declaration, this machine's takes and bed, x264.
Every encode is real, so the lengths are what ffmpeg makes of the same arguments. It needs the
media that is not versioned (the takes, the bed, Turing's fonts) and a browser, and is skipped
without them.
"""

import json
import os
import shutil
from pathlib import Path

import pytest

from videomaker import captions, media
from videomaker.assemble.clip import ClipVideo
from videomaker.audio import mix
from videomaker.cards import html
from videomaker.narration import Takes
from videomaker.sources import chaptered_recording
from videomaker.timeline import plan

VIDEO_MAKER = Path(__file__).parent.parent
GOLDEN = VIDEO_MAKER / "test" / "golden"
WORDPRESS = VIDEO_MAKER.parent / "turing" / "wordpress"
NARRATION = WORDPRESS / "demo" / "narration"
TURING = Path(os.environ.get("TURING_WORDPRESS", r"D:\Git\viglet\turing\latest\wordpress"))

VARIANTS = {
    "chapter-2": ("story", False),
    "vertical-chapter-2": ("story-vertical", True),
}


def _ready() -> bool:
    if not (shutil.which("ffmpeg") and TURING.exists() and (NARRATION / "music.mp3").exists()):
        return False
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return (NARRATION / "pt-BR" / "chapter-2.mp3").exists()


pytestmark = pytest.mark.skipif(not _ready(), reason="the takes, the bed, Turing's fonts or a browser are missing")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def synthetic_recording(fixture: str, vertical: bool, folder: Path) -> Path:
    """The golden runner's synthetic WebM, made with its exact arguments."""
    chapters = load(GOLDEN / "fixtures" / f"{fixture}.json")["chapters"]
    file = folder / f"{fixture}.webm"
    media.ffmpeg([
        "-f", "lavfi", "-i",
        f"testsrc2=size={'360x640' if vertical else '640x360'}:rate=30:duration={chapters[-1]['end'] + 1:.3f}",
        "-c:v", "libvpx", "-deadline", "good", "-cpu-used", "16", "-threads", "1", "-b:v", "400k",
        "-fflags", "+bitexact", "-flags", "+bitexact", str(file),
    ])
    return file


def portable(value, folders):
    if isinstance(value, str):
        for folder, name in folders:
            value = value.replace(folder, name).replace(folder.replace("\\", "/"), name)
        return value.replace("\\", "/")
    if isinstance(value, dict):
        return {k: portable(v, folders) for k, v in value.items()}
    if isinstance(value, list):
        return [portable(v, folders) for v in value]
    return value


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_chapter_clip_plan_equals_the_golden(variant, tmp_path):
    from videomaker.cards.render import render

    fixture, vertical = VARIANTS[variant]
    golden = load(next((GOLDEN / "expected" / variant).glob("*.plan.json")))
    frame = html.Frame(golden["size"]["width"], golden["size"]["height"])
    video = tmp_path / "video"
    parts = video / "parts"
    parts.mkdir(parents=True)

    webm = synthetic_recording(fixture, vertical, tmp_path)
    timeline = tmp_path / "chapters.json"
    timeline.write_text(json.dumps({"record": True, "language": "pt-BR", **load(GOLDEN / "fixtures" / f"{fixture}.json")}),
                        encoding="utf-8")
    recording = chaptered_recording(str(webm), str(timeline), language="pt-BR", chapters=8)

    declaration = load(WORDPRESS / "demo" / "cards.json")
    theme = html.Theme.load(declaration["theme"], {"turing": str(TURING)})
    script = load(NARRATION / "script.json")
    pages = html.pages(
        theme, frame, declaration["words"]["story"]["pt-BR"],
        [captions.Chapter(str(c.n), c.title) for c in recording.chapters], script, "pt-BR",
        clip_chapter=golden["chapter"],
    )
    render(pages, frame, str(parts))

    clip = ClipVideo(
        name="story", language="pt-BR", voices=["pt-BR"], frame=frame, vertical=vertical, webm=str(webm),
        chapters=recording.chapters, takes=Takes(script, str(NARRATION)), theme=theme,
        card_count=sum(1 for name in pages if name.startswith("card-") and name[5:].isdigit()),
        parts=str(parts), bed=mix.Bed(str(NARRATION / "music.mp3")),
    )
    builder, _ = clip.build(golden["chapter"])
    built = portable(plan(builder.timeline), [(str(video), "<video>"), (str(WORDPRESS), "<root>")])
    for key in golden:
        assert built[key] == golden[key], key
    assert list(built) == list(golden)
