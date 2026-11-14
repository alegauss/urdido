"""VM52 / PW711: bounded publishing text, with declared attribution retained intact.

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


def units(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def short_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.netloc.lower() in {"youtube.com", "www.youtube.com", "m.youtube.com"} and parts.path == "/watch":
        query = dict(parse_qsl(parts.query))
        video = query.pop("v", None)
        if video:
            return urlunsplit(("https", "youtu.be", "/" + video, urlencode(query), parts.fragment))
    return url


def compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def format_description(summary: str, chapters: list[str], credits: list[dict], *,
                       sources: list[dict] = (), notes: str = "", generated: str = "", limit: int = 5000) -> str:
    if not summary.strip():
        raise ValueError("description needs a declared opening summary")
    lines = [summary.strip(), "", "Capítulos", *chapters]
    if notes:
        lines += ["", notes.strip()]
    groups, references = OrderedDict(), OrderedDict()
    stocks = OrderedDict()
    own = OrderedDict()
    for source in sources:
        references.setdefault(short_url(source["url"]), compact(source["label"]))
    seen = set()
    for credit in credits:
        for field in ("title", "author", "url", "license"):
            if not credit.get(field):
                raise ValueError(f"attribution missing {field}: {credit.get('title', 'unnamed work')}")
        url = short_url(credit["url"])
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
            section = f"Trecho {credit['section']}"
            if section not in group:
                group.append(section)
        for field in ("copyright", "notice", "disclaimer", "attribution"):
            notice = credit.get(field)
            if notice and not any(compact(notice) in row for row in group):
                group.append(compact(notice))
        references.pop(url, None)
    if references:
        lines += ["", "Fontes e demonstrações"]
        lines += [f"{label}: {url}" for url, label in references.items()]
    if stocks:
        lines += ["", *[f"Apoio: {name} — {license}" for name, license in stocks.items()]]
    if own:
        lines += ["", "Capturas próprias: " + "; ".join(f"{name} {url}" for name, url in own.items())]
    for (license, url, changes), rows in groups.items():
        lines += ["", f"Imagens — {license}" + (f": {url}" if url else "")]
        if changes:
            lines.append(changes)
        lines += rows
    if generated:
        lines += ["", generated.strip()]
    text = "\n".join(lines).strip() + "\n"
    if units(text) > limit:
        raise ValueError(f"description is {units(text)} characters, limit {limit}; shorten the declared summary, notes or citation labels without removing required credits")
    if "<" in text or ">" in text:
        raise ValueError("description contains angle brackets that YouTube does not accept")
    return text


def illustrated(document: dict, chapters: list[str], options: dict | None = None) -> tuple[str, dict]:
    options = options or {}
    used = dict.fromkeys(b["asset"] for beats in document["scenes"].values() for b in beats if b.get("asset"))
    credits = []
    for key in used:
        asset = {**document["media"][key]}
        license = asset["license"]
        if license.startswith(("Registro próprio", "Gravação própria")):
            asset["kind"] = "own"
        elif license == "Pixabay Content License" and urlsplit(asset["url"]).netloc.lower() in {"pixabay.com", "www.pixabay.com"}:
            asset["kind"] = "pixabay"
            asset.setdefault("license_url", "https://pixabay.com/service/license-summary/")
        elif Path(asset["file"]).suffix.lower() in {".mp4", ".mov", ".webm"}:
            asset.setdefault("changes", "Trechos sem áudio original; reenquadrados.")
        license_url = asset.get("license_url", "")
        cc = re.fullmatch(r"https?://creativecommons\.org/licenses/(by(?:-sa)?)/(\d\.\d)/?", license_url)
        if cc:
            asset["license_label"] = f"CC {cc[1].upper()} {cc[2]}"
            if asset.get("plain_background") and Path(asset["file"]).suffix.lower() not in {".mp4", ".mov", ".webm"}:
                asset.setdefault("changes", "Fotografia integral, sem cortes.")
        elif license.startswith(("Public domain", "Domínio público")):
            asset["license_label"] = "Domínio público"
        elif license.startswith("Direitos reservados;"):
            asset["license_label"] = "Direitos reservados; citação editorial"
        elif license.startswith("Breve recorte de demonstração oficial"):
            asset["license_label"] = "Citação editorial; licença de reutilização não declarada"
        elif license.startswith("Documento judicial público;"):
            asset["license_label"] = "Documento judicial público"
        credits.append(asset)
    source_keys = {b["source"] for beats in document["scenes"].values() for b in beats}
    asset_urls = {a["url"] for a in credits}
    sources = [{"label": s.get("credit_label", s["label"].split(" · ")[0]), "url": s["url"]}
               for key, s in document["sources"].items() if key in source_keys or s["url"] in asset_urls]
    text = format_description(options.get("summary", document["description"]), chapters, credits,
                              sources=sources, notes=options.get("notes", document["credits"]),
                              generated=document.get("generated", "Narração e trilha geradas com ElevenLabs."))
    return text, {"assets": credits, "sources": document["sources"], "original_notes": document["credits"]}


def scion(plan: dict, sources: dict, publishing: dict, language: str = "pt-BR") -> tuple[str, dict]:
    used = dict.fromkeys(s["src"] for s in plan["shots"] if ":" not in s["src"])
    credits = [{"title": sources[key]["title"], "author": sources[key]["channel"],
                "url": sources[key]["url"], "license": publishing["license_label"],
                "license_url": publishing["license_url"], "changes": publishing["changes"]} for key in used]
    chapters = ["0:00 Introdução"]
    for segment in plan["segments"]:
        if segment["chapter"] is not None:
            at = int(segment["start"])
            chapters.append(f"{at // 60}:{at % 60:02} {plan['script']['chapters'][str(segment['chapter'])]['title'][language]}")
    text = format_description(publishing["summary"], chapters, credits, sources=publishing["sources"],
                              notes=publishing.get("notes", ""), generated=publishing["generated"])
    return text, {"assets": credits, "original_sources": {key: sources[key] for key in used}}


def write(out: Path, name: str, text: str, provenance: dict) -> Path:
    if units(text) > 5000 or "<" in text or ">" in text:
        raise ValueError("publishing description exceeds 5000 characters or contains invalid angle brackets")
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
