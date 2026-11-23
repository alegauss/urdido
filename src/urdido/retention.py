"""Where a published video's viewers leave, read off YouTube Studio's curve (UR69).

    urdido retention <curve.csv> --captions <cut.srt> --plan <plan.json> [--json]

The input is Studio's audience-retention export (Analytics > Engagement > Audience
retention > See more > Export > CSV): one row per percent of the video, its position
and the absolute retention. A file split by audience (subscribed or not, organic or
paid) has a third column naming the audience, and `--audience` picks one. The curve
is read against the cut's own captions, so every drop names the sentence heard there,
and against the plan's shots, so it names what was on screen.

The rules are heuristics from youtube-agent-skill and youtube-agent-pro (MIT), read on
2026-11-12, and kept as heuristics rather than targets (marketing VM28):

- the hook leak is the loss over the first 30 s (a Short's first 3 s): under 25 points
  healthy, 25 to 40 leaking, over 40 severe;
- a cliff is a drop of more than 0.8 points between two samples; the five largest are
  reported with what was said 4 s either side;
- the slide is the mean bleed per tenth of the video across the middle (20% to 80%);
  its fix is to cut;
- a healthy hook with a flat slide puts the problem in the title and thumbnail;
- the loss over the first 5 s, where the voice is the first thing heard, is reported
  on its own: the evidence for or against "AI narration loses viewers".
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from urdido.errors import UrdidoError

SHORT = 60.0
CLIFF = 0.8
NEAR = 4.0


class RetentionRefused(UrdidoError):
    """A curve or a cut this reader cannot read as it is."""


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    text: str


def _number(text: str) -> float | None:
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def curve(file: Path, audience: str | None = None) -> list[tuple[float, float]]:
    """`(position %, retention %)` pairs from a Studio export, in order."""
    with open(file, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 3:
        raise RetentionRefused(
            f"{file.name}: no curve in it (Studio's 'Detailed activity' is empty)"
        )
    header = [h.lower() for h in rows[0]]
    value = next(
        (i for i, h in enumerate(header) if ("reten" in h) and ("absolut" in h)), None
    )
    if value is None:
        raise RetentionRefused(
            f"{file.name}: no absolute audience retention column ({', '.join(rows[0])})"
        )
    labels = [
        i for i in range(1, len(header)) if i != value and _number(rows[1][i]) is None
    ]
    found = []
    seen = set()
    for row in rows[1:]:
        if labels:
            name = row[labels[0]]
            seen.add(name)
            if name != audience:
                continue
        position, retention = _number(row[0]), _number(row[value])
        if position is None or retention is None:
            continue
        found.append((position, retention))
    if labels and not found:
        raise RetentionRefused(
            f"{file.name}: split by audience; pass --audience with one of "
            f"{', '.join(sorted(seen))}"
        )
    return sorted(found)


_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def captions(file: Path) -> list[Cue]:
    """The cut's SRT cues, the way urdido writes them."""
    cues = []
    for block in re.split(
        r"\r?\n\s*\r?\n", file.read_text(encoding="utf-8-sig").strip()
    ):
        lines = block.splitlines()
        for i, line in enumerate(lines):
            found = _TIME.search(line)
            if found:
                h1, m1, s1, f1, h2, m2, s2, f2 = (int(x) for x in found.groups())
                start = h1 * 3600 + m1 * 60 + s1 + f1 / 1000
                end = h2 * 3600 + m2 * 60 + s2 + f2 / 1000
                cues.append(Cue(start, end, " ".join(lines[i + 1 :]).strip()))
                break
    return cues


def _at(points: list[tuple[float, float]], seconds: float) -> float:
    """The retention at `seconds`, interpolated between samples."""
    for (t0, r0), (t1, r1) in zip(points, points[1:], strict=False):
        if t0 <= seconds <= t1:
            return r0 if t1 == t0 else r0 + (r1 - r0) * (seconds - t0) / (t1 - t0)
    return points[-1][1] if seconds > points[-1][0] else points[0][1]


def _said(cues: list[Cue], start: float, end: float) -> str:
    return " ".join(c.text for c in cues if c.end > start and c.start < end)


def _shot(shots: list[dict], seconds: float) -> str:
    for shot in shots:
        start = shot.get("start")
        length = shot.get("dur", shot.get("length"))
        if (
            isinstance(start, (int, float))
            and isinstance(length, (int, float))
            and start <= seconds < start + length
        ):
            return str(shot.get("label") or shot.get("src") or shot.get("file") or "")
    return ""


