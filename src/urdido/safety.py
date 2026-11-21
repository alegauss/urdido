"""VM48 / PW698: reserve the declared player-caption band for captions."""
from __future__ import annotations

import json
import math
import warnings
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from urdido.keywords import HIGHLIGHT_FONT_SIZE, HIGHLIGHT_OUTLINE
from urdido.sources.model import RecordingRefused


@dataclass(frozen=True)
class Policy:
    bottom: float = 0.2
    action: str = "off"


CURRENT = ContextVar("caption_safe_area", default=Policy())


@contextmanager
def configured(spec: dict):
    policy = Policy(float(spec.get("bottom", 0.2)), spec.get("action", "warn"))
    if not math.isfinite(policy.bottom) or not 0 <= policy.bottom < 1:
        raise ValueError("captions.safe_area.bottom must be a fraction from 0 up to 1")
    if policy.action not in {"warn", "error", "off"}:
        raise ValueError("captions.safe_area.action must be warn, error or off")
    token = CURRENT.set(policy)
    try:
        yield policy
    finally:
        CURRENT.reset(token)


def collisions(boxes: list[dict], height: int, policy: Policy | None = None) -> list[dict]:
    policy = policy or CURRENT.get()
    if policy.action == "off" or policy.bottom == 0:
        return []
    edge = height * (1 - policy.bottom)
    return [{**box, "band_top": edge, "crossing": box["y"] + box["height"] - edge}
            for box in boxes if box["height"] > 0 and box["y"] + box["height"] > edge]


def page_boxes(page, name: str) -> list[dict]:
    if CURRENT.get().action == "off":
        return []
    return page.locator("header, h1, p, small, footer, .url, .badge").evaluate_all("""elements => elements.flatMap(el => {
        const style = getComputedStyle(el), rect = el.getBoundingClientRect();
        const text = el.innerText.trim() || (el.querySelector('img,svg') ? '[image]' : '');
        if (!text || style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0
            || !rect.width || !rect.height) return [];
        return [{label: el.tagName.toLowerCase(), text, x: rect.x, y: rect.y,
                 width: rect.width, height: rect.height}];
    })""")


def publish(findings: list[dict], path: Path) -> None:
    policy = CURRENT.get()
    if policy.action == "off":
        path.unlink(missing_ok=True)
        return
    path.write_text(json.dumps({"bottom": policy.bottom, "action": policy.action, "findings": findings},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if findings:
        first = findings[0]
        message = (f"caption safe area: {len(findings)} overlap(s); {first.get('page', 'highlights')} "
                   f"{first['label']} {first['text']!r} crosses by {first['crossing']:.1f}px; see {path}")
        if policy.action == "error":
            raise RecordingRefused(message)
        warnings.warn(message, UserWarning, stacklevel=2)


def highlights(style: dict, timed: list[dict], path: Path) -> None:
    """ASS uses a 1080p reference; its 18 px box outline extends below MarginV."""
    margin = int(style.get("margin", 85))
    boxes = [{"label": "highlight", "text": cue["show"], "at": cue["at"], "end": cue["end"],
              "y": 1080 - margin - HIGHLIGHT_FONT_SIZE,
              "height": HIGHLIGHT_FONT_SIZE + HIGHLIGHT_OUTLINE} for cue in timed]
    publish(collisions(boxes, 1080), path)
