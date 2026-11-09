"""The push-in and the time maps equal what the JS computes, for every chapter of the fixtures (VM13).

`tests/js/motion.mjs` prints the JS results (motion/pushin.mjs and edit/stretch.mjs, which
story-video.mjs imports); the Python ports are compared with them: the windows and stretches to
the last bit, the zoompan filter and the FCPXML keyframe values as the same strings.
"""

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

from videomaker.edit.stretch import along, kept
from videomaker.motion import pushin
from videomaker.sources import chaptered_recording

HERE = Path(__file__).parent
FIXTURES = HERE.parent / "test" / "golden" / "fixtures"
FRAMES = {
    "story": (pushin.Frame(1920, 1080), False),
    "story-vertical": (pushin.Frame(1080, 1920), True),
    "developer": (pushin.Frame(1920, 1080), False),
}

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node is not on PATH")


@lru_cache(maxsize=1)
def js() -> dict:
    out = subprocess.run(
        ["node", str(HERE / "js" / "motion.mjs")], capture_output=True, text=True, check=True, encoding="utf-8"
    )
    return json.loads(out.stdout)


def chapters_of(fixture: str, tmp: Path):
    data = json.loads((FIXTURES / f"{fixture}.json").read_text(encoding="utf-8"))
    (tmp / "chapters.json").write_text(json.dumps({"record": True, "language": "x", **data}), encoding="utf-8")
    (tmp / "r.webm").write_bytes(b"")
    return chaptered_recording(
        str(tmp / "r.webm"), str(tmp / "chapters.json"), language="x", chapters=len(data["chapters"])
    ).chapters


@pytest.mark.parametrize("fixture", sorted(FRAMES))
def test_every_chapter_moves_as_the_js(fixture, tmp_path):
    frame, vertical = FRAMES[fixture]
    expected = js()[fixture]
    chapters = chapters_of(fixture, tmp_path)
    assert len(chapters) == len(expected)
    pushed = 0
    for chapter, want in zip(chapters, expected):
        label = f"{fixture} chapter {chapter.n}"
        length = chapter.clip.end - chapter.clip.start

        ws = pushin.windows(chapter, frame, vertical)
        assert [
            {"from": w.start, "to": w.end, "zoom": w.zoom, "cx": w.cx, "cy": w.cy, "ease": w.ease} for w in ws
        ] == want["windows"], label
        assert (pushin.zoompan_filter(ws, frame) if ws else None) == want["zoompan"], label
        for (in_chapter, span), keys in zip([(0, length), (1, length / 2)], want["keyed"]):
            got = []
            if ws:
                for t in pushin.moments(ws, in_chapter, span, 30):
                    scale, position = pushin.key(ws, t, frame)
                    got.append({"t": t, "scale": scale, "position": position})
            assert got == keys, label
        pushed += len(ws)

        stretches = kept(chapter, length)
        assert [list(s) for s in stretches] == want["stretches"], label
        for t, landed in want["along"]:
            assert along(stretches, t) == landed, f"{label} at {t}"
    if not vertical:
        assert pushed, f"{fixture}: no chapter pushed in, so the comparison proved little"


def test_some_chapter_cuts_a_wait():
    cut = [
        chapter for fixture in FRAMES for chapter in js()[fixture] if len(chapter["stretches"]) > 1
    ]
    assert cut, "no fixture chapter has a wait long enough to cut"
