"""The explainer pipeline: narration over Creative Commons shots (UR4).

Ported from the Japode videos' `bin/build.py`. Each line of the script plays over the
shots `[source] shots` declares for its take (`{"src": "<id>", "at": 12.0, "dur": 3,
"speed": 1.0, "box": [...]}`, a shot with no `dur` sharing what the fixed ones leave),
read from `<footage>/src/<id>.mp4`, or from a film of our own, `<kind>:<scene>`
(`<footage>/<kind>/<scene>.webm`, a terminal or a page). Each declared keyword pops in
when its take says it, found in the take's word times.

    [source]
    kind = "explainer"
    shots = "shots.json"
    footage = "footage"        # the default
    lead = 0.4                 # silence before the first line
    gap = 0.5                  # the breath after each line
    end = 4.5                  # the closing hold after the last line

`--plan` writes the plan (`<name>.<l>.plan.json`: segments, shots, callouts, length),
the same plan `urdido shorts` cuts from. A full build renders it: each shot fitted to
the frame (a film over a blurred copy of itself, panned slowly) and joined with hard
cuts; the title, the callouts and the closing card drawn in the styles `[source]
styles` names (a file of ASS `Style:` lines, `[source] fonts` their folder) with the
closing words from `[source.closing.<language>]`; the corner mark from `[mark]`; the
takes mixed over `[music] bed` at `under`; the narration's captions beside it as the
`.srt`; and the result measured as every build is.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from urdido import media
from urdido.declaration import DEFAULTS, SHOT, held, setting
from urdido.errors import DeclarationError, Refused
from urdido.narration import Takes
from urdido.pipelines.finishing import Finishing

LEAD, GAP, END = (DEFAULTS["source"][key] for key in ("lead", "gap", "end"))


def lines(script: dict, language: str) -> list[tuple[str, str, int | None]]:
    """Every line in order: its take, its text, and the chapter it opens."""
    out = [("intro", script["intro"][language], None)]
    for n, chapter in script["chapters"].items():
        out.append((f"chapter-{n}", chapter["card"][language], int(n)))
        out.append((f"chapter-{n}-result", chapter["result"][language], None))
    out.append(("outro", script["outro"][language], None))
    return out


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return re.sub(
        r"[^a-z0-9]", "", "".join(c for c in text if not unicodedata.combining(c))
    )


def callouts(segments: list[dict], declared: dict, words_of) -> list[list]:
    """Each declared keyword when its take says it: `[at, until, show, definition]`.

    A keyword with `def` stays longer (5 s, else 2.8 s) and carries its definition; each
    holds until the next one. Words compare without spaces or hyphens ("write-ahead log"
    and "write ahead log" are one keyword)."""
    out = []
    for seg in segments:
        wanted = declared.get(seg["take"], [])
        if not wanted:
            continue
        tokens = [(fold(w["text"]), w["start"]) for w in words_of(seg)]
        found, k = [], 0
        for c in wanted:
            target = fold(c.get("hear", c["show"]))
            hit, end = None, k
            for i in range(k, len(tokens)):
                joined, j = "", i
                while j < len(tokens) and len(joined) < len(target):
                    joined += tokens[j][0]
                    j += 1
                if joined == target:
                    hit, end = i, j
                    break
            if hit is None:
                heard = c.get("hear", c["show"])
                raise Refused(f'{seg["take"]}: "{heard}" is not heard in the take')
            found.append(
                (seg["voice_at"] + tokens[hit][1], c["show"], c.get("def", ""))
            )
            k = end
        end_of_line = seg["voice_at"] + seg["voice"] + 0.3
        for j, (a, show, meaning) in enumerate(found):
            following = found[j + 1][0] - 0.08 if j + 1 < len(found) else end_of_line
            hold = 5.0 if meaning else 2.8
            out.append([round(a, 3), round(min(a + hold, following), 3), show, meaning])
    return out


def plan(
    script: dict,
    shots_doc: dict,
    language: str,
    *,
    take_file,
    seconds,
    source_file,
    words_of,
    lead=LEAD,
    gap=GAP,
    end=END,
) -> dict:
    """The explainer's timeline: when each line is said, the shots under it, the
    callouts. `take_file(name)`, `seconds(path)`, `source_file(src)` and
    `words_of(segment)` are the build's, so this is a pure function of them."""
    by_take = {s["take"]: s["shots"] for s in shots_doc["segments"]}
    t, segments, shots = lead, [], []
    script_lines = lines(script, language)
    for i, (take, text, chapter) in enumerate(script_lines):
        file = take_file(take)
        if not Path(file).exists():
            raise Refused(f"missing take {file}: buy the narration first")
        voice = seconds(file)
        length = voice + (end if i == len(script_lines) - 1 else gap)
        if i == 0:
            length += lead  # the first shots also cover the lead-in
        start = 0.0 if i == 0 else t
        segments.append(
            {
                "take": take,
                "file": str(file),
                "voice_at": round(t, 3),
                "voice": round(voice, 3),
                "start": round(start, 3),
                "length": round(length, 3),
                "text": text,
                "chapter": chapter,
            }
        )
        declared = by_take.get(take)
        if not declared:
            raise DeclarationError(f"the shots declare nothing for {take}")
        fixed = sum(s["dur"] for s in declared if "dur" in s)
        free = [s for s in declared if "dur" not in s]
        share = (length - fixed) / len(free) if free else 0
        if free and share < 1.5:
            raise DeclarationError(f"{take}: {share:.1f} s per free shot is too short")
        at = start
        for s in declared:
            dur = s.get("dur", share)
            path = source_file(s["src"])
            speed = held(s, SHOT, "speed")
            begin = min(s["at"], max(0.0, seconds(path) - dur * speed - 0.05))
            shots.append(
                {
                    "src": s["src"],
                    "file": str(path),
                    "at": round(begin, 3),
                    "dur": round(dur, 3),
                    "speed": speed,
                    "still": ":" in s["src"],
                    "start": round(at, 3),
                    **({"box": s["box"]} if "box" in s else {}),
                }
            )
            at += dur
        t = start + length if i else length
    for seg in segments:
        inside = [
            s
            for s in shots
            if seg["start"] <= s["start"] < seg["start"] + seg["length"] - 1e-6
        ]
        total = sum(s["dur"] for s in inside)
        if abs(total - seg["length"]) > 0.05:
            raise DeclarationError(
                f"{seg['take']}: shots last {total:.2f} s, the line "
                f"{seg['length']:.2f} s"
            )
    return {
        "title": shots_doc["title"],
        "script": script,
        "segments": segments,
        "shots": shots,
        "callouts": callouts(segments, shots_doc.get("callouts", {}), words_of),
        "length": round(t, 3),
    }


