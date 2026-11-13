"""Word-timed callouts over footage, matched against hash-checked narration transcripts."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from videomaker.sources.model import RecordingRefused


def fold(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", text.lower()))


def cues(placed: list[dict], lines: dict) -> list[dict]:
    result = []
    for take in placed:
        file = Path(take["file"])
        name = file.stem
        wanted = lines.get(name, [])
        if not wanted:
            continue
        record = file.with_suffix(".words.json")
        if not record.exists():
            raise RecordingRefused(f"{name}: missing word times; run videomaker.narration_words")
        words = json.loads(record.read_text(encoding="utf-8"))
        if words["sha256"] != hashlib.sha256(file.read_bytes()).hexdigest():
            raise RecordingRefused(f"{name}: stale word times; transcribe the current take")
        tokens = [(fold(w["text"]), w["start"], w["end"]) for w in words["words"]]
        cursor, found = 0, []
        for item in wanted:
            target = fold(item.get("hear", item["show"]))
            match = None
            for i in range(cursor, len(tokens)):
                joined, j = "", i
                while j < len(tokens) and len(joined) < len(target):
                    joined += tokens[j][0]
                    j += 1
                if joined == target:
                    match = i, j
                    break
            if match is None:
                raise RecordingRefused(f"{name}: keyword anchor {item.get('hear', item['show'])!r} not heard")
            i, cursor = match
            found.append({"at": take["at"] + tokens[i][1], "show": item["show"],
                          "duration": min(2.8, item.get("duration", 2.8)), "take": name})
        for i, cue in enumerate(found):
            end = min(cue["at"] + cue["duration"], take["at"] + take["length"])
            if i + 1 < len(found):
                end = min(end, found[i + 1]["at"] - 0.08)
            result.append({**cue, "end": end})
    return result


def stamp(t: float) -> str:
    cs = round(t * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"


def write_ass(file: Path, timed: list[dict], style: dict):
    color = style["color"].lstrip("#")
    box = f"&H00{color[4:6]}{color[2:4]}{color[:2]}"
    # A player draws the optional captions at the bottom; `margin` (px from the bottom edge, at
    # 1080p) lifts the highlights clear of them (VM48). 85 keeps the earlier videos unchanged.
    margin = int(style.get("margin", 85))
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Key,{style['font']},76,&H00111111,&H00111111,{box},&H00000000,0,0,0,0,100,100,0,0,3,18,0,2,130,130,{margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for cue in timed:
        text = cue["show"].replace("{", "").replace("}", "").replace("\n", r"\N")
        events.append(f"Dialogue: 1,{stamp(cue['at'])},{stamp(cue['end'])},Key,,0,0,0,,{{\\fad(100,150)}}{text}")
    file.write_text(head + "\n".join(events) + "\n", encoding="utf-8")


def overlay(joined: str, placed: list[dict], declaration: dict, parts: Path, fonts: str, encoder: str) -> str:
    from videomaker import media

    timed = cues(placed, declaration["lines"])
    ass = parts / "keywords.ass"
    write_ass(ass, timed, declaration["style"])
    (parts / "keywords.json").write_text(json.dumps(timed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path = lambda p: str(p).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    output = str(parts / "highlighted.mp4")
    media.ffmpeg(["-i", joined, "-vf", f"subtitles='{path(ass)}':fontsdir='{path(fonts)}'",
                  *media.video_codec(encoder, 20), "-pix_fmt", "yuv420p", "-an", output])
    return output
