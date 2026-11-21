"""YouTube Shorts (1080x1920) cut from a built video's plan, by its declaration (UR2).

    urdido shorts <video.toml> --language pt-BR           every declared Short
    urdido shorts <video.toml> --language pt-BR 2 3       those two
    urdido shorts <video.toml> --language pt-BR --check   no render

Each Japode video carried a `bin/short.py`, and only the Scion copy knew what was
learned on 2026-11-12. This is that cutter once. It reads what a build left: the plan
(when each line is said, the shots, the callouts), the picture without titles, the
mix, and each take's word times for the captions.

    [shorts]
    plan = "out/plan.json"
    picture = "out/work/picture.mp4"
    mix = "out/work/mix.wav"
    words = "narration/{language}/{take}.words.json"
    out = "out/shorts/scion-short-{n}-{language}"   # .mp4 and .txt
    link = "https://youtu.be/..."                    # the full video
    tags = ["#git", "#programacao", "#ia"]
    sources = "sources.json"                         # credits, optional
    credit = '- "{title}", {channel} ({url}), CC BY'
    fixes = { "2500" = "2.500" }                     # the script's spelling

    [shorts.look]                                    # the channel's look
    night = "#0b1410"
    accent = "#2BCB6B"
    ink = "#111111"
    title_font = "Japode Jakarta ExtraBold"
    text_font = "Japode Jakarta SemiBold"
    fonts = "../brand/fonts"

    [shorts.notes]                                   # each description's close
    pt-BR = "Narração e música geradas com ElevenLabs."

    [[shorts.cut]]
    n = 2
    takes = ["chapter-3", "chapter-3-result"]
    hook = ["O Git da Anthropic ia", "baixar 600 PB por dia"]
    title = "600 PB por dia: onde o Git quebrou na Anthropic #shorts"
    text = "100 GB de histórico, 25 milhões de checkouts por dia."

What every Short keeps (`[shorts.rules]` moves a number, never drops a rule):

- no frozen end card: a Short replays in a loop, so the last word runs straight back
  into the hook, and the pointer to the full video replaces the hook for the last
  `pointer` seconds over the moving picture;
- a visual change every 2 to 4 s: a shot longer than `punch_after` is punched in to
  `punch` at its middle, except a terminal, whose lines the 4:3 cut already trims;
- voice and picture `speed` times faster, pitch kept, `tail` s after the last word;
- captions burned in, word-timed, `caption_chars` a line, numbers in the accent
  colour, left of the buttons column and above the title band;
- the sound normalised to `loudness` LUFS under a true peak of `true_peak` dBTP;
- a title of 60 characters at most, 3 to 5 hashtags, 20 to 55 s, opening on a number.

A title, hashtag count or length past those bounds is refused; a hook with no number
and a length outside 20-55 s but under a minute are advised. Where the provider runs,
the burned .ass is held to `video.safe_area`'s youtube-shorts bounds before encoding,
and the encoded file to `accept.check`: under a minute, loudness within 1 LU of the
target, true peak under -1 dBTP and no frozen end.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

from urdido import media

W, H = 1080, 1920

#: The pointer to the full video per language, unless `[shorts.pointer.<l>]` says.
POINTER = {
    "pt": ("A história completa", "tá no canal"),
    "en": ("The full story", "is on the channel"),
}
#: The description's labels, per language.
LABELS = {
    "pt": {
        "title": "Título ({n} caracteres)",
        "text": "Descrição",
        "link": "O vídeo completo: {link}",
    },
    "en": {
        "title": "Title ({n} characters)",
        "text": "Description",
        "link": "The full video: {link}",
    },
}
STYLE_FORMAT = (
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
    "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
    "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, "
    "MarginV, Encoding"
)
EVENT_FORMAT = (
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
)
WHITE, BLACK, SHADE = "&H00FFFFFF", "&H00000000", "&H90000000"


@dataclass(frozen=True)
class Rules:
    speed: float = 1.1
    tail: float = 0.35
    pointer: float = 2.6
    punch_after: float = 3.6
    punch: float = 1.1
    top: int = 520
    caption_chars: int = 20
    loudness: float = -14.0
    true_peak: float = -1.5
    title_chars: int = 60
    hashtags: tuple[int, int] = (3, 5)
    seconds: tuple[float, float] = (20.0, 55.0)
    hard_seconds: float = 60.0


@dataclass(frozen=True)
class Look:
    night: str
    accent: str
    ink: str
    title_font: str
    text_font: str
    fonts: str = ""


@dataclass(frozen=True)
class Cut:
    n: int
    takes: tuple[str, ...]
    hook: tuple[str, str]
    title: str
    text: str


@dataclass
class Span:
    start: float  # source seconds where the Short starts
    voice_end: float  # source seconds where its last word ends
    clip: float  # source seconds it takes
    length: float  # output seconds
    segments: list[dict] = field(default_factory=list)


def units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def language_key(table: dict, language: str):
    return table.get(language, table.get(language.split("-")[0].lower()))


def ass_colour(hex_rgb: str, alpha: int = 0) -> str:
    """#RRGGBB as ASS's &HAABBGGRR."""
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", hex_rgb):
        raise ValueError(f"shorts: a colour is #RRGGBB, got {hex_rgb!r}")
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def stamp(seconds: float) -> str:
    cs = int(round(max(0.0, seconds) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def rules_of(spec: dict) -> Rules:
    known = {f.name for f in fields(Rules)}
    unknown = sorted(set(spec) - known)
    if unknown:
        raise ValueError(
            f"shorts: [shorts.rules] has no {', '.join(unknown)}; "
            f"it takes {', '.join(sorted(known))}"
        )
    return Rules(**{k: tuple(v) if isinstance(v, list) else v for k, v in spec.items()})


def look_of(spec: dict) -> Look:
    needed = ("night", "accent", "ink", "title_font", "text_font")
    missing = [name for name in needed if not spec.get(name)]
    if missing:
        raise ValueError(
            f"shorts: [shorts.look] needs {', '.join(missing)}: "
            "the channel's look is declared, not assumed"
        )
    look = Look(**{f.name: spec.get(f.name, "") for f in fields(Look)})
    for colour in (look.night, look.accent, look.ink):
        ass_colour(colour)
    return look


def cuts_of(spec: list) -> list[Cut]:
    cuts = []
    for row in spec:
        needed = ("n", "takes", "hook", "title", "text")
        missing = [name for name in needed if name not in row]
        if missing:
            raise ValueError(f"shorts: a [[shorts.cut]] needs {', '.join(missing)}")
        hook = row["hook"]
        if not (
            isinstance(hook, list)
            and len(hook) == 2
            and all(isinstance(h, str) and h for h in hook)
        ):
            raise ValueError(
                f"shorts: short {row['n']}'s hook is two lines, the lead and the key"
            )
        hooked = (hook[0], hook[1])
        takes = tuple(row["takes"])
        cuts.append(Cut(int(row["n"]), takes, hooked, row["title"], row["text"]))
    numbers = [cut.n for cut in cuts]
    if len(set(numbers)) != len(numbers):
        raise ValueError("shorts: two [[shorts.cut]] share a number")
    return cuts


def span(plan: dict, cut: Cut, rules: Rules) -> Span:
    segments = [s for s in plan["segments"] if s["take"] in cut.takes]
    if not segments:
        raise ValueError(
            f"shorts: short {cut.n} names takes the plan does not have: "
            + ", ".join(cut.takes)
        )
    start = segments[0]["start"]
    voice_end = segments[-1]["voice_at"] + segments[-1]["voice"]
    clip = voice_end + rules.tail - start
    return Span(start, voice_end, clip, clip / rules.speed, segments)


def word_lines(
    words: list[dict], offset: float, limit: int, fixes: dict | None = None
) -> list[tuple[float, float, str]]:
    """A take's words grouped into caption lines of `limit` characters, each held
    until the next starts (at most 0.6 s past its last word), in source seconds from
    `offset`."""
    fixes = fixes or {}
    words = [{**w, "text": fixes.get(w["text"], w["text"])} for w in words]

    def joined(group):
        return " ".join(x["text"] for x in group)

    lines, current = [], []
    for word in words:
        ends = current and re.search(r"[.!?:]$", current[-1]["text"])
        if current and (len(joined([*current, word])) > limit or ends):
            lines.append((current[0]["start"], current[-1]["end"], joined(current)))
            current = []
        current.append(word)
    if current:
        lines.append((current[0]["start"], current[-1]["end"], joined(current)))
    timed = []
    for i, (a, b, text) in enumerate(lines):
        following = lines[i + 1][0] if i + 1 < len(lines) else b + 0.3
        timed.append((offset + a, offset + max(b, min(following, b + 0.6)), text))
    return timed


def paint_numbers(text: str, accent: str) -> str:
    """Braces escaped, and every number painted in the accent colour."""
    text = text.replace("{", "(").replace("}", ")")
    colour = ass_colour(accent).replace("&H00", "&H")
    return re.sub(r"(\d[\d.,%]*)", rf"{{\\c{colour}&}}\1{{\\r}}", text)


def punches(
    plan: dict, start: float, end: float, rules: Rules
) -> list[tuple[float, float]]:
    """Source spans (seconds from `start`) drawn punched in: the second half of every
    shot longer than `punch_after`. A terminal is left whole."""
    shots, spans = plan["shots"], []
    for i, shot in enumerate(shots):
        if shot["src"].startswith("terminal:"):
            continue
        following = shots[i + 1]["start"] if i + 1 < len(shots) else plan["length"]
        a, b = max(shot["start"], start), min(following, end)
        if b - a > rules.punch_after:
            spans.append(((a + b) / 2 - start, b - start))
    return spans


def styles(look: Look) -> list[str]:
    """The .ass styles in the channel's fonts and colours."""
    accent, ink = ass_colour(look.accent), ass_colour(look.ink)
    title, text = look.title_font, look.text_font
    # name, font, size, primary, outline colour, back, border style, outline, shadow,
    # alignment, side margins
    rows = [
        ("Hook", title, 78, WHITE, BLACK, SHADE, 1, 6, 4, 2, 40),
        ("HookKey", title, 80, ink, accent, BLACK, 3, 20, 0, 8, 40),
        ("Cap", title, 66, WHITE, BLACK, SHADE, 1, 7, 3, 8, 60),
        ("Key", title, 56, ink, accent, BLACK, 3, 16, 0, 8, 60),
        ("Def", text, 36, WHITE, "&H64000000", BLACK, 3, 10, 0, 8, 80),
    ]
    made = []
    for name, font, size, primary, outline, back, *shape in rows:
        border, width, shadow, align, side = shape
        made.append(
            f"Style: {name},{font},{size},{primary},{WHITE},{outline},{back},"
            f"0,0,0,0,100,100,0,0,{border},{width},{shadow},{align},{side},{side},0,1"
        )
    return made


def subtitles(
    plan: dict,
    cut: Cut,
    cut_span: Span,
    words: dict[str, list[dict]],
    look: Look,
    rules: Rules,
    pointer: tuple[str, str],
    fixes: dict | None = None,
) -> str:
    """The .ass burned into the Short: hook, captions, callouts, the pointer."""

    def out(source: float) -> float:
        return source / rules.speed

    def event(layer, a, b, style, text):
        return f"Dialogue: {layer},{stamp(a)},{stamp(b)},{style},,0,0,0,,{text}"

    start, voice_end, length = cut_span.start, cut_span.voice_end, cut_span.length
    caption_x = 500  # a little left of centre: the right column holds the buttons
    place = f"{{\\an8\\pos({caption_x},1400)}}"
    events = []
    for segment in cut_span.segments:
        offset = segment["voice_at"] - start
        lines = word_lines(words[segment["take"]], offset, rules.caption_chars, fixes)
        for a, b, text in lines:
            painted = paint_numbers(text, look.accent)
            events.append(event(2, out(a), out(b), "Cap", place + painted))
    fade = "{\\fad(150,150)\\an8\\pos(540,%d)}"
    for callout in plan.get("callouts", []):
        a, b, key = callout[:3]
        definition = callout[3] if len(callout) > 3 else ""
        if a < start or a >= voice_end:
            continue
        a, b = out(a - start), out(min(b, voice_end) - start)
        events.append(event(3, a, b, "Key", fade % 560 + key))
        if definition:
            events.append(event(3, a, b, "Def", fade % 660 + definition))
    swap = max(0.0, length - rules.pointer)
    lead, key = "{\\an2\\pos(540,330)}", "{\\an8\\pos(540,350)}"
    arrive = "{\\fad(200,0)}"
    events += [
        event(1, 0, swap, "Hook", lead + cut.hook[0]),
        event(1, 0, swap, "HookKey", key + cut.hook[1]),
        event(1, swap, length, "Hook", arrive + lead + pointer[0]),
        event(1, swap, length, "HookKey", arrive + key + pointer[1]),
    ]
    head = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {W}",
        f"PlayResY: {H}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        STYLE_FORMAT,
        *styles(look),
        "",
        "[Events]",
        EVENT_FORMAT,
    ]
    return "\n".join([*head, *events]) + "\n"


def filter_path(path: Path) -> str:
    return path.as_posix().replace(":", r"\:")


def graph(
    cut_span: Span,
    spans: list[tuple[float, float]],
    look: Look,
    rules: Rules,
    ass: Path,
    fonts: Path | None,
) -> str:
    """The ffmpeg graph: the picture cut to 4:3 between two accent rules over the
    background, punched in where `spans` say, sped up with its sound, captions burned
    in, sound normalised. Inputs: 0 the picture, 1 the mix, 2 the background still."""
    fw, fh = W, W * 3 // 4
    punched = "+".join(f"between(it,{a:.2f},{b:.2f})" for a, b in spans) or "0"
    accent = look.accent.replace("#", "0x")
    burn = f"subtitles='{filter_path(ass)}'"
    if fonts:
        burn += f":fontsdir='{filter_path(fonts)}'"
    zoom = (
        f"zoompan=z='if({punched},{rules.punch},1)'"
        f":x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={fw}x{fh}:fps=30"
    )
    sound = f"loudnorm=I={rules.loudness}:TP={rules.true_peak}:LRA=11,aresample=48000"
    fade_at = cut_span.length - 0.25
    return (
        f"[0:v]crop=ih*4/3:ih,scale={fw * 2}:{fh * 2},{zoom},"
        f"setpts=(PTS-STARTPTS)/{rules.speed}[fg];"
        f"[2:v]format=yuv420p[bg];"
        f"[bg][fg]overlay=0:{rules.top}:shortest=1,"
        f"drawbox=0:{rules.top - 8}:{W}:8:{accent}:t=fill,"
        f"drawbox=0:{rules.top + fh}:{W}:8:{accent}:t=fill,"
        f"{burn},format=yuv420p[v];"
        f"[1:a]atrim=0:{cut_span.clip:.3f},asetpts=PTS-STARTPTS,"
        f"atempo={rules.speed},{sound},"
        f"afade=t=in:d=0.15,afade=t=out:st={fade_at:.3f}:d=0.25[a]"
    )


def check(cut: Cut, cut_span: Span | None, rules: Rules, tags: list[str]) -> list:
    """What a Short is refused or advised for, before anything is encoded."""
    found = []

    def finding(rule, severity, message):
        row = {"short": cut.n, "rule": rule, "severity": severity, "message": message}
        found.append(row)

    title = units(cut.title)
    if title > rules.title_chars:
        most = f"{rules.title_chars} at most"
        finding("title.length", "refuse", f"the title has {title} characters, {most}")
    low, high = rules.hashtags
    if not low <= len(tags) <= high:
        carries = f"a Short carries {low} to {high}"
        finding("tags.count", "refuse", f"{len(tags)} hashtags; {carries}")
    if not any(char.isdigit() for char in " ".join(cut.hook)):
        finding("hook.number", "advise", "the hook opens on no number")
    if cut_span is not None:
        least, most = rules.seconds
        seconds = f"{cut_span.length:.1f} s"
        if cut_span.length > rules.hard_seconds:
            limit = f"a Short is under {rules.hard_seconds:g} s"
            finding("length.hard", "refuse", f"{seconds}; {limit}")
        elif not least <= cut_span.length <= most:
            advice = f"a Short works at {least:g} to {most:g} s"
            finding("length.feed", "advise", f"{seconds}; {advice}")
    return found


def enforce(findings: list[dict]) -> None:
    for row in findings:
        if row["severity"] == "advise":
            print(f"short {row['short']}: {row['message']}", file=sys.stderr)
    refused = [
        f"  short {r['short']} {r['rule']}: {r['message']}"
        for r in findings
        if r["severity"] == "refuse"
    ]
    if refused:
        raise ValueError("shorts refused:\n" + "\n".join(refused))


def used_sources(plan: dict, cut_span: Span) -> list[str]:
    end, used, shots = cut_span.start + cut_span.clip, [], plan["shots"]
    for i, shot in enumerate(shots):
        until = shots[i + 1]["start"] if i + 1 < len(shots) else plan["length"]
        overlaps = shot["start"] < end and until > cut_span.start
        if ":" not in shot["src"] and overlaps and shot["src"] not in used:
            used.append(shot["src"])
    return used


def description(
    cut: Cut, language: str, link: str, tags: list[str], credits: list, notes: str
) -> str:
    labels = language_key(LABELS, language) or LABELS["en"]
    parts = [
        f"{labels['title'].format(n=units(cut.title))}\n{cut.title}",
        f"{labels['text']}\n{cut.text}",
    ]
    if link:
        parts.append(labels["link"].format(link=link))
    if credits:
        parts.append("\n".join(credits))
    if notes:
        parts.append(notes.strip())
    parts.append(" ".join(tags))
    return "\n\n".join(parts) + "\n"


def background(look: Look, path: Path) -> Path:
    """The channel's night colour with its accent glowing top right and bottom left."""
    from urdido import extras

    extras.require("shorts")
    from PIL import Image, ImageDraw, ImageFilter

    image = Image.new("RGB", (W, H), look.night)
    glow = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(glow)
    draw.ellipse((W - 620, -420, W + 520, 620), fill=110)
    draw.ellipse((-560, H - 640, 520, H + 380), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    image.paste(Image.new("RGB", (W, H), look.accent), (0, 0), glow)
    image.save(path)
    return path


def safe_area(ass: Path, root: Path, fonts: Path | None) -> None:
    """Hold the burned .ass to the provider's youtube-shorts bounds (PW698)."""
    from urdido import providers

    if not providers.available():
        why = providers.unavailable()
        print(f"shorts: the safe area is unchecked: {why}", file=sys.stderr)
        return
    answer = providers.safe_area(
        root,
        ass.relative_to(root).as_posix(),
        fonts.relative_to(root).as_posix() if fonts else None,
    )
    if not answer.get("passed", False):
        rows = []
        for row in answer.get("crossed", []):
            hits = ", ".join(f"{h['area']} by {h['by_px']} px" for h in row["crosses"])
            when = f"{row['start']:.2f}-{row['end']:.2f} s"
            rows.append(f'  {when} "{row["text"]}": {hits}')
        raise ValueError(
            f"shorts: {ass.name} reaches under the platform's controls:\n"
            + "\n".join(rows)
        )


def bounds(rules: Rules) -> dict[str, dict[str, float]]:
    """What the encoded file is held to: under the hard length, loudness within 1 LU
    of the target, true peak under -1 dBTP, and no frozen end to break the loop."""
    return {
        "video_seconds": {"max": rules.hard_seconds},
        "video_loudness": {"min": rules.loudness - 1, "max": rules.loudness + 1},
        "video_true_peak": {"max": -1.0},
        "video_frozen_end": {"max": 0.5},
    }


def spec_text(name: str, rules: Rules) -> str:
    rows = [f'asset = "{name}"']
    for measure, bound in bounds(rules).items():
        rows += ["", "[[predicate]]", f'id = "{measure}"', f'measure = "{measure}"']
        rows += [f"{key} = {value:g}" for key, value in bound.items()]
    return "\n".join(rows) + "\n"


def relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def measures(video: Path, root: Path, rules: Rules) -> dict | None:
    """Hold the encoded Short to the provider's video measures (PW697)."""
    from urdido import providers

    if not providers.available():
        why = providers.unavailable()
        print(f"shorts: {video.name} is unmeasured: {why}", file=sys.stderr)
        return None
    spec = video.parent / "work" / f"{video.stem}.spec.toml"
    spec.write_text(spec_text(video.stem, rules), encoding="utf-8")
    answer = providers.accept(root, relative(spec, root), relative(video, root))
    if not answer.get("passed", False):
        rows = []
        for row in answer.get("predicates", []):
            if not row.get("passed", False):
                low, high = row.get("min"), row.get("max")
                held = " to ".join(f"{v:g}" for v in (low, high) if v is not None)
                rows.append(f"  {row['measure']} is {row['value']}, held to {held}")
        raise ValueError(f"shorts: {video.name} misses its bounds:\n" + "\n".join(rows))
    return answer


@dataclass
class Declared:
    here: Path
    spec: dict
    rules: Rules
    look: Look
    cuts: list[Cut]

    def path(self, key: str, **names) -> Path:
        return self.here / self.spec[key].format(**names)


def declared(declaration: Path) -> Declared:
    document = tomllib.loads(declaration.read_text(encoding="utf-8"))
    if "shorts" not in document:
        raise ValueError(f"shorts: {declaration.name} declares no [shorts]")
    spec = document["shorts"]
    from urdido.declaration import shorts_cutter

    if shorts_cutter(spec) == "selection":
        raise ValueError(
            f"shorts: {declaration.name}'s [shorts] declares a scenes selection, which "
            "`urdido build --cut short:<c>` cuts; urdido shorts reads plan, picture, "
            "mix, words, out, tags and [[shorts.cut]]"
        )
    needed = ("plan", "picture", "mix", "words", "out", "tags", "cut")
    missing = [key for key in needed if key not in spec]
    if missing:
        raise ValueError(f"shorts: [shorts] needs {', '.join(missing)}")
    return Declared(
        declaration.parent,
        spec,
        rules_of(spec.get("rules", {})),
        look_of(spec.get("look", {})),
        cuts_of(spec["cut"]),
    )


def pointer_of(d: Declared, language: str) -> tuple[str, str]:
    declared_pointer = language_key(d.spec.get("pointer", {}), language)
    if declared_pointer:
        return declared_pointer["lead"], declared_pointer["key"]
    default = language_key(POINTER, language)
    if not default:
        raise ValueError(
            f"shorts: no pointer to the full video in {language}; "
            f"declare [shorts.pointer.{language}] lead and key"
        )
    return default


def credits_of(d: Declared, plan: dict, cut_span: Span) -> list[str]:
    if not d.spec.get("sources"):
        return []
    file = d.here / d.spec["sources"]
    sources = json.loads(file.read_text(encoding="utf-8-sig"))
    template = d.spec.get("credit", "- {title} ({url})")
    used = used_sources(plan, cut_span)
    return [template.format(**sources[key]) for key in used if key in sources]


def cut_one(d: Declared, cut: Cut, plan: dict, language: str) -> Path:
    tags = list(d.spec["tags"])
    cut_span = span(plan, cut, d.rules)
    enforce(check(cut, cut_span, d.rules, tags))
    pointer = pointer_of(d, language)
    words = {}
    for segment in cut_span.segments:
        file = d.path("words", language=language, take=segment["take"])
        words[segment["take"]] = json.loads(file.read_text(encoding="utf-8"))["words"]
    out = d.path("out", n=cut.n, language=language)
    work = out.parent / "work"
    work.mkdir(parents=True, exist_ok=True)
    ass = work / f"{out.name}.ass"
    fixes = d.spec.get("fixes")
    text = subtitles(plan, cut, cut_span, words, d.look, d.rules, pointer, fixes)
    ass.write_text(text, encoding="utf-8")
    fonts = (d.here / d.look.fonts).resolve() if d.look.fonts else None
    safe_area(ass, d.here, fonts)
    spans = punches(plan, cut_span.start, cut_span.voice_end + d.rules.tail, d.rules)
    still = background(d.look, work / "short-background.png")
    video = out.with_suffix(".mp4")
    start, clip, length = f"{cut_span.start}", f"{cut_span.clip}", f"{cut_span.length}"
    media.ffmpeg(
        ["-ss", start, "-t", clip, "-i", str(d.path("picture"))]
        + ["-ss", start, "-t", clip, "-i", str(d.path("mix"))]
        + ["-loop", "1", "-framerate", "30", "-t", length, "-i", str(still)]
        + ["-filter_complex", graph(cut_span, spans, d.look, d.rules, ass, fonts)]
        + ["-map", "[v]", "-map", "[a]", "-t", length]
        + ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-r", "30"]
        + ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(video)]
    )
    measures(video, d.here, d.rules)
    notes = language_key(d.spec.get("notes", {}), language) or ""
    credits = credits_of(d, plan, cut_span)
    link = d.spec.get("link", "")
    written = description(cut, language, link, tags, credits, notes)
    out.with_suffix(".txt").write_text(written, encoding="utf-8")
    print(
        f"wrote {video} ({cut_span.length:.1f} s from {cut_span.start:.1f} s "
        f"of the full video, {len(spans)} punch-ins)"
    )
    return video


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="urdido shorts")
    p.add_argument("declaration")
    p.add_argument("numbers", nargs="*", type=int, help="the Shorts; every one if none")
    p.add_argument("--language", required=True)
    p.add_argument("--check", action="store_true", help="check only; encode nothing")
    args = p.parse_args(argv)
    try:
        d = declared(Path(args.declaration).resolve())
        known = {cut.n: cut for cut in d.cuts}
        unknown = [str(n) for n in args.numbers if n not in known]
        if unknown:
            raise ValueError(f"shorts: no [[shorts.cut]] numbered {', '.join(unknown)}")
        chosen = [known[n] for n in args.numbers] or d.cuts
        plan_file = d.path("plan")
        plan = None
        if plan_file.exists():
            plan = json.loads(plan_file.read_text(encoding="utf-8"))
        if args.check:
            tags = list(d.spec["tags"])
            findings = []
            for cut in chosen:
                cut_span = span(plan, cut, d.rules) if plan else None
                findings += check(cut, cut_span, d.rules, tags)
            enforce(findings)
            unbuilt = f"; {plan_file.name} is not built, so lengths are unchecked"
            print(f"shorts: {len(chosen)} pass" + ("" if plan else unbuilt))
            return 0
        if plan is None:
            raise ValueError(f"shorts: {plan_file} is not built yet")
        for cut in chosen:
            cut_one(d, cut, plan, args.language)
    except (ValueError, FileNotFoundError) as refused:
        print(refused, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
