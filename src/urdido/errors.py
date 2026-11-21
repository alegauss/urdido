"""What urdido raises when it cannot go on (UR24).

The library raises these and never exits: only `urdido.cli` turns one into a message
and an exit code, so a program that embeds urdido catches an exception rather than
losing its process. Each carries the remedy a person or an agent can act on, if any.

- `Refused`: an input cannot make the video (a stale take, a missing frame, a rejected
  clip); `RecordingRefused` is its oldest name.
- `DeclarationError`: the declaration itself is wrong (an unknown key, a bad value, an
  undeclared root).
- `MissingTool`: a program urdido runs is absent (ffmpeg, Docker, DaVinci Resolve).
"""

from __future__ import annotations


class UrdidoError(Exception):
    """Something urdido cannot do, with what would fix it."""

    def __init__(self, message: str, remedy: str = "") -> None:
        super().__init__(message)
        self.remedy = remedy

    def __str__(self) -> str:
        text = super().__str__()
        return f"{text}\n  remedy: {self.remedy}" if self.remedy else text


class Refused(UrdidoError):
    """An input that cannot make the video."""


class DeclarationError(Refused):
    """The declaration names something wrong or leaves something out."""


class MissingTool(UrdidoError):
    """A program urdido runs is not installed or not on PATH."""
