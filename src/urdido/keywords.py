"""Word-timed callouts over footage, matched against hash-checked narration transcripts."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path

from videomaker.sources.model import RecordingRefused

HIGHLIGHT_FONT_SIZE = 76
HIGHLIGHT_OUTLINE = 18


def fold(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", text.lower()))


def word_record(file: Path) -> list[dict]:
    record = file.with_suffix(".words.json")
    if not record.exists():
        raise RecordingRefused(f"{file.stem}: missing word times; run videomaker.narration_words")
    words = json.loads(record.read_text(encoding="utf-8-sig"))
    from videomaker.cache import file_hash

    if words["sha256"] != file_hash(file):
        raise RecordingRefused(f"{file.stem}: stale word times; transcribe the current take")
    return validate_words(words["words"], file.stem)


def validate_words(transcript, name):
    if not isinstance(transcript, list) or not transcript:
        raise RecordingRefused(f"{name}: word times must contain spoken words")
    previous = 0
    for word in transcript:
        try:
            start, end = word["start"], word["end"]
            valid = isinstance(word["text"], str) and bool(word["text"].strip()) \
                and math.isfinite(start) and math.isfinite(end) and 0 <= previous <= start <= end
        except (KeyError, TypeError):
            valid = False
        if not valid:
            raise RecordingRefused(f"{name}: malformed or unordered word times; review the transcript")
        previous = start
    return transcript


def aliases(script, language):
    """VM60: declared pronunciation and reviewed ASR spellings, never fuzzy guesses."""
    result = {key: [value] for key, value in script.get("pronounce", {}).get(language, {}).items()}
    for key, values in script.get("alignment_aliases", {}).get(language, {}).items():
        result.setdefault(key, []).extend([values] if isinstance(values, str) else values)
    return result


def normalizer(declared):
    forms = {}
    for key, values in (declared or {}).items():
        canonical = fold(key)
        values = [values] if isinstance(values, str) else values
        for value in [key, *values]:
            if not isinstance(value, str) or not fold(value) or not canonical:
                raise RecordingRefused("spoken aliases need nonempty literal words")
            form = fold(value)
            if form in forms and forms[form] != canonical:
                raise RecordingRefused(f"ambiguous spoken alias {value!r}; declare one canonical name")
            forms[form] = canonical
    pattern = re.compile("|".join(re.escape(form) for form in sorted(forms, key=len, reverse=True))) if forms else None
    normalize = lambda text: pattern.sub(lambda match: forms[match[0]], text) if pattern else text
    ratio = max([1, *[len(form) / len(canonical) for form, canonical in forms.items()]])
    return normalize, ratio


def matches(words: list[dict], phrase: str, start: int = 0, *, aliases=None) -> list[tuple[int, int]]:
    normalize, ratio = normalizer(aliases)
    target = normalize(fold(phrase))
    if not target:
        raise RecordingRefused("word anchor must contain a spoken word")
    tokens = [fold(w["text"]) for w in words]
    found = []
    for i in range(start, len(tokens)):
        joined, j = "", i
        while j < len(tokens) and len(joined) <= math.ceil(len(target) * ratio):
            joined += tokens[j]
            j += 1
            if normalize(joined) == target:
                found.append((i, j))
                break
    return found


def anchor(file: Path, spec: str | dict, *, aliases=None) -> float:
    """VM42: resolve one explicit occurrence, refusing a guessed match."""
    spec = {"text": spec} if isinstance(spec, str) else spec
    words = word_record(file)
    text = spec["text"]
    found = matches(words, text, aliases=aliases)
    if spec.get("context"):
        contexts = matches(words, spec["context"], aliases=aliases)
        found = [(i, j) for i, j in found if any(a <= i and j <= b for a, b in contexts)]
    occurrence = spec.get("occurrence")
    if occurrence is not None:
        if isinstance(occurrence, bool) or not isinstance(occurrence, int) or occurrence < 1:
            raise RecordingRefused(f"{file.stem}: anchor occurrence must be a positive integer")
        found = found[occurrence - 1:occurrence]
    if len(found) != 1:
        raise RecordingRefused(f"{file.stem}: word anchor {text!r} has {len(found)} matches; specify occurrence or context")
    return words[found[0][0]]["start"]


def cues(placed: list[dict], lines: dict, *, aliases=None) -> list[dict]:
    result = []
    for take in placed:
        file = Path(take["file"])
        name = file.stem
        wanted = lines.get(name, [])
        if not wanted:
            continue
        words = word_record(file)
        tokens = [(fold(w["text"]), w["start"], w["end"]) for w in words]
        cursor, found = 0, []
        for item in wanted:
            candidates = matches(words, item.get("hear", item["show"]), cursor, aliases=aliases)
            match = candidates[0] if candidates else None
            if match is None:
                raise RecordingRefused(f"{name}: keyword anchor {item.get('hear', item['show'])!r} not heard")
            i, cursor = match
            found.append({"at": take["at"] + tokens[i][1], "show": item["show"],
                          "duration": min(2.8, item.get("duration", 2.8)), "take": name,
                          **{k: item[k] for k in ("person", "event") if k in item}})
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
Style: Key,{style['font']},{HIGHLIGHT_FONT_SIZE},&H00111111,&H00111111,{box},&H00000000,0,0,0,0,100,100,0,0,3,{HIGHLIGHT_OUTLINE},0,2,130,130,{margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for cue in timed:
        text = cue["show"].replace("{", "").replace("}", "").replace("\n", r"\N")
        events.append(f"Dialogue: 1,{stamp(cue['at'])},{stamp(cue['end'])},Key,,0,0,0,,{{\\fad(100,150)}}{text}")
    file.write_text(head + "\n".join(events) + "\n", encoding="utf-8")


def overlay(joined: str, placed: list[dict], declaration: dict, parts: Path, fonts: str, encoder: str,
            *, window: tuple[float, float] | None = None, origin: float = 0, aliases=None) -> str:
    from videomaker import media
    from videomaker import cache

    timed = cues(placed, declaration["lines"], aliases=aliases)
    ass = parts / "keywords.ass"
    write_ass(ass, timed, declaration["style"])
    (parts / "keywords.json").write_text(json.dumps(timed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path = lambda p: str(p).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    output = str(parts / "highlighted.mp4")
    effect = f"subtitles='{path(ass)}':fontsdir='{path(fonts)}'"
    if window:
        start, end = window
        effect = (f"trim=start={start - origin:.9f}:end={end - origin:.9f},"
                  f"setpts=PTS-STARTPTS+{start:.9f}/TB,{effect},setpts=PTS-STARTPTS")
    args = ["-i", joined, "-vf", effect,
            *media.video_codec(encoder, 20), "-pix_fmt", "yuv420p", "-an", output]
    cache.run("highlights", [output], args, lambda: media.ffmpeg(args),
              inputs=[__file__, media.__file__, joined, ass, fonts], tools=["ffmpeg"])
    return output
