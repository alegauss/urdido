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
            look = item.get("look")
            if look not in (None, *LOOKS):
                raise RecordingRefused(f"{name}: highlight look {look!r} is unknown; use one of {sorted(LOOKS)}")
            # A fact callout stays at most 2.8 s; a meme may hold its punchline longer (VM77).
            longest = 5.0 if look == "meme" else 2.8
            found.append({"at": take["at"] + tokens[i][1], "show": item["show"],
                          "duration": min(longest, item.get("duration", 2.8)), "take": name,
                          **{k: item[k] for k in ("person", "event", "look") if k in item}})
        for i, cue in enumerate(found):
            # A reaction meme lands after the line, so it may hold into the take's 0.5 s tail (VM77).
            tail = 0.5 if cue.get("look") == "meme" else 0
            end = min(cue["at"] + cue["duration"], take["at"] + take["length"] + tail)
            if i + 1 < len(found):
                end = min(end, found[i + 1]["at"] - 0.08)
            result.append({**cue, "end": end})
    return result


def stamp(t: float) -> str:
    cs = round(t * 100)
    return f"{cs // 360000}:{cs // 6000 % 60:02}:{cs // 100 % 60:02}.{cs % 100:02}"


#: Burned captions on a vertical frame sit in the Shorts safe area (VM75): clear of the buttons on
#: the right (x 60 to 940 of 1080) and above the title at the bottom (y 1500 of 1920).
SHORTS_BURN = {"size": 84, "margin": 520, "left": 60, "right": 140}
WIDE_BURN = {"size": 58, "margin": 70, "left": 160, "right": 160}


class _Wide:
    width, height = 1920, 1080


#: Highlight looks besides the channel's callout (VM77): a meme is white display type with a heavy
#: black outline near the top of the frame, below the brand mark.
LOOKS = {"meme"}


def meme_style(font: str, frame) -> str:
    size, top = (124, 300) if frame.height > frame.width else (110, 90)
    side = 60 if frame.height > frame.width else 160
    return (f"Style: Meme,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,10,0,8,"
            f"{side},{side},{top},1")


def ass_color(hex_color: str) -> str:
    color = hex_color.lstrip("#")
    return f"&H00{color[4:6]}{color[2:4]}{color[:2]}"


def burn_style(burn: dict, frame) -> dict:
    """The burned captions' look: the frame's default, any key the declaration sets over it."""
    base = SHORTS_BURN if frame.height > frame.width else WIDE_BURN
    known = {"words", "font", "size", "margin", "left", "right", "color", "outline"}
    unknown = set(burn) - known
    if unknown:
        raise ValueError(f"captions.burn: unknown keys {sorted(unknown)}; use {sorted(known)}")
    return {**base, "color": "#FFFFFF", "outline": 6, **burn}


def write_ass(file: Path, timed: list[dict], style: dict, *, frame=None, burned: list | None = None,
              burn: dict | None = None):
    box = ass_color(style["color"])
    frame = frame or _Wide()
    # A player draws the optional captions at the bottom; `margin` (px from the bottom edge, at
    # 1080p) lifts the highlights clear of them (VM48). 85 keeps the earlier videos unchanged.
    margin = int(style.get("margin", 85))
    side = 130 if frame.width >= frame.height else 60
    styles = [f"Style: Key,{style['font']},{HIGHLIGHT_FONT_SIZE},&H00111111,&H00111111,{box},&H00000000,0,0,0,0,100,100,0,0,3,{HIGHLIGHT_OUTLINE},0,2,{side},{side},{margin},1"]
    if any(cue.get("look") == "meme" for cue in timed):
        styles.append(meme_style(style["font"], frame))
    if burned:
        b = burn_style(burn or {}, frame)
        styles.append(f"Style: Cap,{b.get('font', style['font'])},{int(b['size'])},{ass_color(b['color'])},{ass_color(b['color'])},"
                      f"&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,{int(b['outline'])},0,2,"
                      f"{int(b['left'])},{int(b['right'])},{int(b['margin'])},1")
    newline = "\n"
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {frame.width}
PlayResY: {frame.height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{newline.join(styles)}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    clean = lambda text: text.replace("{", "").replace("}", "").replace("\n", r"\N")  # noqa: E731
    # A caption group may wrap (\q0); the highlights keep the file's no-wrap style.
    events = [f"Dialogue: 0,{stamp(c.start)},{stamp(c.end)},Cap,,0,0,0,,{{\\q0}}{clean(c.text)}" for c in burned or []]
    for cue in timed:
        if cue.get("look") == "meme":
            # A meme may wrap to two lines (\q0) and pops in rather than fading.
            events.append(f"Dialogue: 2,{stamp(cue['at'])},{stamp(cue['end'])},Meme,,0,0,0,,{{\\q0}}{clean(cue['show'])}")
        else:
            events.append(f"Dialogue: 1,{stamp(cue['at'])},{stamp(cue['end'])},Key,,0,0,0,,{{\\fad(100,150)}}{clean(cue['show'])}")
    file.write_text(head + "\n".join(events) + "\n", encoding="utf-8")


def burned_cues(placed: list[dict], size: int) -> list:
    """Every heard take's written words as burned caption groups (VM75)."""
    from videomaker.captions import burned_cues as take_cues

    cues = []
    for take in sorted(placed, key=lambda p: p["at"]):
        cues += take_cues(take, word_record(Path(take["file"])), size)
    return cues


def overlay(joined: str, placed: list[dict], declaration: dict, parts: Path, fonts: str, encoder: str,
            *, window: tuple[float, float] | None = None, origin: float = 0, aliases=None,
            frame=None, burn: dict | None = None) -> str:
    from videomaker import media
    from videomaker import cache

    timed = cues(placed, declaration["lines"], aliases=aliases)
    burned = burned_cues(placed, int(burn.get("words", 3))) if burn else None
    ass = parts / "keywords.ass"
    write_ass(ass, timed, declaration["style"], frame=frame, burned=burned, burn=burn)
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
