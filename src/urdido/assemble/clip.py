"""One chapter as a clip of its own (D279), composed on the timeline (VM7), ported from
`chapterClip` in `turing/wordpress/bin/story-video.mjs`.

The clip is its title card, the action with the narrator's line over it, the result (played on
when she speaks over the action, held still otherwise) and the closing card. Where that runs past
the limit, the stretch between her line and the result, where nothing is said, plays faster until
it fits. Every length is read from its encode, as the JS reads it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from urdido import media as mediamod
from urdido.audio import mix
from urdido.cards import html as cardhtml
from urdido.edit.stretch import along, kept
from urdido.jsnum import fixed
from urdido.motion import pushin
from urdido.narration import Take, Takes
from urdido.sources.model import Chapter
from urdido.timeline import Builder


class ClipRefused(Exception):
    """A chapter whose lines alone run past the clip's limit."""


@dataclass
class ClipVideo:
    """What a chapter clip is built from: the recording, the cards, the takes and the bed."""

    name: str  # the files' base, `story`
    language: str
    voices: Sequence[str]  # the narrated languages
    frame: cardhtml.Frame
    vertical: bool
    webm: str
    chapters: Sequence[Chapter]
    takes: Takes
    theme: cardhtml.Theme
    card_count: int  # how many cards the video draws, a clip's own two last
    parts: str  # the work folder its pieces go to
    bed: mix.Bed | None = None
    duck: mix.Duck = field(default_factory=mix.Duck)
    loudness: mix.Loudness = field(default_factory=mix.Loudness)
    card_seconds: float = 2.5
    clip_limit: float = 58
    closing_seconds: float = 5
    voice_lead: float = 0.4
    voice_tail: float = 0.5
    encoder: str = "x264"

    def __post_init__(self):
        self.media = mediamod.media(self.frame.width, self.frame.height, self.parts, encoder=self.encoder)

    # -- the pieces, encoded ------------------------------------------------------------------

    def part(self, name: str) -> str:
        return os.path.join(self.parts, name)

    def still(self, i: int, length: float | None = None) -> str:
        """A card held for `length` s: in parallax over its moving hills when it has a text layer."""
        length = self.card_seconds if length is None else length
        file = self.part(f"card-{i}.mp4" if length == self.card_seconds else f"card-{i}-held-{fixed(length, 2)}.mp4")
        layer = lambda name: self.part(f"{name}.png")  # noqa: E731
        if not os.path.exists(layer(f"card-{i}-text")):
            mediamod.ffmpeg(["-loop", "1", "-t", fixed(length, 3), "-i", layer(f"card-{i}"), *self.media.encode, file])
            return file
        mediamod.ffmpeg(
            cardhtml.parallax_args(self.theme, self.frame, layer, i, length, file, self.media.video_codec(20))
        )
        return file

    def follow(self, file: str, chapter: Chapter, name: str) -> str:
        windows = pushin.windows(chapter, pushin.Frame(self.frame.width, self.frame.height), self.vertical)
        if not windows:
            return file
        followed = self.part(name)
        mediamod.ffmpeg(
            ["-i", file, "-vf", pushin.zoompan_filter(windows, pushin.Frame(self.frame.width, self.frame.height)),
             *self.media.video_codec(20), "-an", followed]
        )
        return followed

    def trimmed(self, clip: str, chapter: Chapter, name: str):
        stretches = kept(chapter, mediamod.seconds(clip))
        into = lambda t: along(stretches, t)  # noqa: E731
        if len(stretches) == 1:
            return clip, into
        pieces = [
            self.media.cut(f"{name}-{n}.mp4", ["-ss", fixed(a, 3), "-t", fixed(b - a, 3), "-i", clip])
            for n, (a, b) in enumerate(stretches)
        ]
        return self.media.concat(pieces, f"{name}.mp4"), into

    def needs(self, takes: Sequence[Take]) -> float:
        return max(t.length for t in takes) + self.voice_lead + self.voice_tail if takes else 0

    def best(self, chapter: Chapter) -> float:
        marks = chapter.marks
        moment = marks.highlight if marks.highlight is not None else chapter.clip.end - 0.8
        return max(0, moment - chapter.clip.start)

    # -- the clip --------------------------------------------------------------------------------

    def build(self, n: int) -> tuple[Builder, float]:
        """Chapter `n` (from 1) as a clip: its timeline, and how much faster the silent stretch
        plays."""
        i = n - 1
        chapter = self.chapters[i]
        start, end = chapter.clip.start, chapter.clip.end
        voice, told = chapter.marks.voice, chapter.marks.result
        base = f"{self.name}-chapter-{n}{'-vertical' if self.vertical else ''}"

        raw = self.media.cut(f"clip-{n}.mp4", ["-ss", fixed(start, 2), "-to", fixed(end, 2), "-i", self.webm])
        clip, into = self.trimmed(self.follow(raw, chapter, f"clip-{n}-followed.mp4"), chapter, f"clip-{n}-trimmed")
        clip_length = mediamod.seconds(clip)

        at = min(into(told.at - start if told else self.best(chapter)), clip_length - 0.1)
        line = self.takes.takes(voice.name, list(self.voices)) if voice else []
        line_at = into(max(0, voice.at - start)) if voice else 0
        spoken_until = min(at, line_at + self.needs(line))
        result = self.takes.takes(f"chapter-{n}-result", list(self.voices))
        held = self.needs(result) if result else self.card_seconds
        if told:
            held = clip_length - at
        fixed_part = self.card_seconds + spoken_until + held + self.closing_seconds
        silent = at - spoken_until
        if fixed_part + 1 > self.clip_limit:
            raise ClipRefused(
                f"chapter {n}'s lines alone run {fixed(fixed_part, 1)} s, past a clip's "
                f"{self.clip_limit:g} s: shorten them in the narration script."
            )
        speed = max(1, silent / (self.clip_limit - fixed_part))

        b = Builder(f"{base}.{self.language}", self.language, self.frame.width, self.frame.height,
                    chapter=n, speed=speed)
        for language in self.voices:
            b.speaks(language)

        def say(moment: float, takes: Sequence[Take]) -> None:
            for take in takes:
                b.say(take.language, moment + self.voice_lead, take.file, take.length, take.text)

        def piece(file: str) -> float:
            length = mediamod.seconds(file)
            b.part(file, length)
            return length

        piece(self.still(self.card_count - 2))
        clock = self.card_seconds
        say(clock + line_at, line)
        if spoken_until > 0:
            clock += piece(self.media.cut(f"clip-{n}-a.mp4", ["-t", fixed(spoken_until, 3), "-i", clip]))
        if silent > 0.05:
            file = self.part(f"clip-{n}-fast.mp4")
            encode = list(self.media.encode)
            k = encode.index("-vf") + 1
            encode[k] = f"setpts=(PTS-STARTPTS)/{fixed(speed, 3)},{encode[k]}"
            mediamod.ffmpeg(["-ss", fixed(spoken_until, 3), "-to", fixed(at, 3), "-i", clip, *encode, file])
            clock += piece(file)
        piece(
            self.media.cut(f"clip-{n}-result.mp4", ["-ss", fixed(at, 3), "-i", clip])
            if told
            else self.media.freeze(clip, at, held, f"clip-{n}-result")
        )
        say(clock, result)
        clock += held
        piece(self.still(self.card_count - 1, self.closing_seconds))
        clock += self.closing_seconds
        b.cue(self.card_seconds, clock - self.closing_seconds, i)
        b.bed(self.music_plan(b))
        return b, speed

    def music_plan(self, b: Builder) -> Mapping | None:
        """The bed as the plan records it: the track, where it starts, its trim, and each narrated
        language's ducking expression."""
        if self.bed is None or not os.path.exists(self.bed.file):
            return None
        envelope = {}
        for track in b.timeline.audio_tracks():
            if not track.name.startswith("A1 "):
                continue  # the sounds and the bed are not narration
            takes = [
                mix.Take(c.media_reference.target_url, c.metadata["videomaker"]["at"] - self.bed.start,
                         c.source_range.duration.to_seconds())
                for c in track if hasattr(c, "media_reference")
            ]
            if takes:
                envelope[track.name[3:]] = mix.duck_expression(takes, self.duck)
        return {
            "file": self.bed.file,
            "from": self.bed.start,
            "trimDb": mix.bed_trim(self.bed),
            "volume": self.duck.under,
            "duck": {"between": self.duck.between, "ramp": self.duck.ramp},
            "loudness": {"target": self.loudness.target, "peak": self.loudness.peak},
            "envelope": envelope,
        }
