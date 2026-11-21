"""VM52 / PW711: bounded publishing text, with declared attribution retained intact.

Its words come from the build language's table and its limits from the publishing
target (`urdido.publish.strings`, UR27), so an English video gets an English
description and a target other than YouTube changes the limit, not this code.

Platform limit: https://support.google.com/youtube/answer/57404
Attribution fields: https://creativecommons.org/licenses/by/3.0/deed.en
Pixabay grouping: https://pixabay.com/service/license-summary/
"""
from __future__ import annotations

import json
import os
import re
from collections import OrderedDict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from urdido.publish.strings import YOUTUBE, Target, licence_kind, strings


def units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def short_url(url: str, target: Target = YOUTUBE) -> str:
    parts = urlsplit(url)
    if parts.netloc.lower() in target.short_hosts and parts.path == "/watch":
        query = dict(parse_qsl(parts.query))
        video = query.pop("v", None)
        if video:
            return urlunsplit(("https", "youtu.be", "/" + video, urlencode(query), parts.fragment))
    return url


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def refuse_for(text: str, target: Target) -> None:
    if units(text) > target.limit:
        raise ValueError(f"description is {units(text)} characters, limit {target.limit}; shorten the declared summary, notes or citation labels without removing required credits")
    refused = [c for c in target.refused if c in text]
    if refused:
        raise ValueError(f"description contains {' '.join(refused)}, which {target.name} does not accept")


def format_description(summary: str, chapters: list[str], credits: list[dict], *,
                       sources: list[dict] = (), notes: str = "", generated: str = "",
                       words: dict | None = None, target: Target = YOUTUBE) -> str:
    words = words or strings("en")
    if not summary.strip():
        raise ValueError("description needs a declared opening summary")
    lines = [summary.strip(), "", words["chapters"], *chapters]
    if notes:
        lines += ["", notes.strip()]
    groups, references = OrderedDict(), OrderedDict()
    stocks = OrderedDict()
    own = OrderedDict()
    for source in sources:
        references.setdefault(short_url(source["url"], target), compact(source["label"]))
    seen = set()
    for credit in credits:
        for field in ("title", "author", "url", "license"):
            if not credit.get(field):
                raise ValueError(f"attribution missing {field}: {credit.get('title', 'unnamed work')}")
        url = short_url(credit["url"], target)
        protected = credit.get("attribution_required") or any(credit.get(k) for k in ("copyright", "notice", "disclaimer", "attribution"))
        cc_license = re.search(r"\bCC\b|Creative Commons", credit["license"], re.I)
        if credit.get("kind") == "own" and not protected and not cc_license:
            origin = urlsplit(url)
            own.setdefault(origin.netloc, urlunsplit((origin.scheme, origin.netloc, "/", "", "")))
            continue
        if credit.get("kind") == "pixabay" and not protected and credit["license"] == "Pixabay Content License" \
                and urlsplit(url).netloc.lower() in {"pixabay.com", "www.pixabay.com"}:
            stocks["Pixabay"] = "Pixabay Content License: https://pixabay.com/service/license-summary/"
            continue
        license_url = credit.get("license_url", "")
        if cc_license and not license_url:
            raise ValueError(f"{credit['title']}: declare the licence URL; no version is inferred")
        key = (credit.get("license_label", credit["license"]), license_url, credit.get("changes", ""))
        group = groups.setdefault(key, [])
        identity = (url, credit["author"], key)
        if identity not in seen:
            row = f"{credit['title']} — {credit['author']}: {url}"
            for field in ("copyright", "notice", "disclaimer", "attribution"):
                if credit.get(field):
                    row += "; " + compact(credit[field])
            group.append(row)
            seen.add(identity)
        if credit.get("section"):
            section = f"{words['excerpt']} {credit['section']}"
            if section not in group:
                group.append(section)
        for field in ("copyright", "notice", "disclaimer", "attribution"):
            notice = credit.get(field)
            if notice and not any(compact(notice) in row for row in group):
                group.append(compact(notice))
        references.pop(url, None)
    if references:
        lines += ["", words["sources"]]
        lines += [f"{label}: {url}" for url, label in references.items()]
    if stocks:
        lines += ["", *[f"{words['support']}: {name} — {license}" for name, license in stocks.items()]]
    if own:
        lines += ["", f"{words['own']}: " + "; ".join(f"{name} {url}" for name, url in own.items())]
    for (license, url, changes), rows in groups.items():
        lines += ["", f"{words['images']} — {license}" + (f": {url}" if url else "")]
        if changes:
            lines.append(changes)
        lines += rows
    if generated:
        lines += ["", generated.strip()]
    text = "\n".join(lines).strip() + "\n"
    refuse_for(text, target)
    return text


