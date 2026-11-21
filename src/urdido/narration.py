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
from collections.abc import Mapping
from dataclasses import dataclass

from urdido import media


@dataclass(frozen=True)
class Take:
    language: str
    file: str
    length: float
    text: str


def stretched(source: str, tempo: float) -> str:
    """The take `tempo` times as fast, pitch kept, with its word times scaled to match (VM72).

    eleven_v3 ignores the `speed` delivery setting, so a faster narration is made from the
    bought take: `<language>/tempo-<t>/<name>.mp3` beside it, rebuilt whenever the take changes.
    Its `.words.json` comes from the take's own transcript divided by the tempo and is keyed to
    the stretched file's hash, so no second transcription is bought. Without a current transcript
    of the take, the stretched one is left without words and the build says so as it always does.
    """
    import subprocess

    from urdido.cache import file_hash

    source_path = os.path.abspath(source)
    folder = os.path.join(os.path.dirname(source_path), f"tempo-{tempo:g}")
    name = os.path.splitext(os.path.basename(source_path))[0]
    out = os.path.join(folder, f"{name}.mp3")
    record = os.path.join(folder, f"{name}.mp3.tempo.json")
    source_hash = file_hash(source_path)
    try:
        with open(record, encoding="utf-8") as f:
            fresh = json.load(f) == {"source_sha256": source_hash, "tempo": tempo} and os.path.exists(out)
    except (OSError, ValueError):
        fresh = False
    if not fresh:
        os.makedirs(folder, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", source_path, "-filter:a", f"atempo={tempo}",
                        "-c:a", "libmp3lame", "-q:a", "2", out], check=True)
        with open(record, "w", encoding="utf-8") as f:
            json.dump({"source_sha256": source_hash, "tempo": tempo}, f)
    words_in = os.path.splitext(source_path)[0] + ".words.json"
    words_out = os.path.splitext(out)[0] + ".words.json"
    try:
        with open(words_in, encoding="utf-8-sig") as f:
            heard = json.load(f)
    except (OSError, ValueError):
        return out
    if heard.get("sha256") == source_hash:
        scaled = {**heard, "sha256": file_hash(out), "tempo": tempo, "source_sha256": source_hash,
                  "words": [{**w, "start": round(w["start"] / tempo, 3), "end": round(w["end"] / tempo, 3)}
                            for w in heard["words"]]}
        with open(words_out, "w", encoding="utf-8") as f:
            json.dump(scaled, f, ensure_ascii=False, indent=2)
            f.write("\n")
    return out


class Takes:
    def __init__(self, script: Mapping, folder: str, tempo: float = 1.0):
        self.script = script
        self.folder = folder
        self.tempo = float(tempo)
        if not 0.5 <= self.tempo <= 2.0:
            raise ValueError(f"narration tempo {tempo} is outside 0.5-2.0")
        self.lines: dict[str, Mapping[str, str]] = {"intro": script["intro"]}
        for n, chapter in script["chapters"].items():
            self.lines[f"chapter-{n}"] = chapter["card"]
            self.lines[f"chapter-{n}-result"] = chapter["result"]
        self.lines["outro"] = script["outro"]

    def spoken(self, language: str | None, text: str) -> str:
        """What the voice says: each word of `pronounce` spelled as it sounds."""
        said = text
        for word, sound in (self.script.get("pronounce", {}).get(language) or {}).items():
            said = re.sub(rf"\b{re.escape(word)}\b", lambda _, sound=sound: sound, said)
        return said

    def source_file(self, language: str, name: str) -> str:
        """The take as bought, whatever the tempo."""
        return os.path.join(self.folder, language, f"{name}.mp3")

    def take_file(self, language: str, name: str) -> str:
        """The take the video hears: the bought one, or at a tempo its stretched copy (VM72)."""
        source = self.source_file(language, name)
        if self.tempo == 1.0 or not os.path.exists(source):
            return source
        return stretched(source, self.tempo)

    def current(self, file: str, language: str | None, text: str | None) -> bool:
        folder = os.path.dirname(file)
        if os.path.basename(folder).startswith("tempo-"):
            # A stretched copy is current when the take it was made from is (VM72).
            file = os.path.join(os.path.dirname(folder), os.path.basename(file))
        record = f"{file}.prov.json"
        if text is None or not (os.path.exists(file) and os.path.exists(record)):
            return False
        with open(record, encoding="utf-8-sig") as f:
            prov = json.load(f)
        recorded_hash = (prov.get("artefact") or {}).get("sha256")
        if recorded_hash:
            from urdido.cache import file_hash

            if recorded_hash != file_hash(file):
                return False
        settings = {"stability": "stability", "similarity": "similarity_boost", "style": "style", "speed": "speed"}
        for key, field in settings.items():
            if self.script.get(key) is not None and (prov.get("details") or {}).get("delivery", {}).get(field) != float(self.script[key]):
                return False
        return (
            str(prov.get("prompt", "")).strip() == self.spoken(language, text).strip()
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
