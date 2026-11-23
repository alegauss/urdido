"""A video filmed scene by scene, assembled with every line over its own scene (VM10).

Each scene of `cenas.json` carries the lines spoken over it: `intro`, a chapter's line (and its
result line, when the chapter has no result scene of its own), a result scene's line, `outro`.
A filmed scene is fitted to its lines (`edit.pacing`); a scene not yet filmed is a card held for
them, in the video's theme, so the video assembles while filming is unfinished.
"""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from urdido import media as mediamod
from urdido.assemble.video import Intro
from urdido.cards import html as cardhtml
from urdido.edit.pacing import Fit, fit_to_line, warp, warp_setpts
from urdido.jsnum import fixed
from urdido.narration import Take, Takes
from urdido.sources.scenes import Scene
from urdido.timeline import Builder

_CHAPTER = re.compile(r"^chapter-(\d+)$")


def anchor_word(spec: str | Mapping, language: str, scene: str = "") -> str | Mapping:
    """An [anchors] word in the narration's language (UR67).

    `word` is what the take says at the mark: a word (`"console"`), a table naming one occurrence
    (`{text, occurrence, context}`), or, for a video narrated in more than one language, a table
    keyed by language whose values are either of those (`{ "pt-BR" = "Aí", en = "Then" }`). A
    language the table does not name is refused by name, never matched against another's words.
    """
    if isinstance(spec, Mapping) and "text" not in spec:
        if language not in spec:
            from urdido.sources.model import RecordingRefused

            raise RecordingRefused(f"{scene}: [anchors] word has no {language} entry "
                                   f"({', '.join(spec) or 'none'})")
        return spec[language]
    return spec


