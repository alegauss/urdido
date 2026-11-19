"""A video filmed scene by scene, one clip per narration take, read from its `cenas.json` (VM10).

Viglet Shio's promo films each scene apart from the voice: `recordings/<pt|en>/<scene>.webm`,
listed in `recordings/<pt|en>/cenas.json` by the source that made it (`story-scenes.mjs` for the
console and site, `story-terminal.mjs` for the agent's session). A scene listed `filmed: false`
has no clip yet; the assembly holds a card for its lines instead, so the video assembles while
filming is unfinished. A clip's length is measured from the file, never taken from the list.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from videomaker import media
from videomaker.sources.model import RecordingRefused


@dataclass(frozen=True)
class Scene:
    """One scene: its id (`intro`, `chapter-2`, `chapter-7-result`), its clip and its length when
    filmed, the source that made it, and why not when it is not."""

    name: str
    file: str | None = None
    seconds: float | None = None
    source: str | None = None
    note: str | None = None
    # VM87: the moments the scene recorded, in clip seconds (`{"setup": 8.1, "console": 15.2}`)
    marks: tuple = ()

    @property
    def filmed(self) -> bool:
        return self.file is not None


def scene_clips(cenas_json: str) -> list[Scene]:
    """The scenes a `cenas.json` lists, in order, each filmed clip measured. A listed clip that is
    not on disk is refused: the list and the folder disagree."""
    folder = os.path.dirname(os.path.dirname(os.path.abspath(cenas_json)))
    with open(cenas_json, encoding="utf-8") as f:
        data = json.load(f)
    scenes = []
    for entry in data["scenes"]:
        if entry.get("filmed") is False or not entry.get("file"):
            scenes.append(Scene(entry["scene"], note=entry.get("note")))
            continue
        file = os.path.join(folder, entry["file"])
        if not os.path.exists(file):
            raise RecordingRefused(f"{entry['scene']}: {entry['file']} is listed in cenas.json but not on disk")
        scenes.append(Scene(entry["scene"], file, media.seconds(file), entry.get("source", "scenes"),
                            marks=tuple(sorted((entry.get("marks") or {}).items()))))
    return scenes
