"""The chapter model (VM8): what every source is read into, whatever shape it was filmed in."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from urdido.errors import Refused


class RecordingRefused(Refused):
    """A source that cannot make the video, with what to do about it."""


@dataclass(frozen=True)
class Clip:
    """What a chapter plays: `file` from `start` to `end`, in seconds into the file."""

    file: str
    start: float
    end: float

    @property
    def length(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class Line:
    """A narration line placed in the recording: the take's name and where it is heard from."""

    name: str
    at: float


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class Focus:
    """An element the camera eases in on from `at`, its box in the recording's frame; a mark with
    no box is a release, which only ends the push-in before it."""

    at: float
    box: Box | None = None


@dataclass(frozen=True)
class Span:
    """A wait the story marked to be cut (an AI answer streaming in), `start` to `end`."""

    start: float
    end: float


@dataclass(frozen=True)
class Marks:
    """What the recording marked in a chapter, in the file's own time."""

    voice: Line | None = None
    result: Line | None = None
    highlight: float | None = None
    focus: tuple[Focus, ...] = ()
    skip: tuple[Span, ...] = ()


@dataclass(frozen=True)
class Chapter:
    """One chapter: its number, its title as the source names it, its clip and its marks.

    `pacing` holds what a source says about how the chapter is timed beyond its marks (a clip
    held, looped or sped to its take, VM10); the chaptered recording leaves it empty.
    """

    n: int
    title: str
    clip: Clip
    marks: Marks = Marks()
    pacing: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Recording:
    """A source read and accepted: its language and its chapters, in order."""

    language: str | None
    chapters: tuple[Chapter, ...]
