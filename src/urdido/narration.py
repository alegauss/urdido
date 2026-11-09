"""A video's narration takes, read as `video-maker/narration/takes.mjs` reads them (VM7).

The script names every line (the opening, each chapter's line over its action and the one about
its result, the closing), a take lives at `<dir>/<language>/<name>.mp3`, and it is current when
its provenance (`<take>.prov.json`) records the same spoken text, voice and model. Buying takes
stays in JS (`narration/buy.mjs`); the assembly only reads them.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Mapping

from videomaker import media


@dataclass(frozen=True)
class Take:
    language: str
    file: str
    length: float
    text: str


class Takes:
    def __init__(self, script: Mapping, folder: str):
        self.script = script
        self.folder = folder
        self.lines: dict[str, Mapping[str, str]] = {"intro": script["intro"]}
        for n, chapter in script["chapters"].items():
            self.lines[f"chapter-{n}"] = chapter["card"]
            self.lines[f"chapter-{n}-result"] = chapter["result"]
        self.lines["outro"] = script["outro"]

    def spoken(self, language: str | None, text: str) -> str:
        """What the voice says: each word of `pronounce` spelled as it sounds."""
        said = text
        for word, sound in (self.script.get("pronounce", {}).get(language) or {}).items():
            said = re.sub(rf"\b{word}\b", sound, said)
        return said

    def take_file(self, language: str, name: str) -> str:
        return os.path.join(self.folder, language, f"{name}.mp3")

    def current(self, file: str, language: str | None, text: str | None) -> bool:
        record = f"{file}.prov.json"
        if text is None or not (os.path.exists(file) and os.path.exists(record)):
            return False
        with open(record, encoding="utf-8") as f:
            prov = json.load(f)
        return (
            prov.get("prompt") == self.spoken(language, text)
            and (prov.get("details") or {}).get("voice") == self.script["voice"]
            and (prov.get("engine") or {}).get("model") == self.script["model"]
        )

    def takes(self, name: str, languages: list[str], current_language=None) -> list[Take]:
        """A line's current takes, in the given languages, with their lengths.

        `current_language` is what story-video.mjs passes to `current()`: None, so no
        pronunciation map applies (its narration has none)."""
        out = []
        for language in languages:
            file = self.take_file(language, name)
            text = (self.lines.get(name) or {}).get(language)
            if self.current(file, current_language, text):
                out.append(Take(language, file, media.seconds(file), text))
        return out