class Explainer(Finishing):
    """The explainer pipeline."""

    def explainer(self) -> int:
        source = self.decl["source"]
        script = self.load(self.decl["narration"]["script"])
        shots_doc = self.load(source["shots"])
        takes = Takes(
            script,
            self.path(self.decl["narration"]["takes"]),
            setting(self.decl, "narration", "tempo"),
        )
        footage = Path(self.path(setting(self.decl, "source", "footage")))

        def source_file(src: str) -> Path:
            kind, _, scene = src.partition(":")
            return (
                footage / kind / f"{scene}.webm"
                if scene
                else footage / "src" / f"{src}.mp4"
            )

        def words_of(segment: dict) -> list[dict]:
            take = Path(segment["file"])
            record = take.with_suffix(".words.json")
            if not record.exists():
                raise Refused(f"no word times for {segment['take']}: run urdido words")
            words = json.loads(record.read_text(encoding="utf-8"))
            if words["sha256"] != hashlib.sha256(take.read_bytes()).hexdigest():
                raise Refused(f"{record.name} is of an older take: run urdido words")
            return words["words"]

        made = plan(
            script,
            shots_doc,
            self.language,
            take_file=lambda name: Path(takes.take_file(self.language, name)),
            seconds=lambda path: media.seconds(str(path)),
            source_file=source_file,
            words_of=words_of,
            lead=setting(self.decl, "source", "lead"),
            gap=setting(self.decl, "source", "gap"),
            end=setting(self.decl, "source", "end"),
        )
        file = self.write_plan(self.name, made)
        print(
            f"{file}: {len(made['segments'])} lines, {len(made['shots'])} shots, "
            f"{made['length']:.1f} s"
        )
        if self.args.plan:
            return 0
        return self.render_explainer(made, source)

    def render_explainer(self, made: dict, source: dict) -> int:
        """Shots, titles and callouts, the mix, the corner mark, the captions beside."""
        work = self.parts / "explainer"
        (work / "shots").mkdir(parents=True, exist_ok=True)
        files = [
            render_shot(i, shot, work / "shots") for i, shot in enumerate(made["shots"])
        ]
        listing = work / "shots.txt"
        listing.write_text(
            "".join(f"file '{f.as_posix()}'\n" for f in files), encoding="utf-8"
        )
        picture = work / "picture.mp4"
        media.ffmpeg(
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listing),
                "-c",
                "copy",
                str(picture),
            ]
        )
        styles = (
            Path(self.path(source["styles"])).read_text(encoding="utf-8").strip()
            if source.get("styles")
            else DEFAULT_STYLES
        )
        closing = (source.get("closing") or {}).get(self.language, {})
        ass = work / "titles.ass"
        ass.write_text(
            titles(made, styles, closing, setting(self.decl, "source", "end")),
            encoding="utf-8",
        )
        srt = self.out / f"{self.name}.{self.language}.srt"
        srt.write_text(captions_srt(made), encoding="utf-8", newline="")
        music = self.decl.get("music") or {}
        bed = self.path(music["bed"]) if music.get("bed") else None
        sound = work / "mix.wav"
        mixed(made, bed, sound, music.get("under", 0.07))
        burn = f"subtitles='{filter_path(ass)}'"
        if source.get("fonts"):
            burn += f":fontsdir='{filter_path(Path(self.path(source['fonts'])))}'"
        titled = work / "titled.mp4"
        length = made["length"]
        media.ffmpeg(
            [
                "-i",
                str(picture),
                "-vf",
                f"{burn},fade=t=in:d=0.6,fade=t=out:st={length - 0.8:.3f}:d=0.8",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                str(titled),
            ]
        )
        if self.decl.get("mark"):
            from urdido import mark

            titled = Path(
                mark.overlay(
                    str(titled),
                    mark.declared(self.decl["mark"], self.path),
                    self.parts,
                    "x264",
                    self.frame().height,
                )
            )
        final = self.out / f"{self.name}.{self.language}.mp4"
        track = self.decl["video"]["languages"][self.language]
        media.ffmpeg(
            [
                "-i",
                str(titled),
                "-i",
                str(sound),
                "-map",
                "0:v",
                "-map",
                "1:a",
                "-t",
                f"{length}",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-metadata:s:a:0",
                f"language={track}",
                "-movflags",
                "+faststart",
                str(final),
            ]
        )
        print(self.checked_output(str(final)))
        if self.decl.get("description"):
            self.describe_explainer(made, source)
        return 0

    def describe_explainer(self, made: dict, source: dict) -> Path:
        """The description: the summary, chapters from the plan, and the credits of the
        footage the cut actually shows (`[source] sources` names each clip's title,
        channel and URL; `[description]` its licence label, URL and changes)."""
        from urdido.publish.description import format_description, write
        from urdido.publish.strings import strings

        options = self.decl["description"]
        words = strings(self.language, options.get("strings"))
        catalogue = self.load(source["sources"]) if source.get("sources") else {}
        intro = (made["script"].get("introTitle") or {}).get(self.language)
        chapters = [f"0:00 {intro or words['intro']}"]
        for segment in made["segments"]:
            if segment["chapter"] is not None:
                at = int(segment["start"])
                title = made["script"]["chapters"][str(segment["chapter"])]["title"]
                chapters.append(f"{at // 60}:{at % 60:02} {title[self.language]}")
        used = dict.fromkeys(s["src"] for s in made["shots"] if ":" not in s["src"])
        missing = [key for key in used if key not in catalogue]
        if missing:
            raise DeclarationError(
                f"[source] sources has no credit for {', '.join(missing)}"
            )
        credits = [
            {
                "title": catalogue[key]["title"],
                "author": catalogue[key]["channel"],
                "url": catalogue[key]["url"],
                "license": options["license_label"],
                "license_url": options.get("license_url", ""),
                "changes": options.get("changes", ""),
            }
            for key in used
        ]
        text = format_description(
            options["summary"],
            chapters,
            credits,
            sources=options.get("sources", []),
            notes=options.get("notes", ""),
            generated=options.get("generated", ""),
            words=words,
        )
        return write(
            self.out,
            f"{self.name}.{self.language}",
            text,
            {"assets": credits, "chapters": chapters},
        )


