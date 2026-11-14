"""VM41: source stills paired with the words actually overlapping each beat.

PW708 tracks exact-time, editorially labelled contact sheets in polyweave.
"""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

from videomaker import captions, media
from videomaker.cards.html import Frame
from videomaker.cards.render import render
from videomaker.sources.model import RecordingRefused


def words(placed: list[dict]) -> list[dict]:
    timed = []
    for take in placed:
        audio = Path(take["file"])
        record = audio.with_suffix(".words.json")
        if not record.is_file():
            raise RecordingRefused(f"{audio.stem}: review needs word times; run videomaker.narration_words")
        data = json.loads(record.read_text(encoding="utf-8"))
        if data["sha256"] != hashlib.sha256(audio.read_bytes()).hexdigest():
            raise RecordingRefused(f"{audio.stem}: stale review word times; transcribe the current take")
        timed.extend({"text": w["text"], "at": take["at"] + w["start"],
                      "end": take["at"] + w["end"]} for w in data["words"])
    return timed


def rows(document: dict, edit: dict, placed: list[dict], highlights: list[dict], opening: float = 0) -> list[dict]:
    timed = words(placed)
    cues = captions.narration_cues(placed)
    beats = {f"{take}-{i}": beat for take, items in document["scenes"].items()
             for i, beat in enumerate(items)}
    result = []
    for shot in edit["beats"]:
        beat = beats[shot["beat"]]
        start, end = shot["at"] + opening, shot["at"] + opening + shot["seconds"]
        asset = document.get("media", {}).get(beat.get("asset"), {})
        overlap = lambda at, until: at < end and until > start
        result.append({"beat": shot["beat"], "start": start, "end": end,
                       "source": asset.get("file"), "source_start": beat.get("at", 0),
                       "source_end": beat.get("at", 0) + shot["seconds"],
                       "source_url": asset.get("url"), "source_title": asset.get("title"),
                       "layout": beat.get("layout", "date"),
                       "spoken": " ".join(w["text"] for w in timed if overlap(w["at"], w["end"])),
                       "captions": [c.text for c in cues if overlap(c.start, c.end)],
                       "highlights": [h["show"] for h in highlights if overlap(h["at"], h["end"])],
                       "on_screen": [beat.get("caption", beat["title"]), beat.get("text", "")],
                       "tags": {k: beat.get(k, asset.get(k, [])) for k in ("people", "events", "topics")}})
    return result


def sheet(document: dict, edit: dict, placed: list[dict], highlights: list[dict],
          folder: Path, parts: Path, out: Path, *, opening: float = 0) -> Path:
    data = rows(document, edit, placed, highlights, opening)
    review = out / "review"
    review.mkdir(parents=True, exist_ok=True)
    pages = {r["beat"]: (parts / "illustrated" / f"{r['beat']}.html").read_text(encoding="utf-8")
             for r in data if not r["source"]}
    if pages:
        render(pages, Frame(1920, 1080), str(review))
    for row in data:
        image = review / f"{row['beat']}.png"
        if row["source"]:
            source = (folder / row["source"]).resolve()
            seek = ["-ss", str(row["source_start"] + (row["end"] - row["start"]) / 2)] \
                if row["layout"] == "footage" else []
            image.unlink(missing_ok=True)
            media.ffmpeg([*seek, "-i", str(source), "-frames:v", "1",
                          "-vf", "scale=640:-2", str(image)])
        if not image.is_file():
            raise RecordingRefused(f"{row['beat']}: review frame was not produced")
        row["image"] = image.name
    esc = lambda value: html.escape(str(value), quote=True)
    cards = []
    for row in data:
        label = "Source midpoint; production overlays are listed separately" if row["source"] else "Production card"
        details = {"Narration": row["spoken"], "Captions": row["captions"],
                   "Highlights": row["highlights"], "On screen": row["on_screen"],
                   "Source": [row["source"], row["source_start"], row["source_end"], row["source_url"]],
                   "Review tags": row["tags"]}
        cards.append(f'<article id="{esc(row["beat"])}"><h2>{esc(row["beat"])} '
                     f'{row["start"]:.2f}–{row["end"]:.2f}s</h2><p>{esc(label)}</p>'
                     f'<img src="{esc(row["image"])}" alt="{esc(row["beat"])}">'
                     + "".join(f'<p><b>{esc(k)}:</b> {esc(v)}</p>' for k, v in details.items())
                     + '<p>Human review: confirm person, event and topic against the source. '
                     'Motion previews: VM57 (not yet available).</p></article>')
    (review / "review.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    file = review / "index.html"
    file.write_text('<!doctype html><meta charset="utf-8"><title>Shot review</title>'
                    '<style>body{font:16px system-ui;margin:2rem;background:#eee}main{display:grid;'
                    'grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:1rem}'
                    'article{background:white;padding:1rem;overflow-wrap:anywhere}img{width:100%}</style>'
                    '<h1>Shot review</h1><p>Source stills do not prove identity or motion quality.</p><main>'
                    + "".join(cards) + '</main>', encoding="utf-8")
    return file
