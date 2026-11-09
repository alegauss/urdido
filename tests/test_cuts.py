"""The Python build renders each of VM1's variants into the golden files (VM9).

Composed as the golden runner composes them (test_assemble_clip, test_assemble_video), then
rendered: the finished files must list the same lengths and streams as the golden outputs.txt,
and the captions and chapter lists beside them must match. Pixels are not compared: a frame may
differ where the encode does. It encodes for minutes, so it runs with VIDEO_MAKER_FULL=1.
"""

import os
from pathlib import Path

import pytest

from test_assemble_clip import GOLDEN, _ready, compose_clip
from test_assemble_video import compose_full
from test_captions import assert_same_captions
from videomaker.cuts.render import Renderer, outputs_line

pytestmark = [
    pytest.mark.skipif(not _ready(), reason="the takes, the bed, Turing's fonts or a browser are missing"),
    pytest.mark.skipif(os.environ.get("VIDEO_MAKER_FULL") != "1", reason="set VIDEO_MAKER_FULL=1 to render"),
]

VARIANTS = ["chapter-2", "vertical-chapter-2", "developer", "story-en", "story-pt-BR"]


@pytest.mark.parametrize("variant", VARIANTS)
def test_rendered_files_equal_the_golden(variant, tmp_path):
    full = not variant.endswith("chapter-2")
    builder, video, script, _, out = (compose_full if full else compose_clip)(variant, tmp_path)
    renderer = Renderer(video, str(out), script)
    if full:
        renderer.full(builder)
    else:
        renderer.clip(builder)

    golden = GOLDEN / "expected" / variant
    finished = sorted(name for name in os.listdir(out) if name.endswith(".mp4"))
    lines = [outputs_line(str(Path(out) / name)) for name in finished]
    assert "\n".join(lines) + "\n" == (golden / "outputs.txt").read_text(encoding="utf-8")

    for expected in sorted(golden.iterdir()):
        if expected.suffix in {".srt", ".vtt"} or expected.name.endswith(".chapters.txt"):
            written = Path(out) / expected.name
            assert written.exists(), expected.name
            assert_same_captions(
                written.read_bytes().decode("utf-8"), expected.read_bytes().decode("utf-8"), expected.name
            )
