"""Captions, the YouTube chapter list and chapter titles (VM4).

Ported from the caption and chapter-list writers of `turing/wordpress/bin/story-video.mjs`
(`stamp`, `subtitles`, `captionCues`, `narrationCaptions`, `chapterList`). A narrated video's
captions are its narration, cut into cues of two short lines; a silent cut is captioned with its
chapter titles. Titles come from the narration script (`chapters[n].title` by language, and
`introTitle` for the opening's line in the chapter list) and otherwise from the recording's own
step titles. Languages are whichever the plan and the script name, never a fixed pair.

Everything here returns text; writing it is the caller's.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

# A caption's lines: at most two of about this many characters, so a cue reads at a glance.
# Narrower on a vertical cut, whose frame is a little over half as wide.
CAPTION_WIDTH = 42
VERTICAL_CAPTION_WIDTH = 26

_TAGS = re.compile(r"\[[^\]]*\]\s*")
_SPACE = re.compile(r"\s+")
_NUMBERED = re.compile(r"^(\d+)\.\s*(.*)$", re.DOTALL)


def _js_round(x: float) -> int:
    """Math.round: halves go up, where Python's round() goes to the even one."""
    return math.floor(x + 0.5)


def _units(text: str) -> int:
    """A string's length as JavaScript counts it, in UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def stamp(t: float) -> str:
    """An SRT time, `hh:mm:ss,mmm`."""
    ms = _js_round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class Chapter:
    """A chapter as the recording names it: `3. Asks the Site assistant…` is 3 and the rest."""

    number: str
    name: str

    @classmethod
    def parse(cls, title: str) -> "Chapter":
        found = _NUMBERED.match(title)
        if not found:
            raise ValueError(f"a chapter title starts with its number: {title!r}")
        return cls(found.group(1), found.group(2))


def chapters_of(recording: Mapping) -> list[Chapter]:
    """The chapters a recording's `chapters.json` lists, in order."""
    return [Chapter.parse(chapter["title"]) for chapter in recording["chapters"]]


def chapter_title(script: Mapping, chapter: Chapter, language: str) -> str:
    """The script's title for a chapter in a language, or the recording's own."""
    titles = (script.get("chapters", {}).get(chapter.number) or {}).get("title") or {}
    return titles.get(language, chapter.name)


def intro_title(script: Mapping, language: str) -> str:
    """The opening's line in the chapter list."""
    return (script.get("introTitle") or {}).get(language, "Intro")


def languages_of(script: Mapping) -> list[str]:
    """The languages a script is written in, as its opening names them."""
    return list(script.get("intro", {}).keys())


def caption_cues(placed: Mapping, width: int = CAPTION_WIDTH) -> list[Cue]:
    """A narrated line as cues: its stage directions out, its words in cues of two short lines,
    each on screen for its share of the take, by its characters."""
    words = [w for w in _SPACE.split(_TAGS.sub("", str(placed.get("text") or ""))) if w]
    rows: list[str] = []
    for word in words:
        if rows and _units(f"{rows[-1]} {word}") <= width:
            rows[-1] = f"{rows[-1]} {word}"
        else:
            rows.append(word)
    blocks = ["\n".join(rows[i : i + 2]) for i in range(0, len(rows), 2)]
    total = sum(_units(block) for block in blocks) or 1
    cues = []
    start = placed["at"]
    for block in blocks:
        end = start + (placed["length"] * _units(block)) / total
        cues.append(Cue(start, end, block))
        start = end
    return cues


def narration_cues(placed: Iterable[Mapping], width: int = CAPTION_WIDTH) -> list[Cue]:
    """One language's takes as cues, in the order they are heard."""
    return [cue for take in sorted(placed, key=lambda p: p["at"]) for cue in caption_cues(take, width)]


def srt(cues: Sequence[Cue]) -> str:
    return "\n".join(
        f"{n}\n{stamp(cue.start)} --> {stamp(cue.end)}\n{cue.text}\n" for n, cue in enumerate(cues, 1)
    )


def vtt(cues: Sequence[Cue]) -> str:
    return "WEBVTT\n\n" + "\n".join(
        f"{stamp(cue.start).replace(',', '.')} --> {stamp(cue.end).replace(',', '.')}\n{cue.text}\n"
        for cue in cues
    )


def chapter_cues(
    cues: Iterable[Mapping], chapters: Sequence[Chapter], script: Mapping, language: str
) -> list[Cue]:
    """A silent cut's captions: one cue per chapter, `n. Title`, while the chapter shows."""
    out = []
    for cue in cues:
        chapter = chapters[cue["chapter"]]
        title = chapter_title(script, chapter, language)
        out.append(Cue(cue["from"], cue["to"], f"{chapter.number}. {title}"))
    return out


def chapter_list(
    cues: Iterable[Mapping], chapters: Sequence[Chapter], script: Mapping, language: str
) -> str:
    """The chapters as YouTube reads them from a description, `0:00 Title` a line."""

    def at(s: float) -> str:
        return f"{math.floor(s / 60)}:{math.floor(s % 60):02d}"

    lines = [f"0:00 {intro_title(script, language)}"]
    for cue in cues:
        chapter = chapters[cue["chapter"]]
        lines.append(f"{at(cue['from'])} {chapter.number}. {chapter_title(script, chapter, language)}")
    return "\n".join(lines) + "\n"


def base_name(plan: Mapping) -> str:
    """The plan's video without its language suffix: `story.pt-BR` is `story`."""
    video, suffix = plan["video"], f".{plan['language']}"
    return video[: -len(suffix)] if video.endswith(suffix) else video


def caption_files(
    plan: Mapping,
    chapters: Sequence[Chapter],
    script: Mapping,
    short_cues: Sequence[Mapping] | None = None,
    title_languages: Sequence[str] | None = None,
) -> dict[str, str]:
    """Every caption file a build writes beside its video, by file name.

    - A narrated language: `<name>.<language>.srt` and `.vtt`, its narration.
    - A cut with no voice: `<name>.<language>.srt` per title language, its chapter titles.
    - A full video (not a chapter clip): `<name>.<language>.chapters.txt` per plan language.
    - `short_cues`, the teaser's chapters: `<name>-30s.<language>.srt` per title language.

    The title languages are the video's to declare; the script's languages when it does not.
    """
    name = base_name(plan)
    titled = list(title_languages) if title_languages is not None else languages_of(script)
    size = plan["size"]
    width = VERTICAL_CAPTION_WIDTH if size["height"] > size["width"] else CAPTION_WIDTH
    spoken: Mapping[str, list] = plan.get("spoken", {})
    narrated = {language: placed for language, placed in spoken.items() if placed}
    files: dict[str, str] = {}

    if "chapter" not in plan:
        for language in spoken:
            files[f"{name}.{language}.chapters.txt"] = chapter_list(
                plan["cues"], chapters, script, language
            )
    if narrated:
        for language, placed in narrated.items():
            cues = narration_cues(placed, width)
            files[f"{name}.{language}.srt"] = srt(cues)
            files[f"{name}.{language}.vtt"] = vtt(cues)
    else:
        for language in titled:
            files[f"{name}.{language}.srt"] = srt(chapter_cues(plan["cues"], chapters, script, language))
    if short_cues is not None:
        for language in titled:
            files[f"{name}-30s.{language}.srt"] = srt(chapter_cues(short_cues, chapters, script, language))
    return files
