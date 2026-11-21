"""A video's DaVinci Resolve project: its OTIO timeline handed over (VM14).

The `.otio` timeline is the video's source of truth: the MP4 is rendered from it without
Resolve, and Resolve only ever receives a copy (the Alexandre, 2026-11-09). The project is
`<video>.project/`: the timeline as `<video>.otio`, named after the video, beside a `media/`
folder holding every file it points at, its references rewritten to that folder so a moved
folder relinks there, the narration's captions, and `finish.lua`, which Resolve runs to import
it all (the template beside this module, its names and paths filled in).

The recording is transcoded once to H.264, since a Playwright VP8 WebM is not something every
editor reads, and the music bed is one looped, trimmed, faded clip the video's length on A2.
What Resolve does not read of the timeline (the `urdido.push-in` and `time-map` effects,
the bed's ducking) is a limit of the copy, not of the video.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Mapping
from pathlib import Path

import opentimelineio as otio

from urdido import media as mediamod
from urdido.jsnum import fixed, number
from urdido.timeline import KEY, _range

FINISH = Path(__file__).with_name("finish.lua")


def _uri(path: str) -> str:
    return Path(path).resolve().as_uri()


def resolved(path: str, roots: Mapping[str, str]) -> str:
    """A plan's portable path (`<video>/parts/...`) on this machine."""
    for name, root in roots.items():
        path = path.replace(f"<{name}>", root)
    return os.path.normpath(path)


def export_project(
    timeline: otio.schema.Timeline,
    project_dir: str,
    name: str,
    *,
    recording: str | None = None,
    captions: str | None = None,
    resolve: Mapping | None = None,
    roots: Mapping[str, str] | None = None,
    encoder: str = "x264",
) -> str:
    """Write `<project_dir>/<name>.otio` with its media, captions and finish.lua; return the .otio."""
    roots = roots or {}
    resolve = resolve or {}
    media_dir = os.path.join(project_dir, "media")
    os.makedirs(media_dir, exist_ok=True)
    timeline = otio.adapters.read_from_string(otio.adapters.write_to_string(timeline))  # a copy
    timeline.name = name
    timeline.metadata[KEY] = {**timeline.metadata.get(KEY, {}), "event": resolve.get("event")}
    copied: dict[str, str] = {}

    def copy(source: str) -> str:
        if source in copied:
            return copied[source]
        here = resolved(source, roots)
        if recording and os.path.normcase(here) == os.path.normcase(resolved(recording, roots)):
            file = os.path.join(media_dir, "recording.mp4")
            mediamod.ffmpeg(["-i", here, "-vf", "fps=30,format=yuv420p",
                             *mediamod.video_codec(encoder, 18), "-an", file])
        else:
            file = os.path.join(media_dir, f"{len(copied)}-{os.path.basename(here)}")
            shutil.copyfile(here, file)
        copied[source] = file
        return file

    for clip in timeline.find_clips():
        reference = clip.media_reference
        if isinstance(reference, otio.schema.ExternalReference) and reference.target_url:
            reference.target_url = _uri(copy(reference.target_url))

    music = timeline.metadata[KEY].get("music")
    if music and os.path.exists(resolved(music["file"], roots)):
        total = max(track.duration().to_seconds() for track in timeline.video_tracks())
        start = music["from"]
        length = total - start
        bed = os.path.join(media_dir, "music-bed.m4a")
        mediamod.ffmpeg([
            "-stream_loop", "-1", "-i", resolved(music["file"], roots), "-t", fixed(length, 3), "-af",
            f"volume={number(music['trimDb'])}dB,afade=t=in:d=2,afade=t=out:st={fixed(max(0, length - 3), 3)}:d=3",
            "-c:a", "aac", "-b:a", "192k", bed,
        ])
        track = otio.schema.Track(name="A2", kind=otio.schema.TrackKind.Audio)
        if start > 0:
            track.append(otio.schema.Gap(source_range=_range(0, start)))
        clip = otio.schema.Clip(name="music-bed.m4a",
                                media_reference=otio.schema.ExternalReference(target_url=_uri(bed)),
                                source_range=_range(0, length))
        clip.metadata[KEY] = {"bed": True, "volume": music.get("volume")}
        track.append(clip)
        timeline.tracks.append(track)

    otio_file = os.path.join(project_dir, f"{name}.otio")
    otio.adapters.write_to_file(timeline, otio_file)

    srt = None
    if captions and os.path.exists(captions):
        srt = os.path.join(project_dir, os.path.basename(captions))
        shutil.copyfile(captions, srt)
    lua = FINISH.read_text(encoding="utf-8")
    for key, value in {
        "__NAME__": name, "__OTIO__": otio_file, "__SRT__": srt or "", "__RENDER_DIR__": project_dir,
        "__PRESET__": resolve.get("fairlightPreset", ""),
    }.items():
        lua = lua.replace(key, value)
    with open(os.path.join(project_dir, "finish.lua"), "w", encoding="utf-8", newline="") as f:
        f.write(lua)
    return otio_file


def main(argv: list[str] | None = None) -> int:
    """`urdido.export`: a plan's project, for story-video.mjs's `--project`."""
    import argparse

    from urdido.timeline import from_plan

    p = argparse.ArgumentParser(prog="urdido.export", description=main.__doc__)
    p.add_argument("--plan", required=True, help="the build's <video>.plan.json")
    p.add_argument("--project-dir", required=True)
    p.add_argument("--name", required=True, help="the project's name, the video's")
    p.add_argument("--recording", help="the recording to transcode, as the plan names it")
    p.add_argument("--captions", help="the narration's SRT")
    p.add_argument("--resolve", help="the video's Resolve declaration (event, Fairlight preset)")
    p.add_argument("--root", action="append", default=[], help="name=folder, for the plan's <name> paths")
    p.add_argument("--encoder", default=os.environ.get("STORY_ENCODER") or mediamod.detect_encoder())
    a = p.parse_args(argv)
    with open(a.plan, encoding="utf-8") as f:
        timeline = from_plan(json.load(f))
    resolve = {}
    if a.resolve:
        with open(a.resolve, encoding="utf-8") as f:
            resolve = json.load(f)
    roots = dict(r.split("=", 1) for r in a.root)
    print(export_project(timeline, a.project_dir, a.name, recording=a.recording, captions=a.captions,
                         resolve=resolve, roots=roots, encoder="nvenc" if a.encoder == "nvenc" else "x264"))
    return 0
