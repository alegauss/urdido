"""Short 9:16 cuts made of chosen chapters of the 16:9 scenes (VM12).

A selection takes the long cut's scenes for the chapters it names (a chapter's result scene comes
with it), fits each to its lines as the long cut does, reframes it to 9:16 (`ScenesVideo` crops a
landscape scene to its centre; cards are drawn upright), burns the narration's captions in above
the bottom fifth where vertical players draw their controls, and mixes the voice over the cut's
own music bed. It is an OTIO timeline like every cut, so it opens in Resolve too.

A selection over its limit first tightens the breaths around its lines; one still over is built
all the same and says by how much, since only shorter lines or fewer chapters can fix it.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, replace
from typing import Sequence

import opentimelineio as otio

from videomaker import captions as cap
from videomaker import media as mediamod
from videomaker.assemble.scenes import ScenesVideo
from videomaker.audio import mix
from videomaker.cards.html import Frame
from videomaker.cuts.render import VERTICAL_CAPTION_STYLE
from videomaker.timeline import KEY, plan

VERTICAL = Frame(1080, 1920)
# The breaths a selection over its limit is allowed down to.
TIGHT = {"voice_lead": 0.2, "line_gap": 0.2, "voice_tail": 0.3}


def chapter_of(scene: str) -> str:
    return re.sub(r"-result$", "", scene)


@dataclass
class Short:
    name: str
    file: str
    length: float
    limit: float
    timeline: otio.schema.Timeline
    scenes: list[str]  # the scenes placed, in order

    @property
    def over(self) -> float:
        return max(0.0, self.length - self.limit)


def selection(
    video: ScenesVideo,
    name: str,
    chapters: Sequence[str],
    music: str | None,
    out: str,
    limit: float = 60,
    track_language: str = "por",
) -> Short:
    """Build the short `name` from `chapters` of `video`'s scenes into `out`."""
    parts = os.path.join(video.parts, name)
    os.makedirs(parts, exist_ok=True)
    chosen = [s for s in video.scenes if chapter_of(s.name) in chapters]
    short = replace(video, frame=VERTICAL, scenes=chosen, parts=parts, placed=[])
    planned = short.compose(render=False)
    if _length(planned) > limit:
        short = replace(short, placed=[], **TIGHT)
    timeline = short.compose(render=True)

    pieces = [c.metadata[KEY]["file"] for track in timeline.video_tracks()
              for c in track if isinstance(c, otio.schema.Clip)]
    joined = short.media.concat(pieces, f"{name}-joined.mp4")
    total = mediamod.seconds(joined)

    data = plan(timeline)
    language = video.language
    placed = data["spoken"].get(language, [])
    cues = cap.narration_cues(placed, cap.VERTICAL_CAPTION_WIDTH)
    srt = f"{name}.{language}.srt"
    with open(os.path.join(out, srt), "w", encoding="utf-8", newline="") as f:
        f.write(cap.srt(cues))
    picture = os.path.join(parts, f"{name}-captioned.mp4")
    # Run from the captions' folder: a Windows path inside a filter needs escaping that a bare
    # file name does not.
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-vf",
         f"subtitles={srt}:force_style='{VERTICAL_CAPTION_STYLE}'", *short.media.video_codec(20), "-an", picture],
        cwd=out, stdin=subprocess.DEVNULL, check=True,
    )

    voice = os.path.join(parts, f"voice.{language}.m4a")
    takes = [mix.Take(p["file"], p["at"], p["length"]) for p in placed]
    bed = mix.Bed(music) if music and os.path.exists(music) else None
    mix.voice_track(takes, total, voice, parts, bed=bed, name=f"mix.{language}")
    file = os.path.join(out, f"{name}.{language}.mp4")
    mediamod.ffmpeg(["-i", picture, "-i", voice, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                     "-c:a", "aac", "-b:a", "160k", "-metadata:s:a:0", f"language={track_language}", file])
    timeline.metadata[KEY]["limit"] = limit
    return Short(name, file, mediamod.seconds(file), limit, timeline, [s.name for s, *_ in short.placed])


def _length(timeline: otio.schema.Timeline) -> float:
    return max(track.duration().to_seconds() for track in timeline.video_tracks())
