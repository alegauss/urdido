"""A video's YouTube thumbnail, declared in its video.toml and drawn by its channel's layout.

    urdido thumbnail <video.toml> --language pt-BR

The Japode videos each carried a `bin/thumbnail.py` that cut a frame, cropped it and called the
channel's `brand.thumbnail`; this is that step once (VM51). Every picture in a thumbnail is a
frame of the video's own sources, named by file, second and crop box, so a thumbnail never shows
what the video does not:

    [thumbnail]
    layout = "../brand/brand.py"            # a module with thumbnail(**fields) -> Path
    out = "video/thumbnail.{language}.jpg"

    [thumbnail.picture]                     # the person or scene on the left
    file = "footage/matt-2019-full.mp4"
    at = 15.0
    box = [0.25, 0.0, 0.72, 0.85]           # left, top, right, bottom, as fractions of the frame

    [thumbnail.proof]                       # optional: a crop of the real source
    file = "footage/origin.webm"
    at = 17.0
    box = [0.265, 0.01, 0.74, 0.35]

    [thumbnail.words.pt-BR]                 # the layout's text fields, per language
    top = "1 comentário"
    ...

Each picture is checked before it is cut (UR8): its file is media the storyboard
(`[source] declaration`) declares, and takes that media's licence, author and URL, or it
says why it is in the thumbnail alone and carries its own:

    [thumbnail.picture]
    file = "footage/wordpress-wmark-white.png"
    reason = "the official mark; the video shows it only inside the wp20 emblem"
    license = "WordPress trademark policy"   # or a .prov.json beside the file
    author = "WordPress Foundation"
    url = "https://wordpress.org/about/logos/"
    fit = "contain"                          # optional: cover or contain, with
    margin = 80                              # margin and background, passed to the
    background = "#0b1410"                   # layout as picture_fit, picture_margin...

Anything else is refused, and the drawn JPG gets a `.prov.json` naming each picture's
media key or reason, provenance and SHA-256.

    [thumbnail.title]                       # the video's published title, per language
    pt-BR = "O Git parou em 30 mil merges por dia"

The title and the thumbnail are checked as a pair before anything is drawn (UR1, `urdido
thumbnail --check` checks without drawing). A pair is refused when the title runs past 60
characters (the desktop search cut), carries no number, name or date, writes more than two words
in capitals or leans on an empty superlative, or when the thumbnail repeats a meaningful word of
the title: the thumbnail adds what the title leaves out. A title past 40 characters (the phone
feed) and a thumbnail of more than three words are advised, not refused. The stop words and the
empty superlatives come from a per-language default and `[thumbnail.check] stopwords` /
`superlatives` add to them; `[thumbnail.check] drawn` names the word fields the layout draws as
text, where some string fields are not (a colour, a path), and otherwise every string is read.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import tomllib
import unicodedata
from pathlib import Path

from urdido import media

TITLE_LIMIT = 60
FEED_LIMIT = 40
THUMBNAIL_WORDS = 3
CAPITALS = 2

STOPWORDS = {
    "pt": {"a", "o", "as", "os", "ao", "aos", "um", "uma", "uns", "umas", "de", "do", "da", "dos",
           "das", "e", "em", "no", "na", "nos", "nas", "por", "pelo", "pela", "para", "pra", "com",
           "sem", "que", "se", "seu", "sua", "nao", "mais", "como", "ou", "mas", "ja", "foi",
           "eu", "voce", "ele", "ela", "isso", "esse", "essa", "este", "esta", "sobre"},
    "en": {"a", "an", "the", "of", "and", "or", "in", "on", "at", "to", "for", "with", "by", "from",
           "is", "are", "was", "it", "its", "this", "that", "not", "no", "but", "as", "how", "you",
           "your", "we", "our", "they", "their", "be", "about"},
}
SUPERLATIVES = {
    "pt": {"incrivel", "inacreditavel", "chocante", "insano", "insana", "absurdo", "absurda",
           "definitivo", "definitiva", "melhor de todos", "o melhor", "a melhor", "imperdivel",
           "surreal", "bizarro", "epico", "epica"},
    "en": {"amazing", "incredible", "unbelievable", "insane", "shocking", "ultimate", "epic",
           "mind-blowing", "best ever", "the best", "crazy", "must-see"},
}


def units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def plain(text: str) -> str:
    """Casefolded, without accents: how two words are compared."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def words_of(text: str) -> list[str]:
    return re.findall(r"[^\W_]+(?:[-'][^\W_]+)*", text)


