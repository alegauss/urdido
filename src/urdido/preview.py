"""VM57 / PW713: motion review from production beat clips and the full production mix."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from videomaker import cache, captions, keywords, media
from videomaker.assemble.scenes import ScenesVideo
from videomaker.cards.html import Frame
from videomaker.sources.illustrated import scenes
from videomaker.sources.model import RecordingRefused
from videomaker.timeline import plan


def select(selector, shots, placed, total, *, before=0, after=0, occurrence=None):
    """Resolve one unambiguous selection, then expand and snap outwards to 30 fps."""
    if any(not math.isfinite(value) or value < 0 for value in (before, after)):
        raise RecordingRefused("preview context must be finite and nonnegative")
    kind, _, value = selector.partition(":")
    if kind == "time":
        try:
            start, end = map(float, value.split(":"))
        except ValueError:
            raise RecordingRefused("preview interval is time:START:END in seconds") from None
    elif kind in {"take", "beat"}:
        found = [s for s in shots if (s["take"] == value if kind == "take" else value in {s["beat"], s["id"]})]
        if not found or (kind == "beat" and len(found) != 1):
            raise RecordingRefused(f"preview {kind} {value!r} is missing or ambiguous")
        start, end = min(s["start"] for s in found), max(s["end"] for s in found)
    elif kind == "cue":
        name, _, phrase = value.partition(":")
        found = [p for p in placed if Path(p["file"]).stem == name]
        if len(found) != 1 or not phrase:
            raise RecordingRefused("spoken preview is cue:TAKE:PHRASE")
        take = found[0]
        file = Path(take["file"])
        spec = {"text": phrase, **({"occurrence": occurrence} if occurrence is not None else {})}
        local = keywords.anchor(file, spec)
        words = keywords.word_record(file)
        first, last = next(pair for pair in keywords.matches(words, phrase) if words[pair[0]]["start"] == local)
        start, end = take["at"] + local, take["at"] + words[last - 1]["end"]
    else:
        raise RecordingRefused("preview selects take:NAME, beat:ID, cue:TAKE:PHRASE or time:START:END")
    if not all(math.isfinite(t) for t in (start, end)) or not 0 <= start < end <= total + 0.001:
        raise RecordingRefused("preview interval must increase within the production timeline")
    first = max(0, math.floor((start - before) * 30 + 1e-7))
    last = min(round(total * 30), math.ceil((end + after) * 30 - 1e-7))
    return first / 30, last / 30


def clip_cues(cues, start, end):
    return [captions.Cue(max(c.start, start) - start, min(c.end, end) - start, c.text)
            for c in cues if c.start < end and c.end > start]


def render(build, document, script, cards, theme, takes, encoder):
    source = scenes(document, takes, theme, build.language, str(build.here), str(build.parts), render=False, encoder=encoder)
    video = ScenesVideo(name=build.name, language=build.language, frame=Frame(1920, 1080), scenes=source,
                        takes=takes, script=script, theme=theme, words=cards["words"][build.language],
                        parts=str(build.parts), encoder=encoder, intro=build.intro())
    timeline = video.compose(render=False)
    data = plan(timeline)
    placed = data["spoken"][build.language]
    edit = json.loads((build.parts / "illustrated/edit.json").read_text("utf-8"))
    beats = {f"{take}-{i}": beat for take, rows in document["scenes"].items() for i, beat in enumerate(rows)}
    opening_frame_time = round(video.opening * 30) / 30
    total = round(data["total"] * 30) / 30
    shots = [{**s, "id": beats[s["beat"]].get("id", s["beat"]),
              "start": opening_frame_time + s["at"], "end": opening_frame_time + s["at"] + s["seconds"]} for s in edit["beats"]]
    start, end = select(build.args.preview, shots, placed, total,
                        before=build.args.context_before, after=build.args.context_after,
                        occurrence=build.args.preview_occurrence)
    chosen = [s for s in shots if s["start"] < end - 1e-7 and s["end"] > start + 1e-7]
    identity = hashlib.sha256(json.dumps([build.language, start, end]).encode()).hexdigest()[:12]
    folder = build.out if build.revision else build.out / "previews" / identity
    folder.mkdir(parents=True, exist_ok=True)
    parts = build.parts / "previews" / identity
    parts.mkdir(parents=True, exist_ok=True)
    tracks = [(build.language, build.decl["video"]["languages"][build.language], captions.narration_cues(placed)),
              *build.translated_tracks(placed)]
    report = {"selector": build.args.preview, "production_start": start, "production_end": end,
              "first_frame": round(start * 30), "end_frame_exclusive": round(end * 30), "fps": 30,
              "beats": chosen, "captions": [], "audio": "Full production mix, trimmed after normalization"}
    subtitles = []
    for language, track, cues in tracks:
        clipped = clip_cues(cues, start, end)
        for cue in cues:
            if cue.start < end and cue.end > start:
                report["captions"].append({"language": language, "text": cue.text,
                    "production_start": cue.start, "production_end": cue.end,
                    "preview_start": max(cue.start, start) - start, "preview_end": min(cue.end, end) - start})
        for ext, text in (("srt", captions.srt(clipped)), ("vtt", captions.vtt(clipped))):
            (folder / f"{build.name}.{language}.{ext}").write_text(text, encoding="utf-8", newline="")
        subtitles.append((track, str(folder / f"{build.name}.{language}.srt")))
    highlight_spec = build.decl.get("highlights")
    declaration = build.load(highlight_spec["declaration"]) if highlight_spec else None
    timed = keywords.cues(placed, declaration["lines"]) if declaration else []
    report["highlights"] = [{**c, "production_at": c["at"], "production_end": c["end"],
                             "at": c["at"] - start, "end": c["end"] - start}
                            for c in timed if c["at"] < end and c["end"] > start]
    metadata = folder / f"{build.name}.{build.language}.preview.json"
    if build.args.plan:
        metadata.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"preview plan: production {start:.3f}..{end:.3f}s; {metadata}")
        return 0
    metadata.unlink(missing_ok=True)
    scenes(document, takes, theme, build.language, str(build.here), str(build.parts), render=True, encoder=encoder,
           beat_keys={s["beat"] for s in chosen})
    pieces = []
    origin = chosen[0]["start"] if chosen else 0
    if video.intro and start < video.opening:
        pieces.append(str(build.parts / "opening.mp4"))
        origin = 0
    pieces.extend(str(build.parts / "illustrated" / f"{s['beat']}.mp4") for s in chosen)
    runtime = media.media(1920, 1080, str(parts), encoder=encoder)
    joined = runtime.concat(pieces, "selected.mp4")
    if declaration:
        picture = keywords.overlay(joined, placed, declaration, parts, build.path(highlight_spec["fonts"]), encoder,
                                   window=(start, end), origin=origin)
    else:
        picture = str(parts / "picture.mp4")
        args = ["-i", joined, "-vf", f"trim=start={start-origin:.9f}:end={end-origin:.9f},setpts=PTS-STARTPTS",
                *media.video_codec(encoder, 20), "-an", picture]
        cache.run("preview picture", [picture], args, lambda: media.ffmpeg(args), inputs=[__file__, media.__file__, joined], tools=["ffmpeg"])
    # MP4's format duration rounds its 30 fps video duration up to milliseconds,
    # exactly as the full production concat consumed by scene_voice does.
    voice = build.scene_voice(video, placed, math.ceil(total * 1000 - 1e-7) / 1000)
    output = folder / f"{build.name}.{build.language}.mp4"
    args = ["-i", picture, "-ss", f"{start:.9f}", "-i", voice,
            *[arg for _, file in subtitles for arg in ("-i", file)],
            "-map", "0:v", "-map", "1:a", *[arg for i in range(len(subtitles)) for arg in ("-map", f"{i+2}:s")],
            "-t", f"{end-start:.9f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-c:s", "mov_text",
            "-metadata:s:a:0", f"language={build.decl['video']['languages'][build.language]}",
            *[arg for i, (track, _) in enumerate(subtitles) for arg in (f"-metadata:s:s:{i}", f"language={track}")], str(output)]
    cache.run("preview mux", [output], args, lambda: media.ffmpeg(args),
              inputs=[__file__, picture, voice, *[file for _, file in subtitles]], tools=["ffmpeg"])
    build.checked_output(str(output))
    report["sha256"] = cache.file_hash(output)
    metadata.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"preview: production {start:.3f}..{end:.3f}s; {output}")
    return 0
