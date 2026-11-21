"""Original editorial illustrations, declared per take and assembled as scene clips (VM35).

These are illustrations, never replicas of a historical screen. PW700 tracks the HTML-to-still
step not yet offered by the provider; cards.render is the framework's existing implementation.
"""
from __future__ import annotations

import base64
import html
import json
import math
from collections import Counter
from pathlib import Path

from urdido import cache, media
from urdido.cards.html import Frame, Theme
from urdido.cards.render import render as draw
from urdido.narration import Takes
from urdido.sources.model import RecordingRefused
from urdido.sources.scenes import Scene


def validate(document: dict, takes: Takes, language: str) -> list[tuple[str, list, object]]:
    """A missing beat, source or current voice must fail before rendering any frame."""
    declared = document["scenes"]
    if list(declared) != list(takes.lines):
        raise RecordingRefused("illustrated scenes must name every narration take, in script order")
    rows = []
    counts = Counter()
    for beats in declared.values():
        for beat in beats:
            brand_mark(beat, document)
            if beat.get("asset"):
                counts[document.get("media", {}).get(beat["asset"], {}).get("file", beat["asset"])] += 1
    for key, asset in document.get("media", {}).items():
        limit = document.get("asset_use_limits", {}).get(key, document.get("max_asset_uses"))
        if not document.get("repetition", {}).get("replace_file_counts") and limit is not None and counts[asset["file"]] > limit:
            raise RecordingRefused(f"{key}: footage reuse exceeds {limit} appearances")
    for name, beats in declared.items():
        voiced = takes.takes(name, [language], current_language=language)
        if len(voiced) != 1:
            raise RecordingRefused(f"{name}: missing or stale narration; buy the current take before building")
        if not beats:
            raise RecordingRefused(f"{name}: no illustrated beats")
        for beat in beats:
            if not beat.get("title"):
                raise RecordingRefused(f"{name}: a beat needs its title")
            if beat.get("source") not in document["sources"]:
                raise RecordingRefused(f"{name}: unknown source {beat.get('source')}")
            if beat.get("layout", "date") not in {"date", "path", "quote", "record", "blocks", "split", "footage", "picture"}:
                raise RecordingRefused(f"{name}: unknown illustration layout")
            if beat.get("weight", 1) <= 0:
                raise RecordingRefused(f"{name}: beat weight must be positive")
            if beat.get("layout") in {"footage", "picture"} and beat.get("asset") not in document.get("media", {}):
                raise RecordingRefused(f"{name}: unknown media asset")
        rows.append((name, beats, voiced[0]))
    return rows


def brand_mark(beat: dict, document: dict) -> str:
    asset = document.get("media", {}).get(beat.get("asset"), {})
    value = beat.get("brand_mark", asset.get("brand_mark", document.get("brand_mark", "top-left")))
    if not isinstance(value, str) or value not in {"top-left", "top-right", "bottom-left", "bottom-right", "none"}:
        raise RecordingRefused(f"unknown brand_mark {value!r}; use a corner or none")
    return value


def picture_crop(beat: dict) -> str:
    """A picture beat's `crop = [left, top, right, bottom]` (fractions of the image) as the ffmpeg
    filter that precedes its fitting to the frame, or nothing without one (VM76)."""
    box = beat.get("crop")
    if box is None:
        return ""
    if beat.get("layout") != "picture":
        raise RecordingRefused("crop applies to picture beats only")
    if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in box)):
        raise RecordingRefused(f"a picture crop is [left, top, right, bottom], got {box!r}")
    left, top, right, bottom = box
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise RecordingRefused(f"a picture crop is fractions with left < right and top < bottom, got {box!r}")
    return f"crop=iw*{right - left:.4f}:ih*{bottom - top:.4f}:iw*{left:.4f}:ih*{top:.4f},"


def paced(beats: list[dict], tempo: float) -> list[dict]:
    """A beat's fixed `seconds` were timed against the bought take, so a narration heard
    `tempo` times as fast shortens them by the same factor (VM72)."""
    if tempo == 1.0:
        return beats
    # A beat that plays its own sound keeps its clip's real seconds (VM78).
    return [{**b, "seconds": b["seconds"] / tempo} if "seconds" in b and not b.get("sound") else b for b in beats]