def vocabulary(defaults: dict, extra, language: str) -> set[str]:
    if isinstance(extra, dict):
        extra = extra.get(language, [])
    if not isinstance(extra, list) or not all(isinstance(word, str) for word in extra):
        raise ValueError("thumbnail: [thumbnail.check] stopwords and superlatives are lists of words")
    return {plain(word) for word in defaults.get(language.split("-")[0].lower(), set())} | {plain(w) for w in extra}


def thumbnail_text(words: dict) -> list[str]:
    """The texts a layout draws: every string field, and every string in a list field."""
    texts = []
    for value in words.values():
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, (list, tuple)):
            texts.extend(item for item in value if isinstance(item, str))
    return [text for text in texts if text.strip()]


def check_pair(title: str, words: dict, language: str, spec: dict | None = None) -> list[dict]:
    """UR1: a published title and its thumbnail, checked as a pair.

    Each finding is {"rule", "severity", "message"}; severity "refuse" stops the thumbnail and
    "advise" is printed beside it."""
    spec = spec or {}
    stop = vocabulary(STOPWORDS, spec.get("stopwords", []), language)
    empty = vocabulary(SUPERLATIVES, spec.get("superlatives", []), language)
    findings = []

    def found(rule, severity, message):
        findings.append({"rule": rule, "severity": severity, "message": message})

    title = title.strip()
    length = units(title)
    if length > TITLE_LIMIT:
        found("title.length", "refuse", f"the title is {length} characters; desktop search cuts it at "
              f"{TITLE_LIMIT}, so its point is lost: \"{title[:TITLE_LIMIT]}...\"")
    elif length > FEED_LIMIT:
        found("title.feed", "advise", f"the title is {length} characters; the phone feed shows about {FEED_LIMIT}")
    tokens = words_of(title)
    named = any(char.isdigit() for char in title) or any(token[:1].isupper() and not token.isupper() for token in tokens[1:])
    if not named:
        found("title.concrete", "refuse", "the title carries no number, name or date")
    shouting = [token for token in tokens if sum(c.isalpha() for c in token) >= 2 and token.isupper()]
    if len(shouting) > CAPITALS:
        found("title.capitals", "refuse", f"the title writes {len(shouting)} words in capitals "
              f"({', '.join(shouting)}); keep it to {CAPITALS}")
    flat = " " + " ".join(plain(token) for token in tokens) + " "
    hollow = sorted(phrase for phrase in empty if f" {phrase} " in flat)
    if hollow:
        found("title.superlative", "refuse", f"the title leans on an empty superlative: {', '.join(hollow)}")
    fields = spec.get("drawn")
    if fields is not None and (not isinstance(fields, list) or not all(isinstance(f, str) for f in fields)):
        raise ValueError("thumbnail: [thumbnail.check] drawn lists the word fields the layout draws as text")
    drawn = thumbnail_text({key: value for key, value in words.items() if fields is None or key in fields})
    meaningful = {plain(token) for token in tokens} - stop
    shared = sorted({plain(token) for text in drawn for token in words_of(text)} & meaningful)
    if shared:
        found("pair.repeats", "refuse", f"the thumbnail repeats the title's {', '.join(shared)}; "
              "it should add what the title leaves out")
    count = sum(len(words_of(text)) for text in drawn)
    if count > THUMBNAIL_WORDS:
        found("thumbnail.words", "advise", f"the thumbnail draws {count} words; {THUMBNAIL_WORDS} read at feed size")
    return findings


def enforce_pair(findings: list[dict], language: str) -> None:
    refused = [row for row in findings if row["severity"] == "refuse"]
    for row in findings:
        if row["severity"] == "advise":
            print(f"thumbnail ({language}): {row['message']}", file=sys.stderr)
    if refused:
        raise ValueError(f"thumbnail ({language}): the title and thumbnail are refused as a pair:\n"
                         + "\n".join(f"  {row['rule']}: {row['message']}" for row in refused))


