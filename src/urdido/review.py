"""VM41: source stills paired with the words actually overlapping each beat.

PW708 tracks exact-time, editorially labelled contact sheets in polyweave.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from urdido import captions, media
from urdido.cards.html import Frame
from urdido.cards.render import render
from urdido.sources.model import RecordingRefused
from urdido.keywords import word_record


def words(placed: list[dict]) -> list[dict]:
    timed = []
    for take in placed:
        audio = Path(take["file"])
        timed.extend({"text": w["text"], "at": take["at"] + w["start"],
                      "end": take["at"] + w["end"]} for w in word_record(audio))
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


FEED_SIZES = ((320, 180), (168, 94))


def scene_moments(placed: list[dict], script: dict, language: str, total: float,
                  edge: float = 0.5) -> list[dict]:
    """UR12: where to look in a finished scene video, from its own takes.

    The cold open (before the first chapter's take), each chapter's start, middle and end
    (from its `chapter-<n>` take to the next chapter's, or to the closing), and the closing
    card in the last second. Each moment carries the chapter's title and the line spoken
    over it, so no second is picked by hand."""
    heard = {}
    for take in placed:
        heard.setdefault(Path(take["file"]).stem, take["at"])
    cues = captions.narration_cues(placed)

    def spoken(at: float) -> str:
        return " ".join(c.text for c in cues if c.start <= at < c.end)

    def moment(label: str, at: float, title: str = "") -> dict:
        at = round(min(max(0.0, at), max(0.0, total - 0.05)), 3)
        return {"label": label, "at": at, "title": title, "spoken": spoken(at)}

    starts = [(key, heard[f"chapter-{key}"]) for key in script["chapters"] if f"chapter-{key}" in heard]
    closing = heard.get("outro", total)
    found = []
    if starts and starts[0][1] > edge:
        found.append(moment("cold open", starts[0][1] / 2, captions.intro_title(script, language)))
    for i, (key, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else closing
        title = script["chapters"][key]["title"].get(language, "")
        found += [moment(f"chapter {key} start", start + edge, title),
                  moment(f"chapter {key} middle", (start + end) / 2, title),
                  moment(f"chapter {key} end", end - edge, title)]
    found.append(moment("closing card", total - edge))
    return found


def scene_sheet(video: Path, placed: list[dict], script: dict, language: str, out: Path,
                thumbnail: Path | None = None) -> Path:
    """UR12: a contact sheet of a finished scene video, beside it under `review/`."""
    total = media.seconds(str(video))
    data = scene_moments(placed, script, language, total)
    review = out / "review"
    review.mkdir(parents=True, exist_ok=True)
    for n, row in enumerate(data):
        image = review / f"scene-{n:02d}.png"
        image.unlink(missing_ok=True)
        media.ffmpeg(["-ss", f"{row['at']:.3f}", "-i", str(video), "-frames:v", "1",
                      "-vf", "scale=640:-2", str(image)])
        if not image.is_file():
            raise RecordingRefused(f"{row['label']}: review frame was not produced")
        row["image"] = image.name
    feeds = []
    if thumbnail is not None and thumbnail.is_file():
        for width, height in FEED_SIZES:
            image = review / f"thumbnail-{width}x{height}.png"
            image.unlink(missing_ok=True)
            media.ffmpeg(["-i", str(thumbnail), "-vf", f"scale={width}:{height}", str(image)])
            feeds.append(image.name)
    esc = lambda value: html.escape(str(value), quote=True)
    cards = [f'<article><h2>{esc(row["label"])} {row["at"]:.2f}s</h2>'
             f'<img src="{esc(row["image"])}" alt="{esc(row["label"])}">'
             f'<p><b>Chapter:</b> {esc(row["title"])}</p><p><b>Narration:</b> {esc(row["spoken"])}</p></article>'
             for row in data]
    if feeds:
        cards.append('<article><h2>Thumbnail at feed sizes</h2>'
                     + "".join(f'<img class="feed" src="{esc(name)}" alt="{esc(name)}">' for name in feeds)
                     + '</article>')
    (review / "scenes.json").write_text(json.dumps({"video": video.name, "moments": data, "thumbnail": feeds},
                                                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    file = review / "scenes.html"
    file.write_text('<!doctype html><meta charset="utf-8"><title>Scene review</title>'
                    '<style>body{font:16px system-ui;margin:2rem;background:#eee}main{display:grid;'
                    'grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:1rem}'
                    'article{background:white;padding:1rem;overflow-wrap:anywhere}img{width:100%}'
                    'img.feed{width:auto;margin-right:1rem}</style>'
                    f'<h1>Scene review: {esc(video.name)}</h1><main>' + "".join(cards) + '</main>',
                    encoding="utf-8")
    return file


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
                     f'Motion review: <code>build VIDEO.toml --language LANGUAGE --preview beat:{esc(row["beat"])}</code>.</p></article>')
    (review / "review.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    file = review / "index.html"
    file.write_text('<!doctype html><meta charset="utf-8"><title>Shot review</title>'
                    '<style>body{font:16px system-ui;margin:2rem;background:#eee}main{display:grid;'
                    'grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:1rem}'
                    'article{background:white;padding:1rem;overflow-wrap:anywhere}img{width:100%}</style>'
                    '<h1>Shot review</h1><p>Source stills do not prove identity or motion quality.</p><main>'
                    + "".join(cards) + '</main>', encoding="utf-8")
    return file