def sound_gain(beat: dict) -> float:
    """A sounding beat's `"sound": {"gain_db": -6}`, or 0 for `"sound": true` (VM78)."""
    sound = beat.get("sound")
    if sound is True:
        return 0.0
    if isinstance(sound, dict) and set(sound) <= {"gain_db"}:
        gain = sound.get("gain_db", 0.0)
        if isinstance(gain, (int, float)) and not isinstance(gain, bool) and -40 <= gain <= 12:
            return float(gain)
    raise RecordingRefused(f"a beat's sound is true or {{\"gain_db\": -40..12}}, got {sound!r}")


def scene_frames(document: dict, name: str, length: float) -> int:
    """A take's scene in frames: its 0.4 s lead, the take, its 0.5 s tail, and any pause the
    storyboard opens after it for a clip to play on its own (VM78)."""
    pause = (document.get("pauses") or {}).get(name, 0)
    if isinstance(pause, bool) or not isinstance(pause, (int, float)) or pause < 0:
        raise RecordingRefused(f"{name}: a pause is seconds of 0 or more, got {pause!r}")
    return math.ceil((0.4 + length + 0.5 + pause) * 30)


def beat_frames(beats: list[dict], total: int, max_static: float | None = None) -> list[int]:
    """Fixed short cards leave their remaining narration time to moving footage."""
    fixed = {i: round(b["seconds"] * 30) for i, b in enumerate(beats) if "seconds" in b}
    free = [i for i in range(len(beats)) if i not in fixed]
    remaining = total - sum(fixed.values())
    if remaining < 0 or (not free and remaining):
        raise RecordingRefused("beat durations do not fit their narration take")
    weights = [beats[i].get("weight", 1) for i in free]
    edges = [round(remaining * sum(weights[:i]) / sum(weights)) for i in range(len(free) + 1)] if free else [0]
    lengths = dict(fixed)
    lengths.update({n: edges[i + 1] - edges[i] for i, n in enumerate(free)})
    result = [lengths[i] for i in range(len(beats))]
    for beat, frames in zip(beats, result):
        if frames < 30:
            raise RecordingRefused("a beat must last at least one second")
        static = beat.get("layout", "date") != "footage" or beat.get("static", False)
        if static and max_static is not None and frames > math.floor(max_static * 30):
            raise RecordingRefused(f"static beat {beat['title']!r} exceeds {max_static:g} seconds")
    return result


def anchored_frames(beats: list[dict], total: int, audio: str,
                    max_static: float | None = None, *, aliases=None) -> list[int]:
    """VM42: word times fix boundaries; normal weights fill each bounded interval."""
    from urdido.keywords import anchor

    boundaries = {0: 0, len(beats): total}
    for i, beat in enumerate(beats):
        if "from_word" not in beat:
            continue
        if i == 0:
            raise RecordingRefused("the first beat starts at the take origin; put a beat before a word anchor")
        boundaries[i] = round((0.4 + anchor(Path(audio), beat["from_word"], **({"aliases": aliases} if aliases else {}))) * 30)
    result = []
    ordered = sorted(boundaries)
    for left, right in zip(ordered, ordered[1:]):
        duration = boundaries[right] - boundaries[left]
        if duration <= 0 or boundaries[right] > total:
            raise RecordingRefused("word anchors must increase within the narration take")
        result += beat_frames(beats[left:right], duration, max_static)
    return result


