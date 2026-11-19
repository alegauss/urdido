"""The time maps of a chapter's clip (VM13), ported from `video-maker/edit/stretch.mjs`: the waits
a story marked cut out, and where a moment lands once they are."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from urdido.sources.model import Chapter


@dataclass(frozen=True)
class SkipKeep:
    """A moment of a wait kept either side, so the cut reads as the answer arriving rather than a
    jump; a wait shorter than `least` stays."""

    before: float = 0.6
    after: float = 0.3
    least: float = 1.0


def kept(chapter: Chapter, length: float, keep: SkipKeep = SkipKeep()) -> list[tuple[float, float]]:
    """The stretches of a chapter's clip the video keeps, in seconds from its start: all of it,
    less the waits it marked."""
    start = chapter.clip.start
    stretches = []
    since = 0.0
    for wait in chapter.marks.skip:
        a = wait.start - start + keep.before
        b = min(length, wait.end - start - keep.after)
        if b - a >= keep.least and a > since:
            stretches.append((since, a))
            since = b
    stretches.append((since, length))
    return stretches


def along(stretches: Sequence[tuple[float, float]], t: float) -> float:
    """Where a moment of the chapter (seconds from its start, as recorded) falls once its waits
    are cut."""
    return sum(max(0.0, min(b, t) - a) for a, b in stretches)
