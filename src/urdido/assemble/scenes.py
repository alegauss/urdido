"""A video filmed scene by scene, assembled with every line over its own scene (VM10).

Each scene of `cenas.json` carries the lines spoken over it: `intro`, a chapter's line (and its
result line, when the chapter has no result scene of its own), a result scene's line, `outro`.
A filmed scene is fitted to its lines (`edit.pacing`); a scene not yet filmed is a card held for
them, in the video's theme, so the video assembles while filming is unfinished.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from videomaker import media as mediamod
from videomaker.cards import html as cardhtml
from videomaker.edit.pacing import Fit, fit_to_line
from videomaker.jsnum import fixed
from videomaker.narration import Take, Takes
from videomaker.sources.scenes import Scene
from videomaker.timeline import Builder

_CHAPTER = re.compile(r"^chapter-(\d+)$")


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
    placed: list = field(default_factory=list)  # (scene, kind, start, length, takes)

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
        return cardhtml.card(css, w["brand"], w["what"], w["line"])

    def compose(self, render: bool = False) -> Builder:
        """The video on a timeline. With `render`, every piece is encoded and placed at its encoded
        length; without, at the length its fit gives, nothing encoded."""
        b = Builder(f"{self.name}.{self.language}", self.language, self.frame.width, self.frame.height)
        b.speaks(self.language)
        clock = 0.0
        pages = {}
        for n, scene in enumerate(self.scenes):
            takes = [t for name in self.lines_of(scene)
                     for t in self.takes.takes(name, [self.language], current_language=self.language)]
            need = self.need(takes)
            if scene.filmed:
                fit = fit_to_line(scene.seconds, need)
                file = self.part(f"scene-{n}-{scene.name}.mp4")
                if render:
                    self.encode_fit(scene, fit, file)
                length = mediamod.seconds(file) if render else fit.length(scene.seconds)
                b.scene(scene.file, file, length, scene.seconds, fit.speed, fit.hold)
                kind = "scene"
            else:
                still = self.part(f"scene-{n}-{scene.name}.png")
                pages[os.path.basename(still)[:-4]] = self.card_page(scene)
                file = self.part(f"scene-{n}-{scene.name}.mp4")
                length = need
                if render:
                    self.encode_card(still, need, file, pages)
                    length = mediamod.seconds(file)
                b.card(still, file, length)
                kind = "card"
            at = clock + self.voice_lead
            for take in takes:
                b.say(take.language, at, take.file, take.length, take.text)
                at += take.length + self.line_gap
            self.placed.append((scene, kind, clock, length, takes))
            clock += length
        return b.finish()

    def part(self, name: str) -> str:
        return os.path.join(self.parts, name)

    def encode_fit(self, scene: Scene, fit: Fit, file: str) -> None:
        """The clip at its speed, its last frame held, encoded like every piece."""
        encode = list(self.media.encode)
        k = encode.index("-vf") + 1
        if self.frame.height > self.frame.width:
            # A 9:16 cut of a 16:9 scene (VM12): its centre, full height; a scene carries no focus
            # box to follow.
            encode[k] = f"crop=ih*{self.frame.width}/{self.frame.height}:ih,{encode[k]}"
        timing = f"setpts=PTS/{fixed(fit.speed, 4)}"
        if fit.hold > 0:
            timing += f",tpad=stop_mode=clone:stop_duration={fixed(fit.hold, 3)}"
        encode[k] = f"{timing},{encode[k]}"
        mediamod.ffmpeg(["-i", scene.file, *encode, file])

    def encode_card(self, still: str, length: float, file: str, pages: Mapping[str, str]) -> None:
        from videomaker.cards.render import render

        name = os.path.basename(still)[:-4]
        render({name: pages[name]}, self.frame, self.parts)
        mediamod.ffmpeg(["-loop", "1", "-t", fixed(length, 3), "-i", still, *self.media.encode, file])
