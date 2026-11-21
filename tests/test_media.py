"""media.py builds what media/ffmpeg.mjs builds for the same context (VM23)."""

import json
import os
import shutil
from pathlib import Path

import pytest

from urdido import media as m

HERE = Path(__file__).parent
QUIET = ["-y", "-loglevel", "error"]
needs_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg is not on PATH"
)


# What media/ffmpeg.mjs built for each context, frozen before the JS assembly was removed (VM17):
# the oracle this port was proved against.
ORACLE = json.loads((HERE / "oracles" / "ffmpeg-args.json").read_text(encoding="utf-8"))

CONTEXTS = [
    (1920, 1080, 30, "x264"),  # the long cut
    (1080, 1920, 30, "nvenc"),  # the vertical cut
    (1280, 720, 25, "x264"),
]


@pytest.mark.parametrize("width,height,fps,encoder", CONTEXTS)
def test_arguments_equal_ffmpeg_mjs(tmp_path, width, height, fps, encoder):
    js = ORACLE[f"{width}x{height}@{fps}-{encoder}"]
    py = m.media(width, height, str(tmp_path), fps, encoder)
    here = lambda path: path.replace(str(tmp_path), "<work>")  # noqa: E731

    assert py.encode == js["encode"]
    assert m.video_codec("nvenc", 18) == js["videoCodec"]["nvenc"]
    assert m.video_codec("x264", 18) == js["videoCodec"]["x264"]

    # a card or chapter cut
    cut = py.cut_job("chapter-3.mp4", ["-ss", "12.500", "-t", "4.250", "-i", "take.webm"])
    assert here(cut.file) == js["cutJob"]["file"]
    assert [here(a) for a in cut.args] == js["cutJob"]["args"]

    # a held frame: the frame taken, then held
    freeze = py.freeze_jobs("clip.mp4", 2.3456, 1.5, "held-1")
    assert here(freeze[-1].file) == js["freeze"]["file"]
    assert [QUIET + [here(a) for a in job.args] for job in freeze] == js["freeze"]["calls"]

    # a join
    segments = [s.replace("<work>", str(tmp_path)) for s in js["concat"]["segments"]]
    _, join = py.concat_job(segments, "joined.mp4")
    assert here(join.file) == js["concat"]["file"]
    assert [QUIET + [here(a) for a in join.args]] == js["concat"]["calls"]
    assert here(py.concat_list(segments)).replace(str(tmp_path).replace(chr(92), "/"), "<work>") == js["concat"]["list"]


def test_forced_encoder(monkeypatch):
    monkeypatch.setenv("STORY_ENCODER", "nvenc")
    assert m.detect_encoder() == "nvenc"
    monkeypatch.setenv("STORY_ENCODER", "anything-else")
    assert m.detect_encoder() == "x264"


def test_pool_keeps_order_and_bounds():
    running, peak = [0], [0]
    import threading
    import time

    lock = threading.Lock()

    def task(n):
        def run():
            with lock:
                running[0] += 1
                peak[0] = max(peak[0], running[0])
            time.sleep(0.02)
            with lock:
                running[0] -= 1
            return n

        return run

    assert m.pool([task(n) for n in range(10)], limit=3) == list(range(10))
    assert peak[0] <= 3
    assert m.pool([]) == []


def test_parse_loudness_takes_the_last_report():
    log = (
        'noise {"input_i" : "-30.0", "input_tp" : "-2.0"}\n'
        'more {"input_i" : "-23.1", "input_tp" : "-1.5", "target_offset" : "0.1"}\n'
        "trailing [aac] stats\n"
    )
    assert m.parse_loudness(log)["input_i"] == "-23.1"
    with pytest.raises(RuntimeError):
        m.parse_loudness("no report here")


@needs_ffmpeg
def test_cut_freeze_concat_and_seconds(tmp_path):
    """The operations run: a cut, a held frame and their join, measured."""
    work = m.media(320, 180, str(tmp_path), 30, "x264")
    source = str(tmp_path / "source.mp4")
    m.ffmpeg(["-f", "lavfi", "-i", "testsrc=s=640x360:r=30:d=3", *work.encode, source])

    cut = work.cut("cut.mp4", ["-ss", "0.500", "-t", "1.000", "-i", source])
    held = work.freeze(source, 1.0, 0.5, "held")
    joined = work.concat([cut, held], "joined.mp4")

    assert os.path.exists(joined)
    assert m.seconds(cut) == pytest.approx(1.0, abs=0.05)
    assert m.seconds(held) == pytest.approx(0.5, abs=0.05)
    assert m.seconds(joined) == pytest.approx(1.5, abs=0.1)


@needs_ffmpeg
def test_measure_loudness():
    report = m.measure_loudness(
        ["-f", "lavfi", "-i", "sine=f=440:d=1", "-af", "loudnorm=print_format=json"]
    )
    assert {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"} <= report.keys()
