"""The cuts a video is rendered into (VM9), ported from `turing/wordpress/bin/story-video.mjs`:
the full cut with its dissolves, the 30 s teaser, a chapter clip and its vertical cut. Each is a
timeline (VM7) rendered by one path: its pieces joined, each narrated language mixed over the bed
(VM5), and its captions (VM4) muxed in, or burned in on a vertical cut, whose player draws its
controls over a caption track.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

import opentimelineio as otio

from urdido import captions as cap
from urdido import media as mediamod
from urdido.assemble.clip import ClipVideo
from urdido.assemble.video import FullVideo
from urdido.audio import mix
from urdido.jsnum import fixed
from urdido.timeline import KEY, Builder, pieces as pieces_of, plan

TAB, NEWLINE = chr(9), chr(10)

# Where a vertical cut's captions sit, in libass's units for an SRT (288 to the frame's height):
# above the bottom fifth, where Shorts, Reels and TikTok draw the title, the buttons and the
# progress bar (D280); on a box, since they sit over the page's own text.
VERTICAL_CAPTION_STYLE = (
    "FontName=Arial,FontSize=11,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H50000000,"
    "BorderStyle=3,Outline=1.2,Shadow=0,Alignment=2,MarginL=14,MarginR=14,MarginV=64"
)


@dataclass
class Renderer:
    """Renders a composed video's cuts into `out`, beside its `parts`."""

    video: ClipVideo
    out: str
    script: Mapping
    title_languages: Sequence[str] = ("en", "pt-BR")
    # How ffmpeg names each language on a track.
    track_languages: Mapping[str, str] = field(default_factory=lambda: {"en": "eng", "pt-BR": "por"})
    dissolve_seconds: float = 0.5
    teaser_intro: float = 2
    teaser_seconds: float = 3
    # Where the build keeps what it decided (VM17): `write_plan(name, plan)` for the teaser's plan,
    # `portable(text)` for the paths a mix graph names.
    write_plan: "Callable[[str, dict], None] | None" = None
    portable: "Callable[[str], str] | None" = None

    @property
    def m(self):
        return self.video.media

    def part(self, name: str) -> str:
        return self.video.part(name)

    # -- dissolves -------------------------------------------------------------------------------

    def blend_span(self, file: str, start: float, length: float, image: str, end: str, name: str) -> str:
        """A stretch of a clip with a still crossfading over one end of it."""
        d = self.dissolve_seconds
        fade = (
            f"fade=t=out:st=0:d={d:g}:alpha=1" if end == "out"
            else f"fade=t=in:st={fixed(max(0, length - d), 3)}:d={d:g}:alpha=1"
        )
        w, h = self.video.frame.width, self.video.frame.height
        blended = self.part(name)
        mediamod.ffmpeg([
            *(["-ss", fixed(start, 3)] if start > 0 else []), "-t", fixed(length, 3), "-i", file,
            "-loop", "1", "-t", fixed(length, 3), "-i", image,
            "-filter_complex",
            f"[1:v]scale={w}:{h},fps=30,format=yuva420p,{fade}[still];[0:v][still]overlay=shortest=1,format=yuv420p[v]",
            "-map", "[v]", *self.m.video_codec(20), "-an", blended,
        ])
        return blended

    def copy_span(self, file: str, start: float, to: float | None, name: str) -> str:
        """A stretch of a clip copied as encoded, cut on its keyframes."""
        copied = self.part(name)
        mediamod.ffmpeg([
            *(["-ss", fixed(start, 3)] if start > 0 else []), "-i", file,
            *([] if to is None else ["-t", fixed(to - start, 3)]),
            "-c", "copy", "-an", "-avoid_negative_ts", "make_zero", copied,
        ])
        return copied

    def dissolve_piece(self, file: str, out_of: str | None, into: str | None, n: int) -> list[str]:
        """A piece with the still fading out over its first half second and in over its last; only
        the half second blended is encoded again, the rest copied on the keyframes."""
        step = mediamod.KEY_EVERY / 30
        pieces = [file]
        if out_of:
            length = mediamod.seconds(file)
            pieces = (
                [self.blend_span(file, 0, step, out_of, "out", f"dissolve-{n}-out-head.mp4"),
                 self.copy_span(file, step, None, f"dissolve-{n}-out-rest.mp4")]
                if length >= 2 * step
                else [self.blend_span(file, 0, length, out_of, "out", f"dissolve-{n}-out.mp4")]
            )
        if into:
            last = pieces.pop()
            length = mediamod.seconds(last)
            key_at = math.floor((length - self.dissolve_seconds) / step) * step  # as Math.floor
            if key_at > 0:
                pieces += [
                    self.copy_span(last, 0, key_at, f"dissolve-{n}-in-head.mp4"),
                    self.blend_span(last, key_at, length - key_at, into, "in", f"dissolve-{n}-in-tail.mp4"),
                ]
            else:
                pieces.append(self.blend_span(last, 0, length, into, "in", f"dissolve-{n}-in.mp4"))
        return pieces

    # -- sound and captions ----------------------------------------------------------------------

    def voices(self, timeline: otio.schema.Timeline, total: float, music: Mapping | None) -> list[tuple[str, str]]:
        """Each narrated language's mix, a track the video's length."""
        sounds = [
            mix.Sound(c.media_reference.target_url, c.source_range.start_time.to_seconds(),
                      c.metadata[KEY]["at"], c.source_range.duration.to_seconds())
            for track in timeline.audio_tracks() if track.name == "A3"
            for c in track if isinstance(c, otio.schema.Clip)
        ]
        out = []
        for track in timeline.audio_tracks():
            if not track.name.startswith("A1 "):
                continue
            takes = [
                mix.Take(c.media_reference.target_url, c.metadata[KEY]["at"], c.source_range.duration.to_seconds())
                for c in track if isinstance(c, otio.schema.Clip)
            ]
            if not takes:
                continue
            language = track.name[3:]
            file = self.part(f"voice.{language}.m4a")
            bed = None
            if music is not None and os.path.exists(music["file"]):
                bed = mix.Bed(music["file"], music["from"])
            if self.portable is not None:
                self.write_graph(language, takes, total, sounds, bed, music)
            mix.voice_track(
                takes, total, file, self.video.parts, sounds=sounds, bed=bed,
                trim_db=music["trimDb"] if music else None, duck=self.video.duck,
                loudness=self.video.loudness, name=f"mix.{language}",
            )
            out.append((language, file))
        return out

    def write_graph(self, language, takes, total, sounds, bed, music) -> None:
        """The mix as it runs, its paths portable: the oracle the golden check holds (VM25)."""
        built = mix.mix_graph(takes, total, sounds, bed, music["trimDb"] if music else 0.0, self.video.duck)
        data = {"total": float(fixed(total, 3)), "inputs": [self.portable(a) for a in built.inputs],
                "graph": [self.portable(f) for f in built.filters]}
        with open(self.part(f"mix.{language}.graph.json"), "w", encoding="utf-8", newline="") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=TAB) + NEWLINE)

    def write(self, files: Mapping[str, str]) -> None:
        for name, text in files.items():
            with open(os.path.join(self.out, name), "w", encoding="utf-8", newline="") as f:
                f.write(text)

    def finish(self, joined: str, name: str, voices: Sequence[tuple[str, str]], subtitles: Sequence[tuple[str, str]]) -> str:
        """The joined video with its voice and caption tracks."""
        file = os.path.join(self.out, f"{name}.{self.video.language}.mp4")
        lang = self.track_languages
        mediamod.ffmpeg([
            "-i", joined,
            *[a for _, f in subtitles for a in ("-i", f)],
            *[a for _, f in voices for a in ("-i", f)],
            "-map", "0:v",
            *[a for i in range(len(voices)) for a in ("-map", f"{i + 1 + len(subtitles)}:a")],
            *[a for i in range(len(subtitles)) for a in ("-map", str(i + 1))],
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-c:s", "mov_text",
            *[a for i, (l, _) in enumerate(voices) for a in (f"-metadata:s:a:{i}", f"language={lang[l]}")],
            *[a for i, (l, _) in enumerate(subtitles) for a in (f"-metadata:s:s:{i}", f"language={lang[l]}")],
            file,
        ])
        return file

    def _captions(self, data: Mapping, short_cues=None) -> dict[str, str]:
        chapters = [cap.Chapter(str(c.n), c.title) for c in self.video.chapters]
        files = cap.caption_files(data, chapters, self.script, short_cues=short_cues,
                                  title_languages=list(self.title_languages))
        self.write(files)
        return files

    def _subtitles(self, name: str, data: Mapping, files: Mapping[str, str]) -> list[tuple[str, str]]:
        narrated = [l for l, placed in data["spoken"].items() if placed]
        languages = narrated or list(self.title_languages)
        return [(l, os.path.join(self.out, f"{name}.{l}.srt")) for l in languages if f"{name}.{l}.srt" in files]

    # -- the cuts --------------------------------------------------------------------------------

    def full(self, builder: Builder, teaser: bool = True) -> list[str]:
        """The full cut, with its dissolves, and the teaser when the video declares one."""
        assert isinstance(self.video, FullVideo)
        data = plan(builder.timeline)
        clips = sorted(
            ((start, c) for track in builder.timeline.video_tracks() for start, c in _placed(track)),
            key=lambda p: p[0],
        )
        joined_files = mediamod.pool([
            (lambda c=c, n=n: self.dissolve_piece(
                c.metadata[KEY]["file"], c.metadata[KEY].get("dissolve", {}).get("out"),
                c.metadata[KEY].get("dissolve", {}).get("in"), n))
            for n, (_, c) in enumerate(clips)
        ])
        joined = self.m.concat([f for files in joined_files for f in files], "joined.mp4")
        total = mediamod.seconds(joined)
        voices = self.voices(builder.timeline, total, data["music"])

        short, short_cues = self.teaser_pieces() if teaser else (None, None)
        if teaser and self.write_plan is not None:
            self.write_plan(f"{self.video.name}-30s", {
                "video": f"{self.video.name}-30s.{self.video.language}",
                "language": self.video.language,
                "size": {"width": self.video.frame.width, "height": self.video.frame.height},
                "pieces": [{"file": f, "length": mediamod.seconds(f)} for f in short],
                "cues": short_cues,
            })
        files = self._captions(data, short_cues=short_cues)
        base = self.video.name
        video = self.finish(joined, base, voices, self._subtitles(base, data, files))
        if not teaser:
            return [video]
        teaser_data = {**data, "spoken": {l: [] for l in data["spoken"]}}
        teaser = self.finish(self.m.concat(short, "joined-30s.mp4"), f"{base}-30s", [],
                             self._subtitles(f"{base}-30s", teaser_data, files))
        return [video, teaser]

    def teaser_pieces(self):
        """Each chapter's last seconds, where its result shows, between a short opening and the
        closing card, with no cards between."""
        v = self.video
        short = [self.m.cut("short-intro.mp4", ["-t", f"{self.teaser_intro:g}", "-i", v.still(0)])]
        cues, clock = [], self.teaser_intro
        for i, chapter in enumerate(v.chapters):
            clip = self.m.cut(f"short-{i + 1}.mp4", [
                "-ss", fixed(max(0, v.best(chapter) + 0.8 - self.teaser_seconds), 2),
                "-t", f"{self.teaser_seconds:g}", "-i", self.part(f"chapter-{i + 1}.mp4"),
            ])
            short.append(clip)
            length = mediamod.seconds(clip)
            cues.append({"from": clock, "to": clock + length, "chapter": i})
            clock += length
        short.append(v.still(v.card_count - 1))
        return short, cues

    def clip(self, builder: Builder) -> str:
        """A chapter clip: its pieces joined, its voice, its captions; burned in when vertical."""
        data = plan(builder.timeline)
        files_in_order = pieces_of(builder.timeline)
        name = data["video"][: -len(f".{self.video.language}")]
        joined = self.m.concat(files_in_order, f"{name}-joined.mp4")
        total = mediamod.seconds(joined)
        voices = self.voices(builder.timeline, total, data["music"])
        files = self._captions(data)
        if not self.video.vertical:
            return self.finish(joined, name, voices, self._subtitles(name, data, files))
        picture = joined
        narrated = [l for l, placed in data["spoken"].items() if placed]
        if narrated:
            picture = self.part(f"{name}-captioned.mp4")
            # Run from the captions' folder: a Windows path inside a filter needs escaping that a
            # bare file name does not.
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-vf",
                 f"subtitles={name}.{narrated[0]}.srt:force_style='{VERTICAL_CAPTION_STYLE}'",
                 *self.m.video_codec(20), "-an", picture],
                cwd=self.out, stdin=subprocess.DEVNULL, check=True,
            )
        file = os.path.join(self.out, f"{name}.{self.video.language}.mp4")
        mediamod.ffmpeg([
            "-i", picture, *[a for _, f in voices for a in ("-i", f)], "-map", "0:v",
            *[a for i in range(len(voices)) for a in ("-map", f"{i + 1}:a")],
            "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
            *[a for i, (l, _) in enumerate(voices) for a in (f"-metadata:s:a:{i}", f"language={self.track_languages[l]}")],
            file,
        ])
        return file


def _placed(track):
    clock = 0.0
    for item in track:
        if isinstance(item, otio.schema.Clip):
            yield clock, item
        clock += item.source_range.duration.to_seconds()


def outputs_line(file: str) -> str:
    """A finished file as the golden runner's outputs.txt lists it: length and streams."""
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height:stream_tags=language",
         "-of", "json", file],
        capture_output=True, text=True, check=True,
    ).stdout)
    streams = ", ".join(
        s["codec_type"] + (f" {s['width']}x{s['height']}" if s.get("width") else "")
        + (f" {s['tags']['language']}" if (s.get("tags") or {}).get("language") else "")
        for s in probe["streams"]
    )
    return f"{os.path.basename(file)} {fixed(float(probe['format']['duration']), 3)}s {streams}"