def pair_of(decl: dict, language: str) -> tuple[str | None, dict]:
    words = dict(decl["words"][language])
    titles = decl.get("title", {})
    if not isinstance(titles, dict):
        raise ValueError("thumbnail: [thumbnail.title] names the published title per language")
    title = titles.get(language)
    if title is not None and (not isinstance(title, str) or not title.strip()):
        raise ValueError(f"thumbnail: [thumbnail.title] {language} must be the published title")
    return title, words


def check(decl: dict, language: str) -> list[dict]:
    title, words = pair_of(decl, language)
    if title is None:
        print(f"thumbnail ({language}): no [thumbnail.title] {language}, so the title and thumbnail "
              "go out unchecked as a pair", file=sys.stderr)
        return []
    findings = check_pair(title, words, language, decl.get("check", {}))
    enforce_pair(findings, language)
    return findings


def fit_title(page, box: tuple[float, float, float, float], *, max_size: int,
              min_size: int = 64, selector: str = "h1") -> dict:
    """VM54 / PW699: fit actual title-line extents to the layout's subject-free box."""
    left, top, right, bottom = box
    if any(not isinstance(size, int) or isinstance(size, bool) for size in (min_size, max_size)) \
            or not (0 <= left < right and 0 <= top < bottom and 1 <= min_size <= max_size):
        raise ValueError("thumbnail: invalid title box or font-size limits")
    title = page.locator(selector)
    page.evaluate("() => document.fonts.ready")
    for size in range(int(max_size), int(min_size) - 1, -1):
        title.evaluate("(el, size) => el.style.fontSize = size + 'px'", size)
        lines = title.evaluate("""el => [...el.childNodes].flatMap(node => {
            if (!node.textContent.trim()) return [];
            const range = document.createRange(); range.selectNodeContents(node);
            return [...range.getClientRects()].filter(r => r.width && r.height).map(r =>
                ({text: node.textContent, x:r.x, y:r.y, width:r.width, height:r.height}));
        })""")
        if all(line["x"] >= left and line["y"] >= top and line["x"] + line["width"] <= right
               and line["y"] + line["height"] <= bottom for line in lines):
            return {"box": list(box), "font_size": size, "max_size": max_size, "min_size": min_size, "lines": lines}
    raise ValueError(f"thumbnail: title does not fit its subject-free column {left:g}..{right:g} "
                     f"at {min_size}px; shorten the title or revise the declared text box")


def crop_filter(box: list[float]) -> str:
    """An ffmpeg crop for a box given as fractions of the frame (left, top, right, bottom)."""
    left, top, right, bottom = box
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError(f"thumbnail: a box is left, top, right, bottom between 0 and 1, got {box}")
    return f"crop=iw*{right - left:.4f}:ih*{bottom - top:.4f}:iw*{left:.4f}:ih*{top:.4f}"


def still(here: Path, spec: dict, out: Path) -> Path:
    """One frame of a declared source, cropped to its box."""
    source = here / spec["file"]
    if not source.exists():
        raise FileNotFoundError(f"thumbnail: {spec['file']} is not here")
    media.ffmpeg(["-ss", str(spec.get("at", 0)), "-i", str(source), "-frames:v", "1",
                  "-vf", crop_filter(spec.get("box", [0, 0, 1, 1])), str(out)])
    return out


PROVENANCE = ("license", "author", "url")
#: How a .prov.json names the fields a picture's provenance needs.
RECORDED = {"license": "licence", "author": "author", "url": "source_page"}
PLACEMENT = ("fit", "margin", "background")


def storyboard_media(here: Path, video: dict) -> dict:
    """The storyboard's media, library bindings resolved, keyed by their resolved file."""
    declared = video.get("source", {}).get("declaration")
    if not declared:
        return {}
    from urdido.library import resolve_asset

    document = json.loads((here / declared).read_text(encoding="utf-8-sig"))
    found = {}
    for key, asset in document.get("media", {}).items():
        resolved = resolve_asset(asset, here)
        found[(here / resolved["file"]).resolve()] = (key, resolved)
    return found


