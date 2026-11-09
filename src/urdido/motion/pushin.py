"""The push-in that follows the action (D292, VM13), ported from `video-maker/motion/pushin.mjs`.

For each element a chapter marked, the frame eases in on that element's box while the step runs
and back out before the next. Pure functions of the frame and the chapter's marks: the MP4's
zoompan and the Resolve project's transform keyframes are both drawn from them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence

from videomaker.sources.model import Chapter


@dataclass(frozen=True)
class PushIn:
    """The most the frame zooms (text stays sharp from a 1080p source), the room kept around the
    element, how long a move takes (`ease` at least, `slow` at most, a `hold` between), and how
    much the clip is enlarged before zoompan, which crops at whole input pixels."""

    cap: float = 1.6
    margin: float = 1.25
    ease: float = 0.8
    slow: float = 2.5
    hold: float = 0.5
    over: int = 2


@dataclass(frozen=True)
class Window:
    """One push-in, in seconds from the chapter's start: its zoom and the centre it moves to."""

    start: float
    end: float
    zoom: float
    cx: float
    cy: float
    ease: float


@dataclass(frozen=True)
class Frame:
    width: int
    height: int


def windows(chapter: Chapter, frame: Frame, vertical: bool = False, push: PushIn = PushIn()) -> list[Window]:
    """A chapter's push-ins: one per focused element it holds long enough. A vertical cut is
    already a phone's page, so it has none; a focus mark with no box only ends the one before."""
    if vertical:
        return []
    start, end = chapter.clip.start, chapter.clip.end
    focus = chapter.marks.focus
    out = []
    for n, mark in enumerate(focus):
        if mark.box is None:
            continue
        box = mark.box
        w_from = mark.at - start
        w_to = (focus[n + 1].at if n + 1 < len(focus) else end) - start
        zoom = min(push.cap, frame.width / (box.width * push.margin), frame.height / (box.height * push.margin))
        if not (zoom >= 1.1 and w_to - w_from >= 2 * push.ease + push.hold):
            continue
        out.append(
            Window(
                w_from,
                w_to,
                zoom,
                min(frame.width, max(0, box.x + box.width / 2)),
                min(frame.height, max(0, box.y + box.height / 2)),
                min(push.slow, max(push.ease, (w_to - w_from - push.hold) / 2)),
            )
        )
    return out


def _weight(w: Window, t: float) -> float:
    ramp = min(1, max(0, min((t - w.start) / w.ease, (w.end - t) / w.ease)))
    return ramp * ramp * (3 - 2 * ramp)


def push_at(ws: Sequence[Window], t: float, frame: Frame) -> tuple[float, float, float]:
    """The zoom at a moment, and the point of the page at the frame's centre, clamped so the
    frame never leaves the page."""
    weights = [_weight(w, t) for w in ws]
    zoom = 1 + sum((w.zoom - 1) * k for w, k in zip(ws, weights))

    def shown(axis: str, extent: float) -> float:
        half = extent / 2
        centre = half + sum((getattr(w, axis) - half) * k for w, k in zip(ws, weights))
        visible = extent / zoom / 2
        return min(extent - visible, max(visible, centre))

    return zoom, shown("cx", frame.width), shown("cy", frame.height)


def _fixed(x: float, digits: int) -> str:
    """Number.prototype.toFixed: the double's exact value rounded, an exact tie away from zero
    (Python's format would take the even one), and '-0.000' kept for a negative that rounds to
    zero, as JavaScript prints it."""
    exact = Decimal(abs(x)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return ("-" if x < 0 else "") + f"{exact:.{digits}f}"


def zoompan_filter(ws: Sequence[Window], frame: Frame, push: PushIn = PushIn()) -> str:
    """The push-ins as ffmpeg's `-vf`: the clip enlarged, then zoompan along the windows, each
    weighted at the frame's time by a smoothstep."""
    time = "in/30"

    def weight(w: Window) -> str:
        e = _fixed(w.ease, 3)
        ramp = f"clip(min(({time}-{_fixed(w.start, 3)})/{e},({_fixed(w.end, 3)}-{time})/{e}),0,1)"
        return f"({ramp}*{ramp}*(3-2*{ramp}))"

    zoom = "1+" + "+".join(f"{_fixed(w.zoom - 1, 4)}*{weight(w)}" for w in ws)

    def centre(axis: str, half: float) -> str:
        return f"{_js(half * push.over)}+" + "+".join(
            f"{_fixed((getattr(w, axis) - half) * push.over, 1)}*{weight(w)}" for w in ws
        )

    return (
        f"scale={frame.width * push.over}:{frame.height * push.over}:flags=lanczos,"
        f"zoompan=z='{zoom}':"
        f"x='clip({centre('cx', frame.width / 2)}-iw/zoom/2,0,iw-iw/zoom)':"
        f"y='clip({centre('cy', frame.height / 2)}-ih/zoom/2,0,ih-ih/zoom)':"
        f"d=1:s={frame.width}x{frame.height}:fps=30,format=yuv420p"
    )


def _js(x: float) -> str:
    """A number as a JavaScript template prints it: 1920 not 1920.0."""
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def _round(x: float) -> int:
    return math.floor(x + 0.5)


def moments(ws: Sequence[Window], in_chapter: float, length: float, fps: float) -> list[float]:
    """Where an editor keys a clip's push-ins: its start and end, and where each move starts, is
    halfway and ends; one key per frame."""
    until = in_chapter + length
    points = [in_chapter]
    for w in ws:
        points += [w.start, w.start + w.ease / 2, w.start + w.ease, w.end - w.ease, w.end - w.ease / 2, w.end]
    points.append(until)
    ordered = sorted(t for t in points if in_chapter <= t <= until)
    return [t for n, t in enumerate(ordered) if n == 0 or _round(t * fps) != _round(ordered[n - 1] * fps)]


def key(ws: Sequence[Window], t: float, frame: Frame) -> tuple[str, str]:
    """The push-in at a moment as FCPXML's transform: scale, and position in a hundredth of the
    frame's height with y up."""
    zoom, x, y = push_at(ws, t, frame)
    unit = 100 / frame.height
    return (
        f"{_fixed(zoom, 4)} {_fixed(zoom, 4)}",
        f"{_fixed(-zoom * (x - frame.width / 2) * unit, 3)} {_fixed(zoom * (y - frame.height / 2) * unit, 3)}",
    )
