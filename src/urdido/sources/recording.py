"""One long recording with chapter marks, read into the chapter model (VM8).

`chapters.json` is read as Turing's specs write it, unchanged: `record` (a recording, not a test
run), `language` (the store it played in, D298) and `chapters`, each with its `title`
(`3. Asks…`), `start`, `end` and the marks (`voice`, `result`, `highlight`, `focus`, `skip`).
It is refused as `story-video.mjs` refuses it, with the command to run.
"""

from __future__ import annotations

import json
import os
import re
from typing import Iterable, Mapping

from videomaker.sources.model import (
    Box, Chapter, Clip, Focus, Line, Marks, Recording, RecordingRefused, Span,
)

_NUMBERED = re.compile(r"^(\d+)\.\s*(.*)$", re.DOTALL)


def _line(data: Mapping | None) -> Line | None:
    return Line(data["name"], data["at"]) if data else None


def _chapter(webm: str, n: int, data: Mapping) -> Chapter:
    found = _NUMBERED.match(data["title"])
    if not found:
        raise RecordingRefused(f"chapter {n}'s title does not start with its number: {data['title']!r}")
    marks = Marks(
        voice=_line(data.get("voice")),
        result=_line(data.get("result")),
        highlight=data.get("highlight"),
        focus=tuple(
            Focus(f["at"], Box(**f["box"]) if f.get("box") else None) for f in data.get("focus", [])
        ),
        skip=tuple(Span(s["from"], s["to"]) for s in data.get("skip", [])),
    )
    return Chapter(int(found.group(1)), found.group(2), Clip(webm, data["start"], data["end"]), marks)


def chaptered_recording(
    webm: str,
    chapters_json: str,
    *,
    language: str,
    chapters: int,
    record_command: str = "the recording",
    sources: Iterable[str] = (),
) -> Recording:
    """Read a chaptered recording, or refuse it.

    - `language`: the video's; a recording made in another store's language is refused.
    - `chapters`: how many the story has; fewer means the story failed part way.
    - `record_command`: what a person runs to record again, quoted in every refusal.
    - `sources`: the story and specs it was recorded from; one newer than the recording means a
      re-record was skipped.
    """
    if not (os.path.exists(chapters_json) and os.path.exists(webm)):
        raise RecordingRefused(f"no recording yet: run `{record_command}` first.")
    with open(chapters_json, encoding="utf-8") as f:
        data = json.load(f)
    recorded = data.get("language")
    if data.get("record") and recorded != language:
        raise RecordingRefused(
            f"the recording is in {recorded}, not {language}: run `{record_command}` again."
            if recorded
            else f"the recording does not say its language: run `{record_command}` again."
        )
    if not data.get("record"):
        raise RecordingRefused(f"the last story run was the test, not the recording: run `{record_command}`.")
    if len(data["chapters"]) != chapters:
        raise RecordingRefused(
            f"the recording has {len(data['chapters'])} of {chapters} chapters: "
            "the story failed part way. Re-record it."
        )
    recorded_at = os.path.getmtime(chapters_json)
    for source in sources:
        if os.path.getmtime(source) > recorded_at:
            raise RecordingRefused(f"{source} changed after the recording: run `{record_command}` again.")
    return Recording(recorded, tuple(_chapter(webm, n, c) for n, c in enumerate(data["chapters"], 1)))