def recorded(file: Path) -> dict:
    """What a .prov.json beside the file says of its licence, author and source."""
    for path in (Path(str(file) + ".prov.json"), file.with_suffix(".prov.json")):
        if path.is_file():
            record = json.loads(path.read_text(encoding="utf-8-sig"))
            return {field: record.get(key) for field, key in RECORDED.items()}
    return {}


def provenance(here: Path, role: str, spec: dict, media_by_file: dict) -> dict:
    """UR8: a thumbnail picture is media the storyboard declares, or one declared
    thumbnail-only with a reason, and either way its licence, author and URL are known."""
    file = (here / spec["file"]).resolve()
    if file in media_by_file:
        key, asset = media_by_file[file]
        source = {"media": key, **{f: asset.get(f) for f in PROVENANCE}}
    elif isinstance(spec.get("reason"), str) and spec["reason"].strip():
        on_file = recorded(file)
        source = {"reason": spec["reason"].strip(),
                  **{f: spec.get(f) or on_file.get(f) for f in PROVENANCE}}
    else:
        raise ValueError(
            f"thumbnail: [thumbnail.{role}] {spec['file']} is not media the storyboard "
            "declares; name a storyboard media file, or declare it thumbnail-only with "
            "reason, license, author and url (or a .prov.json beside it)")
    missing = [f for f in PROVENANCE if not source.get(f)]
    if missing:
        raise ValueError(f"thumbnail: [thumbnail.{role}] {spec['file']} has no "
                         f"{', '.join(missing)}; a thumbnail shows nothing unattributed")
    if file.is_file():
        source["sha256"] = hashlib.sha256(file.read_bytes()).hexdigest()
    return {"role": role, "file": spec["file"], **source}


def placement(role: str, spec: dict) -> dict:
    """How a graphic is placed, passed to the layout only where declared."""
    fields = {}
    for key in PLACEMENT:
        if key in spec:
            fields[f"{role}_{key}"] = spec[key]
    if fields.get(f"{role}_fit", "cover") not in {"cover", "contain"}:
        raise ValueError(f"thumbnail: [thumbnail.{role}] fit is cover or contain")
    return fields


def layout(path: Path):
    spec = importlib.util.spec_from_file_location("channel_layout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.thumbnail


def make(declaration: Path, language: str) -> Path:
    here = declaration.parent
    video = tomllib.loads(declaration.read_text(encoding="utf-8"))
    decl = video["thumbnail"]
    check(decl, language)
    roles = [role for role in ("picture", "proof") if role in decl]
    media_by_file = storyboard_media(here, video)
    sources = [provenance(here, role, decl[role], media_by_file) for role in roles]
    words = dict(decl["words"][language])
    from urdido.build import roots_of

    output = video.get("output") or {}
    work = Path(roots_of(here, video)["video"]) / output.get("parts", "parts") / "thumbnail"
    work.mkdir(parents=True, exist_ok=True)
    fields = dict(words)
    for role in roles:
        fields[role] = still(here, decl[role], work / f"{role}.png")
        fields.update(placement(role, decl[role]))
    if "badges" in fields:
        fields["badges"] = tuple(fields["badges"])
    out = here / decl.get("out", "video/thumbnail.{language}.jpg").format(language=language)
    drawn = layout((here / decl["layout"]).resolve())(**fields, out=out)
    record = Path(str(drawn) + ".prov.json")
    record.write_text(json.dumps({"pictures": sources}, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return drawn


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="urdido thumbnail")
    p.add_argument("declaration")
    p.add_argument("--language", required=True)
    p.add_argument("--check", action="store_true", help="check the title and thumbnail as a pair; draw nothing")
    args = p.parse_args(argv)
    if args.check:
        declaration = Path(args.declaration).resolve()
        try:
            video = tomllib.loads(declaration.read_text(encoding="utf-8"))
            decl = video["thumbnail"]
            check(decl, args.language)
            media_by_file = storyboard_media(declaration.parent, video)
            for role in ("picture", "proof"):
                if role in decl:
                    provenance(declaration.parent, role, decl[role], media_by_file)
                    placement(role, decl[role])
        except (ValueError, OSError) as refused:
            print(refused, file=sys.stderr)
            return 1
        print(f"thumbnail ({args.language}): the pair and its pictures pass")
        return 0
    out = make(Path(args.declaration).resolve(), args.language)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