#: Title, keyword, definition and closing styles, used where `[source] styles` names
#: none; a channel declares its own fonts and colours in that file.
_FORMAT = (
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
    "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
    "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
)
_WHITE = "&H00FFFFFF"
# name, size, primary, outline colour, back, outline px, alignment, side margin, bottom
_ROWS = [
    ("Key", 84, "&H00111111", _WHITE, "&H00000000", 22, 2, 120, 80),
    ("Def", 42, _WHITE, "&H64000000", "&H00000000", 12, 2, 160, 40),
    ("Title", 140, _WHITE, "&H40000000", "&H00000000", 26, 5, 120, 0),
    ("Sub", 62, _WHITE, "&H40000000", "&H00000000", 16, 5, 120, 0),
    ("Credit", 34, "&H00F0F0F0", "&H90000000", "&H00000000", 10, 2, 120, 64),
]
DEFAULT_STYLES = "\n".join(
    [_FORMAT]
    + [
        f"Style: {name},Arial,{size},{primary},{_WHITE},{outline},{back},"
        f"0,0,0,0,100,100,0,0,3,{width},0,{align},{side},{side},{bottom},1"
        for name, size, primary, outline, back, width, align, side, bottom in _ROWS
    ]
)
W, H, FPS, PAN = 1920, 1080, 30, 1.06


