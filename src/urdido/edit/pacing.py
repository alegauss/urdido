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


def warp(clip: float, need: float, pins: list[tuple[float, float, str]]) -> list[tuple[float, float]]:
    """VM87: a clip fitted to its lines piece by piece. Each pin is (clip second, line second, name):
    the moment a scene recorded, and the second its word is said. The clip plays at its own speed
    between two pins, so each moment lands on its word, and starts and ends with the lines.

    Returns the points (clip second, screen second) from (0, 0) to (clip, need). Refuses pins out of
    order, and a piece that would play slower than a quarter or faster than six times, which no
    edit hides: that is a scene to film again, or a word to pin elsewhere."""
    points = [(0.0, 0.0)]
    for at, on, name in sorted(pins):
        if not 0 < at < clip or not 0 < on < need:
            raise ValueError(f"anchor {name}: clip {at:.2f} s or line {on:.2f} s falls outside the scene "
                             f"({clip:.2f} s filmed, {need:.2f} s of lines)")
        if on <= points[-1][1]:
            raise ValueError(f"anchor {name}: its word comes before the previous anchor's ({on:.2f} s)")
        points.append((at, on))
    points.append((clip, need))
    for (c0, o0), (c1, o1) in zip(points, points[1:], strict=False):
        speed = (c1 - c0) / (o1 - o0)
        if not 0.25 <= speed <= 6:
            raise ValueError(f"the piece from clip {c0:.2f} s to {c1:.2f} s would play at {speed:.2f}x "
                             f"to fit {o1 - o0:.2f} s of lines; film it again or move an anchor")
    return points


def warp_setpts(points: list[tuple[float, float]]) -> str:
    """The points as one ffmpeg setpts expression: screen time as a piecewise-linear function of T."""
    def piece(i):
        (c0, o0), (c1, o1) = points[i], points[i + 1]
        return f"{o0:.4f}+(T-{c0:.4f})*{(o1 - o0) / (c1 - c0):.6f}"
    expr = piece(len(points) - 2)
    for i in range(len(points) - 3, -1, -1):
        expr = f"if(lt(T,{points[i + 1][0]:.4f}),{piece(i)},{expr})"
    return f"setpts='({expr})/TB'"


def fit_to_line(clip: float, need: float) -> Fit:
    """Fit a clip of `clip` seconds to lines that need `need` seconds of screen."""
    if clip <= 0:
        return Fit(1.0, need)
    if clip <= need:
        return Fit(1.0, need - clip)
    return Fit(clip / need, 0.0)