@dataclass
class ScenesVideo:
    name: str
    language: str  # the narration's, `pt-BR`
    frame: cardhtml.Frame
    scenes: Sequence[Scene]
    takes: Takes
    script: Mapping
    theme: cardhtml.Theme
    words: Mapping  # the video's card words in this language
    parts: str
    encoder: str | None = None
    voice_lead: float = 0.4
    line_gap: float = 0.4
    voice_tail: float = 0.5
    card_seconds: float = 2.5
    # The opening animation and where its usable part starts: played before the first scene with
    # its own sound, the bed starting after it (as the WordPress demo's opening does).
    intro: Intro | None = None
    placed: list = field(default_factory=list)  # (scene, kind, start, length, takes)
    # VM87: per scene, the moments pinned to words (`[{mark, take, word}]`, video.toml's [anchors])
    anchors: Mapping = field(default_factory=dict)
    warps: dict = field(default_factory=dict)
    opening: float = 0.0  # how long the opening runs, where the bed starts

    def __post_init__(self):
        self.media = mediamod.media(self.frame.width, self.frame.height, self.parts, encoder=self.encoder)

    def lines_of(self, scene: Scene) -> list[str]:
        """The takes spoken over a scene."""
        names = {s.name for s in self.scenes}
        found = _CHAPTER.match(scene.name)
        if found and f"{scene.name}-result" not in names:
            return [scene.name, f"{scene.name}-result"]
        return [scene.name]

    def need(self, takes: Sequence[Take]) -> float:
        if not takes:
            return self.card_seconds
        spoken = sum(t.length for t in takes) + self.line_gap * (len(takes) - 1)
        return self.voice_lead + spoken + self.voice_tail

    def card_page(self, scene: Scene) -> str:
        css = cardhtml.style(self.theme, self.frame)
        w = self.words
        found = re.match(r"^chapter-(\d+)", scene.name)
        if found:
            n = found.group(1)
            title = ((self.script["chapters"].get(n) or {}).get("title") or {}).get(self.language, n)
            return cardhtml.card(css, f"{w['chapter']} {n}", title, w["store"], pill=True)
        if scene.name == "outro" and w.get("tryLinks"):
            # The closing card the WordPress demo ends on: where to try it, the address big.
            return cardhtml.links_card(self.theme, css, self.frame, w["tryIt"], w["tryTitle"], w["tryLinks"])
        return cardhtml.card(css, w["brand"], w["what"], w["line"])

    def compose(self, render: bool = False) -> Builder:
        """The video on a timeline. With `render`, every piece is encoded and placed at its encoded
        length; without, at the length its fit gives, nothing encoded."""
        b = Builder(f"{self.name}.{self.language}", self.language, self.frame.width, self.frame.height)
        b.speaks(self.language)
        # First what each scene is: its lines, how long they need, its fit or its card.
        planned = []
        pages = {}
        for n, scene in enumerate(self.scenes):
            takes = [t for name in self.lines_of(scene)
                     for t in self.takes.takes(name, [self.language], current_language=self.language)]
            need = self.need(takes)
            file = self.part(f"scene-{n}-{scene.name}.mp4")
            fit = fit_to_line(scene.seconds, scene.seconds if scene.source == "illustrated" else need) if scene.filmed else None
            if scene.filmed and self.anchors.get(scene.name):
                self.warps[scene.name] = self.anchored(scene, takes, need)
                fit = Fit(scene.seconds / need, 0.0)
            still = None if scene.filmed else self.part(f"scene-{n}-{scene.name}.png")
            if still:
                pages[os.path.basename(still)[:-4]] = self.card_page(scene)
            planned.append((scene, takes, need, file, fit, still))
        if render:
            # Every card drawn in one browser session, then every piece encoded side by side: they
            # depend on nothing but their own scene or card.
            if pages:
                from urdido.cards.render import render as draw

                draw(pages, self.frame, self.parts)
            from urdido import progress

            progress.plan("source clips", len(planned))
            mediamod.pool([
                (lambda s=scene, f=fit, o=file: progress.run("source clips", s.name, lambda: self.encode_fit(s, f, o))) if fit else
                (lambda p=still, k=need, o=file: progress.run("source clips", os.path.basename(o), lambda: self.encode_still(p, k, o)))
                for scene, takes, need, file, fit, still in planned
            ])
        clock = 0.0
        if self.intro is not None:
            opening = self.part("opening.mp4")
            if render or not os.path.exists(opening):
                from urdido import cache

                cache.run("opening", [opening], [self.intro.start, self.frame.width, self.frame.height,
                                                self.media.fps, self.media.encoder],
                          lambda: self.media.cut("opening.mp4", ["-ss", fixed(self.intro.start, 3), "-i", self.intro.file]),
                          inputs=[__file__, mediamod.__file__, self.intro.file], tools=["ffmpeg"])
            length = mediamod.seconds(opening)
            b.shots([(opening, length)])
            b.sound(self.intro.file, self.intro.start, 0.0, length)
            clock = self.opening = length
        for scene, takes, need, file, fit, still in planned:
            if fit:
                length = mediamod.seconds(file) if render else fit.length(scene.seconds)
                b.scene(scene.file, file, length, scene.seconds, fit.speed, fit.hold)
                kind = "scene"
            else:
                length = mediamod.seconds(file) if render else need
                b.card(still, file, length)
                kind = "card"
            at = clock + self.voice_lead
            for take in takes:
                b.say(take.language, at, take.file, take.length, take.text)
                at += take.length + self.line_gap
            self.placed.append((scene, kind, clock, length, takes))
            clock += length
        return b.finish()

    def anchored(self, scene: Scene, takes: Sequence[Take], need: float) -> list[tuple[float, float]]:
        """The scene's warp: each declared mark at the second its word is said over the scene."""
        from pathlib import Path

        from urdido import keywords
        from urdido.sources.model import RecordingRefused

        starts, at = {}, self.voice_lead
        for take in takes:
            starts[Path(take.file).stem] = (take, at)
            at += take.length + self.line_gap
        marks = dict(scene.marks)
        pins = []
        for anchor in self.anchors[scene.name]:
            mark, name = anchor["mark"], anchor["take"]
            if mark not in marks:
                raise RecordingRefused(f"{scene.name}: [anchors] names mark {mark!r}, which cenas.json does "
                                       f"not record ({', '.join(marks) or 'none'}); film the scene again")
            if name not in starts:
                raise RecordingRefused(f"{scene.name}: [anchors] names take {name!r}, not spoken over this "
                                       f"scene ({', '.join(starts)})")
            take, start = starts[name]
            spoken = anchor_word(anchor["word"], self.language, scene.name)
            word = keywords.anchor(Path(take.file), spoken, aliases=keywords.aliases(self.script, self.language))
            pins.append((float(marks[mark]), start + word, mark))
        try:
            return warp(scene.seconds, need, pins)
        except ValueError as error:
            raise RecordingRefused(f"{scene.name}: {error}") from None

    def part(self, name: str) -> str:
        return os.path.join(self.parts, name)

    def encode_fit(self, scene: Scene, fit: Fit, file: str) -> None:
        """The clip at its speed, its last frame held, encoded like every piece."""
        if scene.source == "illustrated" and fit.speed == 1 and not fit.hold:
            # These clips were already composed at the exact output frame rate and size.
            # Keep their frame cadence instead of stretching and encoding them a second time.
            shutil.copyfile(scene.file, file)
            return
        encode = list(self.media.encode)
        k = encode.index("-vf") + 1
        if self.frame.height > self.frame.width:
            # A 9:16 cut of a 16:9 scene (VM12): its centre, full height; a scene carries no focus
            # box to follow.
            encode[k] = f"crop=ih*{self.frame.width}/{self.frame.height}:ih,{encode[k]}"
        timing = f"setpts=PTS/{fixed(fit.speed, 4)}"
        if scene.name in self.warps:
            timing = warp_setpts(self.warps[scene.name])
        if fit.hold > 0:
            timing += f",tpad=stop_mode=clone:stop_duration={fixed(fit.hold, 3)}"
        encode[k] = f"{timing},{encode[k]}"
        mediamod.ffmpeg(["-i", scene.file, *encode, file])

    def encode_still(self, still: str, length: float, file: str) -> None:
        """A drawn card held for `length` seconds, encoded like every piece."""
        mediamod.ffmpeg(["-loop", "1", "-t", fixed(length, 3), "-i", still, *self.media.encode, file])
