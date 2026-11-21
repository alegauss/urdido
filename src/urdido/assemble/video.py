"""A full video composed on the timeline (VM7), ported from the main build of
the first demo's `story-video.mjs`.

The opening animation with its own sound; the opening card, held while the narrator's first
line runs, its shots cut at her pauses; each chapter's card and its clip, the waits cut, her line
placed where the recording marked it, the result held still while she talks about it (or played
on, where she spoke over the action); the closing card with its shots, then alone. Dissolves
join a card to what is beside it. Every length is read from its encode.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field

from urdido import media as mediamod
from urdido.assemble.clip import ClipVideo
from urdido.edit.stretch import along, kept
from urdido.jsnum import fixed, number
from urdido.motion import pushin
from urdido.timeline import Builder

_SILENCE_END = re.compile(r"silence_end: ([\d.]+)")


def pauses(file: str) -> list[float]:
    """Where a take falls silent between phrases, in seconds from its start."""
    log = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", file, "-af", "silencedetect=n=-35dB:d=0.3", "-f", "null", "-"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stderr
    return [float(m) for m in _SILENCE_END.findall(log)]


@dataclass
class Intro:
    """The opening animation and where its usable part starts."""

    file: str
    start: float = 0.0


@dataclass
class FullVideo(ClipVideo):
    """A whole video: ClipVideo's sources, plus the opening and the footage around the cards."""

    intro: Intro | None = None
    broll: Sequence[str] = field(default_factory=list)  # footage, photos and pages, in turn
    footage: Sequence[str] = field(default_factory=list)  # the b-roll clips alone
    title_seconds: float = 3
    shot_seconds: float = 4
    final_seconds: float = 6
    dissolve_seconds: float = 0.5

    # -- shots -----------------------------------------------------------------------------------

    def ken_burns(self, image: str, length: float, n: int, name: str) -> str:
        """A still with slow motion: a zoom in and a drift sideways."""
        file = self.part(name)
        w, h = self.frame.width, self.frame.height
        frames = max(1, int(length * 30 + 0.5))
        side = [0, 1, 0.5][n % 3]
        mediamod.ffmpeg([
            "-loop", "1", "-i", image, "-vf",
            f"scale={w * 4}:{h * 4}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w * 4}:{h * 4},"
            f"zoompan=z='1+0.12*on/{frames}':x='(iw-iw/zoom)*{number(side)}':"
            f"y='(ih-ih/zoom)/2':d={frames}:s={w}x{h}:fps=30,format=yuv420p",
            "-frames:v", str(frames), *self.media.video_codec(20), "-an", file,
        ])
        return file

    def footage_shot(self, video: str, length: float, name: str) -> str:
        """Footage from a few seconds in, where a clip has settled, looped if it is too short."""
        file = self.part(name)
        w, h = self.frame.width, self.frame.height
        mediamod.ffmpeg([
            "-stream_loop", "-1", "-ss", "2", "-i", video, "-t", fixed(length, 3), "-vf",
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30,format=yuv420p",
            *self.media.video_codec(20), "-an", file,
        ])
        return file

    def shot(self, source: str, length: float, n: int, name: str) -> str:
        return self.footage_shot(source, length, name) if source.endswith(".mp4") else self.ken_burns(
            source, length, n, name
        )

    # -- the video -------------------------------------------------------------------------------

    def compose(self) -> Builder:
        """The whole video on a timeline, and its dissolves."""
        b = Builder(f"{self.name}.{self.language}", self.language, self.frame.width, self.frame.height)
        for language in self.voices:
            b.speaks(language)
        self._clips = []  # (clip, lane, still, source, file)
        self._clock = 0.0
        music_from = 0.0

        def say(at: float, takes) -> None:
            for take in takes:
                b.say(take.language, at + self.voice_lead, take.file, take.length, take.text)

        def place(file: str, make) -> float:
            length = mediamod.seconds(file)
            clip = make(length)
            meta = clip.metadata["videomaker"]
            self._clips.append((clip, meta["lane"], bool(meta.get("still")), meta["source"], file))
            return length

        def card(i: int, length: float | None = None) -> float:
            file = self.still(i, length)
            return place(file, lambda n: b.card(self.part(f"card-{i}.png"), file, n))

        def title_card(i: int, name: str, shots: Sequence[str]) -> list[str]:
            line = self.takes.takes(name, list(self.voices))
            length = max(self.card_seconds, self.needs(line))
            say(self._clock, line)
            self._clock += length
            if not shots or length < self.title_seconds + self.shot_seconds:
                card(i, length)
                return []
            longest = line[0]
            for take in line[1:]:
                if take.length > longest.length:
                    longest = take
            cuts, last = [], self.title_seconds
            for pause in pauses(longest.file):
                at = pause + self.voice_lead
                if at - last >= self.shot_seconds and length - at >= 2:
                    cuts.append(at)
                    last = at
            card(i, self.title_seconds)
            bounds = [self.title_seconds, *cuts, length]
            shown = []
            for n in range(len(bounds) - 1):
                source = shots[n % len(shots)]
                shown.append(source)
                file = self.shot(source, bounds[n + 1] - bounds[n], n, f"card-{i}-shot-{n}.mp4")
                place(file, lambda k, f=file: b.shots([(f, k)])[0])
            return shown

        if self.intro is not None:
            opening = self.media.cut("opening.mp4", ["-ss", fixed(self.intro.start, 3), "-i", self.intro.file])
            length = place(opening, lambda k: b.shots([(opening, k)])[0])
            b.sound(self.intro.file, self.intro.start, self._clock, length)
            self._clock += length
            music_from = self._clock

        # Each chapter's clip and its push-ins, the build's heaviest encodes, made side by side
        # before the timeline: they depend on nothing but the recording (as story-video.mjs did).
        def chapter_clip(n: int, chapter) -> str:
            raw = self.media.cut(
                f"chapter-{n}.mp4", ["-ss", fixed(chapter.clip.start, 2), "-to", fixed(chapter.clip.end, 2), "-i", self.webm]
            )
            return self.follow(raw, chapter, f"chapter-{n}-followed.mp4")

        chapter_clips = mediamod.pool(
            [lambda n=n, c=c: chapter_clip(n, c) for n, c in enumerate(self.chapters, 1)]
        )

        opening_shots = title_card(0, "intro", self.broll)
        for i, chapter in enumerate(self.chapters):
            n = i + 1
            clip = chapter_clips[i]
            card(n)
            self._clock += self.card_seconds
            start = chapter.clip.start
            from_ = self._clock
            voice, told = chapter.marks.voice, chapter.marks.result
            clip_length = mediamod.seconds(clip)
            stretches = kept(chapter, clip_length)
            into = lambda t, s=stretches: along(s, t)  # noqa: E731
            if voice:
                say(from_ + into(max(0, voice.at - start)), self.takes.takes(voice.name, list(self.voices)))
            in_recording = float(fixed(start, 2))
            result = self.takes.takes(f"chapter-{n}-result", list(self.voices))
            if told and result:
                say(from_ + into(told.at - start), result)
            at = self.best(chapter) if result and not told else None
            if at is not None:
                inside = next((s for s in stretches if s[0] <= at < s[1]), None)
                if inside is None:
                    inside = next((s for s in reversed(stretches) if s[0] <= at), stretches[0])
                at = min(at, inside[1] - 0.1, clip_length - 0.1)
            k = 0
            for a, b_ in stretches:
                stops = [a, at, b_] if at is not None and a < at < b_ else [a, b_]
                for p, q in zip(stops, stops[1:], strict=False):
                    if len(stretches) == 1 and len(stops) == 2:
                        piece = clip
                    else:
                        piece = self.media.cut(
                            f"chapter-{n}-{k}.mp4", ["-ss", fixed(p, 3), "-t", fixed(q - p, 3), "-i", clip]
                        )
                        k += 1
                    p3 = float(fixed(p, 3))
                    self._clock += place(
                        piece, lambda length, f=piece, p3=p3, at=in_recording, i=i: b.chapter(self.webm, at + p3, i, p3, f, length)
                    )
                    placed = self._clips[-1][0]
                    windows = pushin.windows(chapter, pushin.Frame(self.frame.width, self.frame.height), self.vertical)
                    if windows:
                        b.effect(placed, "push-in", {"windows": [vars(w) for w in windows]})
                    if len(stretches) > 1:
                        b.effect(placed, "time-map", {"kept": [list(s) for s in stretches]})
                    if q == at:
                        length = self.needs(result)
                        held = self.media.freeze(clip, at, length, f"chapter-{n}-result")
                        png = held[: -len(".mp4")] + ".png"
                        place(held, lambda k_, h=held, s=png: b.held(s, h, k_))
                        say(self._clock, result)
                        self._clock += length
            b.cue(from_, self._clock, i)

        closing_shots = [c for c in reversed(self.footage) if c not in opening_shots] + [
            s for s in reversed(list(self.broll)) if s not in self.footage
        ]
        last = self.card_count - 1
        title_card(last, "outro", closing_shots)
        card(last, self.final_seconds)
        self._clock += self.final_seconds

        self._dissolve(b)
        bed = self.bed
        if bed is not None:
            from urdido.audio.mix import Bed

            self.bed = Bed(bed.file, music_from, bed.reference)
        b.bed(self.music_plan(b))
        self.bed = bed
        return b

    def last_frame(self, file: str, n: int) -> str:
        frame = self.part(f"dissolve-{n}-last.png")
        mediamod.ffmpeg(["-sseof", "-0.1", "-i", file, "-frames:v", "1", frame])
        return frame

    def _dissolve(self, b: Builder) -> None:
        """Where a card meets the recording or a shot, and between shots: the still crossfades over
        the first or last half second of the piece beside it. Inside a chapter the cuts stay hard."""
        marks = [{"out": None, "in": None} for _ in self._clips]
        for n in range(len(self._clips) - 1):
            (_, lane_a, still_a, source_a, file_a), (_, lane_b, still_b, source_b, _) = self._clips[n], self._clips[n + 1]
            if lane_a == "V1" and lane_b == "V1":
                continue
            if still_b:
                marks[n]["in"] = source_b
            else:
                marks[n + 1]["out"] = source_a if still_a else self.last_frame(file_a, n)
        for (clip, *_), mark in zip(self._clips, marks, strict=False):
            b.dissolve(clip, into=mark["in"], out_of=mark["out"])
