"""The ffmpeg runtime the assembly sits on, ported from `media/ffmpeg.mjs` (VM2, VM23).

Running ffmpeg quietly, a pool that bounds how many encodes run at once, the encoder (NVENC
where the machine has one, x264 elsewhere), a file's length and a mix's loudness, and the
cuts, held frames and joins a timeline is made of. Nothing here knows which video it serves:
the frame size, the frame rate and the folder the pieces go to are a context's, from
`media()`. Every argument list is built exactly as `ffmpeg.mjs` builds it, so the two
produce the same pieces while `story-video.mjs` is still the production build.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass, field
from typing import Callable, Literal, Sequence, TypeVar

Encoder = Literal["nvenc", "x264"]
T = TypeVar("T")

# STORY_TIMING=1 prints each encode that takes over two seconds, to see where a build goes.
_TIMING = bool(os.environ.get("STORY_TIMING"))


def _timed(started: float, args: Sequence[str]) -> None:
    took = time.monotonic() - started
    if _TIMING and took > 2:
        sys.stderr.write(f"[timing] {took:.1f}s {os.path.basename(str(args[-1]))}\n")


def ffmpeg(args: Sequence[str]) -> None:
    """Run ffmpeg quietly, failing loudly (CalledProcessError on a non-zero exit)."""
    started = time.monotonic()
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *args],
        stdin=subprocess.DEVNULL,
        check=True,
    )
    _timed(started, args)


# How many encodes run at once. Most of a build is filters that use one core each (zoompan)
# run one after another, which left the rest of the machine idle; six at a time also stays
# under a consumer NVIDIA card's limit on concurrent encode sessions.
PARALLEL = max(1, min(6, (os.cpu_count() or 1) // 4))


def pool(tasks: Sequence[Callable[[], T]], limit: int = PARALLEL) -> list[T]:
    """Run tasks with at most `limit` of them at once, keeping their results in order.

    ffmpeg runs in its own process, so threads are enough to keep `limit` encodes busy.
    The first failure is raised once every started task has settled.
    """
    if not tasks:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(limit, len(tasks)))) as running:
        futures = [running.submit(copy_context().run, task) for task in tasks]
        return [future.result() for future in futures]


def detect_encoder() -> Encoder:
    """NVIDIA's NVENC where this machine has one, x264 elsewhere; STORY_ENCODER forces one."""
    forced = os.environ.get("STORY_ENCODER")
    if forced:
        return "nvenc" if forced == "nvenc" else "x264"
    try:
        probe = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
                "-c:v", "h264_nvenc", "-f", "null", "-",
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
        )
    except FileNotFoundError:
        return "x264"
    return "nvenc" if probe.returncode == 0 else "x264"


# A keyframe every half second exactly (15 frames at 30 fps), on every piece: a dissolve
# then re-encodes only the half second it blends and copies the rest, cut on a keyframe.
KEY_EVERY = 15


def video_codec(encoder: Encoder, quality: int) -> list[str]:
    """The encoder arguments at a quality: x264's CRF, or NVENC's constant quality."""
    if encoder == "nvenc":
        return [
            "-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr",
            "-cq", str(quality), "-b:v", "0",
            "-g", str(KEY_EVERY), "-no-scenecut", "1",
        ]
    return [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(quality),
        "-g", str(KEY_EVERY), "-keyint_min", str(KEY_EVERY), "-sc_threshold", "0",
    ]


def seconds(file: str) -> float:
    """A file's length in seconds."""
    out = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file,
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=True,
    )
    return float(out.stdout.strip())


_REPORT = re.compile(r"\{[^{}]*\"input_i\"[^{}]*\}")


def parse_loudness(log: str) -> dict:
    """The last brace block naming input_i in an ffmpeg log: loudnorm's report."""
    reports = _REPORT.findall(log)
    if not reports:
        raise RuntimeError(f"loudnorm printed no report:\n{log[-2000:]}")
    return json.loads(reports[-1])


def measure_loudness(args: Sequence[str]) -> dict:
    """Run ffmpeg to measure, and read loudnorm's report (input_i, input_tp, input_lra, ...)."""
    log = subprocess.run(
        ["ffmpeg", "-hide_banner", *args, "-f", "null", "-"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stderr
    return parse_loudness(log)


def _join(work_dir: str, name: str) -> str:
    # Node's path.join normalises as it joins; normpath does the same here.
    return os.path.normpath(os.path.join(work_dir, name))


@dataclass(frozen=True)
class Job:
    """A piece and the ffmpeg arguments that make it, not yet run."""

    file: str
    args: list[str]


@dataclass
class Media:
    """One video's media context: its frame, its encoder and the folder its pieces go to."""

    width: int
    height: int
    work_dir: str
    fps: int = 30
    encoder: Encoder = field(default_factory=detect_encoder)

    def video_codec(self, quality: int) -> list[str]:
        return video_codec(self.encoder, quality)

    @property
    def encode(self) -> list[str]:
        """Each card and clip encoded alike, so they join without another encode."""
        w, h = self.width, self.height
        return [
            "-vf",
            f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={self.fps},format=yuv420p",
            *self.video_codec(20),
            "-an",
        ]

    def cut_job(self, name: str, input: Sequence[str]) -> Job:
        """A segment cut from a file, encoded like the rest, without running it."""
        file = _join(self.work_dir, name)
        return Job(file, [*input, *self.encode, file])

    def cut(self, name: str, input: Sequence[str]) -> str:
        """A segment cut from a file, encoded like the rest."""
        job = self.cut_job(name, input)
        ffmpeg(job.args)
        return job.file

    def freeze_jobs(self, clip: str, at: float, length: float, name: str) -> list[Job]:
        """The two runs of a held frame: the frame taken, then held for `length` seconds."""
        frame = _join(self.work_dir, f"{name}.png")
        file = _join(self.work_dir, f"{name}.mp4")
        return [
            Job(frame, ["-ss", f"{at:.3f}", "-i", clip, "-frames:v", "1", frame]),
            Job(file, ["-loop", "1", "-t", f"{length:.3f}", "-i", frame, *self.encode, file]),
        ]

    def freeze(self, clip: str, at: float, length: float, name: str) -> str:
        """One frame of a clip, held still for a while."""
        jobs = self.freeze_jobs(clip, at, length, name)
        for job in jobs:
            ffmpeg(job.args)
        return jobs[-1].file

    def concat_list(self, segments: Sequence[str]) -> str:
        """The concat demuxer's list, forward slashes as ffmpeg wants them on Windows."""
        return "\n".join("file '" + file.replace("\\", "/") + "'" for file in segments)

    def concat_job(self, segments: Sequence[str], name: str) -> tuple[str, Job]:
        """Where the list goes and the join that reads it, without running it."""
        listing = _join(self.work_dir, f"{name}.txt")
        file = _join(self.work_dir, name)
        return listing, Job(file, ["-f", "concat", "-safe", "0", "-i", listing, "-c", "copy", file])

    def concat(self, segments: Sequence[str], name: str) -> str:
        """Join segments without another encode."""
        listing, job = self.concat_job(segments, name)
        with open(listing, "w", encoding="utf-8", newline="") as out:
            out.write(self.concat_list(segments))
        from urdido import cache

        cache.run("join", [job.file], job.args, lambda: ffmpeg(job.args),
                  inputs=[__file__, *segments], tools=["ffmpeg"])
        return job.file


def media(
    width: int,
    height: int,
    work_dir: str,
    fps: int = 30,
    encoder: Encoder | None = None,
) -> Media:
    """One video's media context; the encoder is probed when not given."""
    return Media(width, height, work_dir, fps, encoder or detect_encoder())