def filter_path(path: Path) -> str:
    return path.as_posix().replace(":", r"\:")


def render_shot(i: int, shot: dict, work: Path) -> Path:
    """One shot fitted to the frame: a 4:3 film over a blurred copy of itself, panned
    slowly (alternating directions), or a film of our own drawn whole. Kept beside a
    stamp of the shot, so an unchanged shot is not encoded again."""
    out = work / f"{i:03d}.mp4"
    stamp = out.with_suffix(".json")
    key = json.dumps(shot, sort_keys=True)
    if out.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == key:
        return out
    still = shot["still"]
    cw, ch = (W, H) if still else (int(W * PAN) // 2 * 2, int(H * PAN) // 2 * 2)
    d = shot["dur"]
    if still:
        x = "(iw-ow)/2"
    else:
        x = f"(iw-ow)*t/{d}" if i % 2 == 0 else f"(iw-ow)*(1-t/{d})"
    box = ""
    if shot.get("box"):
        x0, y0, x1, y1 = shot["box"]
        box = f"crop=iw*{x1 - x0}:ih*{y1 - y0}:iw*{x0}:ih*{y0},"
    graph = (
        f"[0:v]setpts=(PTS-STARTPTS)/{shot['speed']},{box}fps={FPS},split[a][b];"
        f"[a]scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch},"
        "boxblur=24:2,eq=brightness=-0.08[bg];"
        f"[b]scale={cw}:{ch}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,crop={W}:{H}:x='{x}':y='(ih-oh)/2',setsar=1,"
        "format=yuv420p[v]"
    )
    media.ffmpeg(
        [
            "-ss",
            f"{shot['at']}",
            "-t",
            f"{d * shot['speed'] + 0.2}",
            "-i",
            shot["file"],
            "-filter_complex",
            graph,
            "-map",
            "[v]",
            "-t",
            f"{d}",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "16",
            "-r",
            str(FPS),
            str(out),
        ]
    )
    got = media.seconds(str(out))
    if got < d - 0.1:
        raise Refused(
            f"shot {i} ({shot['src']} at {shot['at']}): {got:.2f} s of {d:.2f} s"
        )
    stamp.write_text(key, encoding="utf-8")
    return out


def stamp_ass(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def titles(made: dict, styles: str, closing: dict, end: float = END) -> str:
    """The title over the opening, each callout when it is said (with its definition),
    and the closing card's words, as the declaration gives them."""
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {W}\nPlayResY: {H}\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        f"[V4+ Styles]\n{styles}\n\n[Events]\nFormat: Layer, Start, End, Style, "
        "Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    title, _, subtitle = made["title"].partition(": ")
    events = [
        f"Dialogue: 1,{stamp_ass(0.6)},{stamp_ass(5.2)},Title,,0,0,0,,"
        f"{{\\fad(400,500)\\pos(960,450)}}{title}"
    ]
    if subtitle:
        events.append(
            f"Dialogue: 1,{stamp_ass(1.0)},{stamp_ass(5.2)},Sub,,0,0,0,,"
            f"{{\\fad(400,500)\\pos(960,610)}}{subtitle}"
        )
    for a, b, text, meaning in made["callouts"]:
        y = 900 if meaning else 968
        events.append(
            f"Dialogue: 3,{stamp_ass(a)},{stamp_ass(b)},Key,,0,0,0,,"
            f"{{\\an2\\pos(960,{y})\\fad(120,260)\\fscx72\\fscy72"
            f"\\t(0,200,\\fscx100\\fscy100)}}{text}"
        )
        if meaning:
            events.append(
                f"Dialogue: 3,{stamp_ass(a + 0.25)},{stamp_ass(b)},Def,,0,0,0,,"
                f"{{\\an2\\pos(960,1000)\\fad(200,260)}}{meaning}"
            )
    length = made["length"]
    for key, style, y, delay in (
        ("title", "Title", 420, 0.2),
        ("sub", "Sub", 580, 0.5),
        ("credit", "Credit", None, 0.8),
    ):
        if closing.get(key):
            place = f"\\pos(960,{y})" if y else ""
            events.append(
                f"Dialogue: 1,{stamp_ass(length - end + delay)},"
                f"{stamp_ass(length)},{style},,0,0,0,,"
                f"{{\\fad(500,0){place}}}{closing[key]}"
            )
    return head + "\n".join(events) + "\n"


def captions_srt(made: dict) -> str:
    """The narration as side captions, each line's words timed across its take."""
    from urdido import captions

    cues = captions.narration_cues(
        [
            {"at": s["voice_at"], "length": s["voice"], "text": s["text"]}
            for s in made["segments"]
        ]
    )
    return captions.srt(cues)


def mixed(made: dict, bed: str | None, out: Path, under: float = 0.07) -> Path:
    """The takes at their places over the bed, ducked under the voice, at -14 LUFS."""
    takes = made["segments"]
    inputs, parts = [], []
    for seg in takes:
        inputs += ["-i", seg["file"]]
    n = len(takes)
    for i, seg in enumerate(takes):
        ms = int(round(seg["voice_at"] * 1000))
        parts.append(
            f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,"
            f"adelay={ms}|{ms}[v{i}]"
        )
    parts.append(
        "".join(f"[v{i}]" for i in range(n))
        + f"amix=inputs={n}:normalize=0,apad,atrim=0:{made['length']}[voice]"
    )
    if bed and Path(bed).exists():
        inputs += ["-stream_loop", "-1", "-i", bed]
        fade = made["length"] - 3.5
        parts += [
            "[voice]asplit[vo][key]",
            f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,"
            f"atrim=0:{made['length']},volume={under},afade=t=in:d=1.5,"
            f"afade=t=out:st={fade}:d=3.5[bed]",
            "[bed][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=450:"
            "makeup=1[ducked]",
            "[vo][ducked]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[out]",
        ]
    else:
        parts.append("[voice]loudnorm=I=-14:TP=-1.5:LRA=11[out]")
    media.ffmpeg(
        [
            *inputs,
            "-filter_complex",
            ";".join(parts),
            "-map",
            "[out]",
            "-ar",
            "48000",
            "-t",
            str(made["length"]),
            str(out),
        ]
    )
    return out