def page(beat: dict, document: dict, theme: Theme, frame: Frame, logo: str, number: int, *, field_prefix="scene") -> str:
    esc = lambda s: html.escape(str(s), quote=True)
    source = document["sources"][beat["source"]]
    layout = beat.get("layout", "date")
    full = layout in {"footage", "picture"} and beat.get("presentation", "full") == "full"
    items = beat.get("items", [])
    tiles = "".join(f'<div class="tile"><span>{i + 1:02}</span><strong>{esc(item)}</strong></div>'
                    for i, item in enumerate(items))
    graphic = f'<div class="tiles {layout}">{tiles}</div>'
    if layout == "record":
        graphic = '<div class="vinyl"><div class="label">JAZZ<br>+<br>CODE</div></div>'
    if layout == "date":
        big = beat.get("big", "")
        size = ' style="font-size:110px;letter-spacing:-4px"' if len(big) > 6 else ""
        graphic = f'<div class="date"{size}>{esc(big)}</div>'
    if layout == "quote":
        graphic = f'<blockquote>“{esc(beat.get("quote", ""))}”</blockquote><p class="attribution">{esc(beat.get("by", ""))}</p>'
    if layout in {"footage", "picture"}:
        graphic = ""  # Composited from the real source file, without changing its contents.
    c = theme.colors
    mark = brand_mark(beat, document)
    mark_css = ""
    if mark not in {"top-left", "none"}:
        vertical, horizontal = mark.split("-")
        mark_css = ("body header,body.full header{width:max-content;"
                    f"top:{'50px' if vertical == 'top' else 'auto'};"
                    f"bottom:{'50px' if vertical == 'bottom' else 'auto'};"
                    f"left:{'70px' if horizontal == 'left' else 'auto'};"
                    f"right:{'70px' if horizontal == 'right' else 'auto'};" + "}")
    header = "" if mark == "none" else (
        f'<header><img src="{logo}"><b>{esc(document["brand"])}</b><small>{esc(document["series"])}</small></header>')
    fields = {"h1": f"{field_prefix}.{'caption' if 'caption' in beat else 'title'}", "p.text": f"{field_prefix}.text",
              ".kicker": f"{field_prefix}.kicker", ".date": f"{field_prefix}.big", "blockquote": f"{field_prefix}.quote",
              ".attribution": f"{field_prefix}.by", ".tile strong": f"{field_prefix}.items",
              "header b": "brand", "header small": "series", "footer span": f"sources.{beat['source']}"}
    full_css = '''
.full.layer-text{background:transparent}.full .glow{display:none}
.full header{top:50px;left:70px;text-shadow:0 2px 8px #000}
.full header small{display:none}.full header img{filter:drop-shadow(0 2px 8px #000)}
.full main{display:block;left:80px;right:80px;top:auto;bottom:110px;min-height:0}
.full .graphic,.full .rule,.full .kicker{display:none}
.full h1{font-size:44px;line-height:1.15;margin:0 0 14px;letter-spacing:-1px;max-width:1400px;text-shadow:0 2px 12px #000}
.full .text{font-size:26px;line-height:1.4;margin:0;max-width:1400px;text-shadow:0 2px 12px #000}
.full footer{display:none}.full:before{content:'';position:absolute;inset:0;background:linear-gradient(transparent 55%,#000b)}
.full.hero h1{font-size:78px;max-width:1500px}.full.hero main{bottom:160px}
''' if full else ""
    if full and beat.get("mark_only"):
        full_css += ".full:before{display:none}"  # the caption's shade leaves with the caption
    return f'''<!doctype html><meta charset="utf-8"><style>
@font-face{{font-family:Display;src:url({theme.fonts['display-800']});font-weight:800}}
@font-face{{font-family:Text;src:url({theme.fonts['text']})}}
*{{box-sizing:border-box}}body{{margin:0;width:{frame.width}px;height:{frame.height}px;overflow:hidden;
background:{theme.data['background']};color:{c['text']};font-family:Text}}
.glow{{position:absolute;inset:0;background:radial-gradient(ellipse at 78% 40%,#11904a30,transparent 60%)}}
header{{position:absolute;top:68px;left:100px;right:100px;display:flex;align-items:center;gap:20px}}
header img{{width:50px;height:50px}}header b{{font:800 29px Display;letter-spacing:5px}}
header small{{margin-left:auto;color:{c['muted']};font:23px Text;letter-spacing:2px}}
main{{position:absolute;left:110px;right:110px;top:220px;bottom:150px;display:grid;grid-template-columns:1fr 1.1fr;gap:90px;align-items:center}}
.kicker{{color:{c['accent']};font:800 23px Display;letter-spacing:4px;text-transform:uppercase}}
h1{{font:800 72px/1.12 Display;margin:28px 0;letter-spacing:-2px;overflow-wrap:break-word}}
.text{{font:30px/1.55 Text;color:{c['muted']};max-width:690px}}
.rule{{width:100px;height:7px;background:{c['accent']};margin-bottom:24px}}
.graphic{{position:relative;text-align:center;min-width:0}}
.date{{font:800 190px/.95 Display;color:{c['accent']};letter-spacing:-10px;white-space:nowrap;overflow-wrap:normal}}
.tiles{{display:flex;flex-direction:column;gap:24px;text-align:left}}
.tile{{border:1px solid #2bcb6b55;background:#183326aa;border-radius:20px;padding:28px 32px;display:flex;align-items:center;gap:26px}}
.tile span{{font:800 25px Display;color:{c['accent']}}}.tile strong{{font:800 32px Display}}
.split{{gap:40px}}.split .tile{{min-height:180px;flex-direction:column;align-items:flex-start}}
.blocks{{transform:rotate(-3deg)}}.blocks .tile:nth-child(2){{margin-left:70px;background:#23754b}}
blockquote{{font:800 44px/1.45 Display;text-align:left;border-left:8px solid {c['accent']};padding:32px 0 32px 36px;margin:0}}
.attribution{{font:24px/1.4 Text;text-align:left;margin-left:44px;color:{c['muted']}}}
.vinyl{{width:520px;height:520px;margin:auto;border-radius:50%;border:4px solid #52715f;
background:repeating-radial-gradient(circle,#15251c 0 4px,#294534 5px,#0b1410 7px 11px);display:grid;place-items:center;box-shadow:0 30px 80px #0008}}
.label{{width:210px;height:210px;border-radius:50%;background:{c['accent']};color:#0b1410;display:grid;place-content:center;font:800 31px/1.3 Display;transform:rotate(-12deg)}}
footer{{position:absolute;left:110px;right:110px;bottom:70px;border-top:1px solid #2bcb6b44;padding-top:22px;display:flex;gap:30px;align-items:center}}
footer span{{font:21px Text;color:#9bbba7;max-width:1460px}}footer b{{margin-left:auto;color:{c['accent']};font:800 23px Display}}
{full_css}
{mark_css}
</style><body data-text-fields="{esc(json.dumps(fields))}" class="{'full' if full else ''} {'hero' if beat.get('hero') else ''}"><div class="glow"></div>{header}
<main{' data-text-box="fixed"' if not full else ''}><section><div class="rule"></div><div class="kicker">{esc(beat['kicker'])}</div><h1>{esc(beat.get('caption', beat['title']))}</h1><p class="text">{esc(beat.get('text', ''))}</p></section><section class="graphic">{graphic}</section></main>
<footer><span>Fonte: {esc(source['label'])}<br>{esc(source['url'])}</span><b>{number:02}</b></footer>'''


