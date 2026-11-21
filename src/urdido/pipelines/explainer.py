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

This slice plans: `urdido build <video.toml> --language <l> --plan` writes the plan
(`<name>.<l>.plan.json`: segments, shots, callouts, length), the same plan
`urdido shorts` cuts from. Rendering the shots, the captions and the mix is UR4's next
step; until then a full build is refused by name.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from urdido import media
from urdido.errors import DeclarationError, Refused
from urdido.narration import Takes
from urdido.pipelines.finishing import Finishing

LEAD, GAP, END = 0.4, 0.5, 4.5


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
            speed = s.get("speed", 1.0)
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
            self.decl["narration"].get("tempo", 1.0),
        )
        footage = Path(self.path(source.get("footage", "footage")))

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
            lead=source.get("lead", LEAD),
            gap=source.get("gap", GAP),
            end=source.get("end", END),
        )
        file = self.write_plan(self.name, made)
        print(
            f"{file}: {len(made['segments'])} lines, {len(made['shots'])} shots, "
            f"{made['length']:.1f} s"
        )
        if self.args.plan:
            return 0
        raise Refused(
            "urdido build: an explainer is planned but not yet rendered by "
            "urdido (UR4); build with --plan, or with the video's own script"
        )