def illustrated(document: dict, chapters: list[str], options: dict | None = None,
                language: str = "en") -> tuple[str, dict]:
    options = options or {}
    words = strings(language, options.get("strings"))
    used = dict.fromkeys(b["asset"] for beats in document["scenes"].values() for b in beats if b.get("asset"))
    credits = []
    for key in used:
        asset = {**document["media"][key]}
        license = asset["license"]
        kind = licence_kind(license)
        if kind == "own":
            asset["kind"] = "own"
        elif license == "Pixabay Content License" and urlsplit(asset["url"]).netloc.lower() in {"pixabay.com", "www.pixabay.com"}:
            asset["kind"] = "pixabay"
            asset.setdefault("license_url", "https://pixabay.com/service/license-summary/")
        elif Path(asset["file"]).suffix.lower() in {".mp4", ".mov", ".webm"}:
            asset.setdefault("changes", words["video_changes"])
        license_url = asset.get("license_url", "")
        cc = re.fullmatch(r"https?://creativecommons\.org/licenses/(by(?:-sa)?)/(\d\.\d)/?", license_url)
        if cc:
            asset["license_label"] = f"CC {cc[1].upper()} {cc[2]}"
            if asset.get("plain_background") and Path(asset["file"]).suffix.lower() not in {".mp4", ".mov", ".webm"}:
                asset.setdefault("changes", words["photo_changes"])
        elif kind in ("public_domain", "reserved", "demo", "court"):
            asset["license_label"] = words[kind]
        credits.append(asset)
    source_keys = {b["source"] for beats in document["scenes"].values() for b in beats}
    asset_urls = {a["url"] for a in credits}
    sources = [{"label": s.get("credit_label", s["label"].split(" · ")[0]), "url": s["url"]}
               for key, s in document["sources"].items() if key in source_keys or s["url"] in asset_urls]
    claim_report = document.get("_claims_report")
    if claim_report:
        from urdido.claims import citations

        sources.extend(citations(claim_report))
    text = format_description(options.get("summary", document["description"]), chapters, credits,
                              sources=sources, notes=options.get("notes", document["credits"]),
                              generated=document.get("generated", words["generated"]), words=words)
    return text, {"assets": credits, "sources": document["sources"], "original_notes": document["credits"],
                  **({"claims": claim_report} if claim_report else {})}


def intro_line(script: dict, language: str, words: dict) -> str:
    """The chapter list's opening line: the script's `introTitle`, else the table's."""
    return "0:00 " + ((script.get("introTitle") or {}).get(language) or words["intro"])


def chapter_lines(script: dict, spoken: list[dict], language: str, lead: float = 0.4,
                  words: dict | None = None) -> list[str]:
    """UR9: `0:00 Title` lines, each chapter dated by when its own take is heard.

    A placement is matched to its take by file name (`chapter-<n>.mp3`, at any tempo),
    never by its position, so a take bought later or a missing result line moves nothing
    else. A chapter whose take is not in the cut is refused rather than guessed."""
    words = words or strings(language)
    heard = {}
    for placement in spoken:
        heard.setdefault(Path(placement["file"]).stem, placement["at"])
    lines = [intro_line(script, language, words)]
    for key, chapter in script["chapters"].items():
        take = f"chapter-{key}"
        if take not in heard:
            raise ValueError(f"description: {take} is not heard in the cut, so chapter {key} has no time")
        at = int(max(0, heard[take] - lead))
        lines.append(f"{at // 60}:{at % 60:02} {chapter['title'][language]}")
    return lines


def scenes(script: dict, plan: dict, language: str, options: dict) -> tuple[str, dict]:
    """UR9: a filmed-scenes video's description, its chapters measured off the cut."""
    if not options.get("summary"):
        raise ValueError("description: a scenes video declares [description] summary")
    words = strings(language, options.get("strings"))
    chapters = chapter_lines(script, plan["spoken"][language], language, words=words)
    sources = [{"label": s["label"], "url": s["url"]} for s in options.get("sources", [])]
    text = format_description(options["summary"], chapters, [], sources=sources,
                              notes=options.get("notes", ""), generated=options.get("generated", ""),
                              words=words)
    return text, {"chapters": chapters, "sources": sources}


def write(out: Path, name: str, text: str, provenance: dict, target: Target = YOUTUBE) -> Path:
    refuse_for(text, target)
    file = out / f"{name}.description.txt"
    pending = file.with_suffix(".txt.tmp")
    credits = out / f"{name}.credits.json"
    credits_pending = credits.with_suffix(".json.tmp")
    try:
        pending.write_text(text, encoding="utf-8", newline="")
        credits_pending.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(credits_pending, credits)
        os.replace(pending, file)
    finally:
        pending.unlink(missing_ok=True)
        credits_pending.unlink(missing_ok=True)
    return file