def scenes(document: dict, takes: Takes, theme: Theme, language: str, folder: str,
           parts: str, *, render: bool, encoder: str, beat_keys: set[str] | None = None,
           cards_only: bool = False, frame: Frame | None = None) -> list[Scene]:
    from urdido.keywords import aliases as declared_aliases
    from urdido.library import check_range, check_rejected, resolve

    document = resolve(document, folder)
    rows = validate(document, takes, language)
    # The video's frame, 1920x1080 unless the declaration sets another, e.g. a 9:16 Short (VM74).
    frame = frame or Frame(1920, 1080)
    W, H = frame.width, frame.height
    out = Path(parts) / "illustrated"
    out.mkdir(parents=True, exist_ok=True)
    logo_path = (Path(folder) / document["logo"]).resolve()
    mime = "image/svg+xml" if logo_path.suffix == ".svg" else "image/png"
    logo = f"data:{mime};base64," + base64.b64encode(logo_path.read_bytes()).decode()
    pages, jobs, result, audit = {}, [], [], []
    clock = 0
    n = 0
    for name, beats, take in rows:
        total_frames = scene_frames(document, name, take.length)
        lengths = anchored_frames(paced(beats, takes.tempo), total_frames, take.file, document.get("max_static_seconds"),
                                  aliases=declared_aliases(takes.script, language))
        for i, (beat, frames) in enumerate(zip(beats, lengths)):
            if frames < 30:
                raise RecordingRefused(f"{name}: too many beats for the spoken take")
            n += 1
            key = f"{name}-{i}"
            content = page(beat, document, theme, frame, logo, n, field_prefix=f"scenes.{name}.{i}")
            pages[key] = content
            (out / f"{key}.html").write_text(content, encoding="utf-8")
            if beat.get("overlay_seconds"):
                # The caption leaves after overlay_seconds; the brand mark stays the whole beat.
                mark = page({**beat, "caption": "", "title": "", "text": "", "mark_only": True},
                            document, theme, frame, logo, n, field_prefix=f"scenes.{name}.{i}")
                pages[f"{key}-mark"] = mark
                content += mark
            picture_crop(beat)  # refused before any rendering (VM76)
            asset = document.get("media", {}).get(beat.get("asset"))
            if asset:
                file = (Path(folder) / asset["file"]).resolve()
                if not file.exists():
                    raise RecordingRefused(f"{name}: missing media asset {asset['file']}")
                if not asset.get("license") or not asset.get("url") or not asset.get("author"):
                    raise RecordingRefused(f"{name}: media asset needs its licence, author and source URL")
                check_range(beat, asset, frames)
                check_rejected(beat, asset, frames)
                if beat["layout"] == "footage" and beat.get("at", 0) + frames / 30 > media.seconds(str(file)) + 0.02:
                    raise RecordingRefused(f"{name}: the footage is shorter than the requested beat")
                asset = {**asset, "path": str(file), "sha256": cache.file_hash(file)}
            jobs.append((key, content, frames, beat, asset))
            if beat.get("sound") and beat.get("layout") != "footage":
                raise RecordingRefused(f"{name}: only a footage beat can play its own sound")
            audit.append({"take": name, "beat": key, "at": clock / 30, "seconds": frames / 30,
                          "static": beat.get("layout", "date") != "footage" or beat.get("static", False),
                          "asset": beat.get("asset"),
                          # Where the mix finds the clip's sound (VM78).
                          **({"sound": {"file": asset["path"], "source_at": beat.get("at", 0),
                                        "gain_db": sound_gain(beat)}}
                             if beat.get("sound") and asset else {})})
            clock += frames
        result.append(Scene(name, str(out / f"{name}.mp4"), total_frames / 30, "illustrated"))
    (out / "edit.json").write_text(json.dumps({"beats": audit, "total": clock / 30}, indent=2) + "\n", encoding="utf-8")
    if not render:
        return result
    # Existing cards renderer waits for local fonts; no website is restaged or recorded here.
    if beat_keys is not None:
        jobs = [job for job in jobs if job[0] in beat_keys]
        pages = {key: content for key, content in pages.items()
                 if key in beat_keys or (key.endswith("-mark") and key[:-5] in beat_keys)}
    if pages:
        draw(pages, frame, str(out))
    if cards_only:
        return result
    def encode(job):
        key, content, frames, beat, asset = job
        file = out / f"{key}.mp4"
        inputs = ["-i", str(out / f"{key}.png")]
        if asset:
            full = beat.get("presentation", "full") == "full"
            if full:
                inputs = ["-i", str(out / f"{key}-text.png")]
            inputs = ["-loop", "1", "-framerate", "30", *inputs]
            if beat["layout"] == "picture":
                inputs += ["-loop", "1", "-framerate", "30", "-i", asset["path"]]
            else:
                inputs += ["-ss", str(beat.get("at", 0)), "-i", asset["path"]]
            if full:
                if beat["layout"] == "picture":
                    cut = picture_crop(beat)
                    if asset.get("plain_background"):
                        graph = f"[1:v]setpts=PTS-STARTPTS,{cut}scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x0b1410,setsar=1[asset];"
                    else:
                        graph = f"[1:v]setpts=PTS-STARTPTS,{cut}split[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.2[back];[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[front];[back][front]overlay=(W-w)/2:(H-h)/2,setsar=1[asset];"
                elif asset.get("fit") == "blur":
                    # The whole clip over a blurred, darkened fill of itself: a 16:9 or low-resolution
                    # clip on a 9:16 frame without bars or a blown-up crop (VM74).
                    graph = (f"[1:v]setpts=PTS-STARTPTS,fps=30,split[bg][fg];[bg]scale={W}:{H}:force_original_aspect_ratio=increase,"
                             f"crop={W}:{H},boxblur=30:2,eq=brightness=-0.2[back];[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[front];"
                             "[back][front]overlay=(W-w)/2:(H-h)/2,setsar=1[asset];")
                else:
                    sizing = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x0b1410") if asset.get("fit") == "contain" else f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
                    graph = f"[1:v]setpts=PTS-STARTPTS,fps=30,{sizing},setsar=1[asset];"
                if beat.get("overlay_seconds"):
                    # The mark layer (input 2) stays; only the caption layer leaves on time.
                    inputs += ["-loop", "1", "-framerate", "30", "-i", str(out / f"{key}-mark-text.png")]
                    graph += ("[asset][2:v]overlay=0:0:shortest=1[marked];"
                              f"[marked][0:v]overlay=0:0:shortest=1:enable='lt(t,{beat['overlay_seconds']})',"
                              "format=yuv420p[v]")
                else:
                    graph += "[asset][0:v]overlay=0:0:shortest=1,format=yuv420p[v]"
            else:
                fit = "decrease" if beat["layout"] == "picture" else "increase"
                graph = f"[1:v]setpts=PTS-STARTPTS,scale=800:590:force_original_aspect_ratio={fit},pad=800:590:(ow-iw)/2:(oh-ih)/2:color=0x0b1410" if fit == "decrease" else "[1:v]setpts=PTS-STARTPTS,scale=800:590:force_original_aspect_ratio=increase,crop=800:590"
                graph += ",setsar=1[asset];[0:v][asset]overlay=1000:245:shortest=1,format=yuv420p[v]"
            filters = ["-filter_complex", graph, "-map", "[v]"]
        else:
            # Native-resolution zoompan quantises the crop to pixels and makes type jitter.
            # Editorial cards stay locked; only the source footage supplies camera movement.
            inputs = ["-loop", "1", "-framerate", "30", *inputs]
            filters = ["-vf", "setsar=1"]
        args = [*inputs, *filters, "-frames:v", str(frames), *media.video_codec(encoder, 20),
                "-pix_fmt", "yuv420p", "-r", "30", "-an", str(file)]
        sources = [inputs[i + 1] for i, arg in enumerate(inputs) if arg == "-i"]
        cache.run("illustrated clip", [file], args, lambda: media.ffmpeg(args),
                  inputs=[__file__, media.__file__, *sources], tools=["ffmpeg"])
    from urdido import progress

    progress.plan("source clips", len(jobs))
    media.pool([lambda job=job: encode(job) for job in jobs])
    if beat_keys is not None:
        return result  # VM57: previews reuse the exact production beat clips, without full-take joins.
    progress.plan("join", len(result))
    for scene, (_, beats, _) in zip(result, rows):
        listing = out / f"{scene.name}.concat.txt"
        listing.write_text("".join(f"file '{scene.name}-{i}.mp4'\n" for i in range(len(beats))), encoding="utf-8")
        args = ["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", scene.file]
        cache.run("illustrated take join", [scene.file], args, lambda: media.ffmpeg(args),
                  inputs=[__file__, *[out / f"{scene.name}-{i}.mp4" for i in range(len(beats))]], tools=["ffmpeg"])
    return result


def description(document: dict, script: dict, plan: dict, language: str, out: Path, name: str, options: dict | None = None):
    """Chapter times come from the composed voice placements, never estimated reading times."""
    from urdido.publish.description import illustrated, intro_line, write
    from urdido.publish.strings import strings

    lines = [intro_line(script, language, strings(language, (options or {}).get("strings")))]
    placed = plan["spoken"][language]
    # takes.lines uses a stable order; one spoken placement per take was validated above.
    for i, (key, chapter) in enumerate(script["chapters"].items()):
        at = int(max(0, placed[1 + i * 2]["at"] - 0.4))
        lines.append(f"{at // 60}:{at % 60:02} {chapter['title'][language]}")
    text, provenance = illustrated(document, lines, options, language)
    write(out, f"{name}.{language}", text, provenance)