def _grade(points: float) -> str:
    return "healthy" if points < 25 else "leaking" if points <= 40 else "severe"


def read(
    points_pct: list[tuple[float, float]],
    length: float,
    cues: list[Cue],
    shots: list[dict] | None = None,
) -> dict:
    """The report: hook, first seconds, cliffs, slide and what they point at."""
    if length <= 0:
        raise RetentionRefused("the cut's length must be positive")
    points = [(p / 100 * length, r) for p, r in points_pct]
    if len(points) < 3:
        raise RetentionRefused("a curve needs at least three samples")
    shots = shots or []
    base = points[0][1]
    short = length <= SHORT
    window = 3.0 if short else 30.0
    hook = base - _at(points, window)
    first = base - _at(points, min(5.0, length))
    drops = []
    for (t0, r0), (t1, r1) in zip(points, points[1:], strict=False):
        if r0 - r1 > CLIFF:
            at = (t0 + t1) / 2
            drops.append(
                {
                    "at": round(at, 1),
                    "from": r0,
                    "to": r1,
                    "points": round(r0 - r1, 2),
                    "said": _said(cues, at - NEAR, at + NEAR),
                    "shot": _shot(shots, at),
                }
            )
    cliffs = sorted(drops, key=lambda d: -d["points"])[:5]
    middle = [(t, r) for t, r in points if 0.2 * length <= t <= 0.8 * length]
    span = middle[-1][0] - middle[0][0] if len(middle) > 1 else 0
    slide = (middle[0][1] - middle[-1][1]) / span * length / 10 if span else 0.0
    if _grade(hook) == "healthy" and slide < 2:
        verdict = (
            "the hook holds and the middle is flat: "
            "the title and thumbnail bring the wrong viewers"
        )
    elif _grade(hook) != "healthy":
        verdict = (
            "the opening loses them: "
            "rewrite what is said and shown before the first proof"
        )
    else:
        verdict = "the middle bleeds: cut what the largest cliffs point at"
    return {
        "length": round(length, 2),
        "short": short,
        "hook": {"window": window, "points": round(hook, 2), "grade": _grade(hook)},
        "first_5s": round(first, 2),
        "end": round(points[-1][1], 2),
        "slide_per_tenth": round(slide, 2),
        "cliffs": sorted(cliffs, key=lambda d: d["at"]),
        "verdict": verdict,
    }


def text(report: dict) -> str:
    """The report as a person reads it."""
    hook = report["hook"]
    lines = [
        f"length {report['length']} s{' (a Short)' if report['short'] else ''}",
        f"hook: {hook['points']} points lost in the first {hook['window']:g} s, "
        f"{hook['grade']}",
        f"first 5 s: {report['first_5s']} points lost",
        f"slide: {report['slide_per_tenth']} points per 10% of the video, mid-video",
        f"end: {report['end']}% still watching",
        "cliffs:",
    ]
    for cliff in report["cliffs"]:
        minutes, seconds = divmod(int(cliff["at"]), 60)
        lines.append(
            f"  {minutes}:{seconds:02} -{cliff['points']} "
            f"({cliff['from']} -> {cliff['to']})"
            + (f" [{cliff['shot']}]" if cliff["shot"] else "")
        )
        if cliff["said"]:
            lines.append(f'      "{cliff["said"]}"')
    lines.append(f"verdict: {report['verdict']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="urdido retention",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("curve", type=Path, help="Studio's audience-retention CSV")
    parser.add_argument(
        "--captions", type=Path, required=True, help="the published cut's .srt"
    )
    parser.add_argument(
        "--plan", type=Path, help="the cut's plan.json: its length and shots"
    )
    parser.add_argument(
        "--seconds", type=float, help="the cut's length, when there is no plan"
    )
    parser.add_argument(
        "--audience", help="the audience to read, in a file split by audience"
    )
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    plan = json.loads(args.plan.read_text(encoding="utf-8")) if args.plan else {}
    length = args.seconds or plan.get("length")
    if not length:
        raise RetentionRefused(
            "the cut's length is unknown: pass --plan with a length, or --seconds"
        )
    report = read(
        curve(args.curve, args.audience),
        float(length),
        captions(args.captions),
        plan.get("shots"),
    )
    print(
        json.dumps(report, ensure_ascii=False, indent=2) if args.json else text(report)
    )
    return 0
