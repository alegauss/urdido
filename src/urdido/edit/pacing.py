"""A scene clip fitted to the lines spoken over it (`pacing: narration`, VM10).

A clip shorter than its lines plays as filmed and holds its last frame until they end; a longer
one plays faster, as a whole, so it ends with them. Nothing is cut: the moment a line describes
is always on screen, sooner rather than missing. A scene carries no marks of where it is silent,
so the speed is the same across it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fit:
    """How a clip plays under its lines: `speed` times as fast, then its last frame `hold` s."""

    speed: float
    hold: float

    def length(self, clip: float) -> float:
        return clip / self.speed + self.hold


def fit_to_line(clip: float, need: float) -> Fit:
    """Fit a clip of `clip` seconds to lines that need `need` seconds of screen."""
    if clip <= 0:
        return Fit(1.0, need)
    if clip <= need:
        return Fit(1.0, need - clip)
    return Fit(clip / need, 0.0)
