"""VM58 / PW714: reviewed candidates, explicit rights and hash-bound source ranges."""
from __future__ import annotations

import argparse
import copy
import html
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from fractions import Fraction
from pathlib import Path

from videomaker.cache import file_hash
from videomaker.sources.model import RecordingRefused


def read(file):
    data = json.loads(Path(file).read_text("utf-8-sig"))
    if data.get("version") != 1 or not isinstance(data.get("candidates"), dict):
        raise ValueError("library needs version=1 and a candidates object")
    return data


def probe(file):
    result = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(file)],
                                       capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    stream = next((s for s in result.get("streams", []) if s.get("codec_type") == "video"), None)
    if not stream or not all(stream.get(k, 0) > 0 for k in ("width", "height")):
        raise ValueError("candidate has no readable picture or video stream")
    duration = result.get("format", {}).get("duration")
    duration = float(duration) if duration is not None else None
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError("candidate duration must be finite and positive")
    try:
        rate = float(Fraction(stream.get("avg_frame_rate", "0/1")))
    except (ValueError, ZeroDivisionError):
        rate = None
    return {"width": stream["width"], "height": stream["height"], "fps": rate,
            "duration": duration, "codec": stream.get("codec_name")}


def imported(file, metadata, catalogue):
    file = Path(file).resolve()
    # Imported metadata remains a claim, never an editorial or rights approval.
    source = {key: metadata.get(key) for key in ("url", "title", "author", "license", "license_url")}
    result = {**source, "file": os.path.relpath(file, Path(catalogue).resolve().parent).replace("\\", "/"),
              "sha256": file_hash(file), "measurements": probe(file),
              "retrieved_at": metadata.get("retrieved_at"), "imported_at": datetime.now(timezone.utc).isoformat(),
              "rights": {"status": "unknown"}, "ranges": [], "imported_metadata": metadata}
    result["kind"] = "video" if result["measurements"]["duration"] is not None else "picture"
    result.update({key: metadata[key] for key in ("source_id", "source_offset") if key in metadata})
    for path in (Path(str(file) + ".prov.json"), file.with_suffix(".prov.json")):
        if path.is_file():
            record = json.loads(path.read_text("utf-8-sig"))
            if record.get("artefact", {}).get("sha256") not in (None, result["sha256"]):
                raise RecordingRefused("imported provenance belongs to different media bytes")
            result["provenance"] = {"file": str(path), "sha256": file_hash(path),
                                    "record": record}
            if result["retrieved_at"] is None and record.get("kind") == "fetch":
                result["retrieved_at"] = record.get("produced_at")
            for target, key in (("url", "source_page"), ("author", "author"), ("license", "licence"), ("title", "title")):
                if not result.get(target):
                    result[target] = record.get(key)
            break
    return result


def decision(record):
    if not all(isinstance(record.get(k), str) and record[k].strip() for k in ("reviewer", "date", "reason")):
        raise ValueError("a review needs an explicit reviewer, ISO date and reason")
    date.fromisoformat(record["date"])


def validate(candidate):
    if candidate.get("kind") not in {"video", "picture"}:
        raise ValueError("candidate kind must be video or picture")
    rights = candidate.get("rights", {})
    if rights.get("status") not in {"unknown", "uncertain", "approved", "restricted"}:
        raise ValueError("rights status is unknown, uncertain, approved or restricted")
    if rights["status"] == "approved":
        decision(rights)
        if not all(candidate.get(k) for k in ("url", "title", "author", "license")):
            raise ValueError("approved rights need source URL, title, author and declared license")
    ids = set()
    for item in candidate.get("ranges", []):
        if not isinstance(item.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]+", item["id"]) or item["id"] in ids:
            raise ValueError("range IDs must be unique simple names")
        ids.add(item["id"])
        decision(item)
        if item.get("status") not in {"accepted", "rejected"}:
            raise ValueError("range status is accepted or rejected")
        for key in ("people", "events", "categories"):
            if not isinstance(item.get(key, []), list) or not all(isinstance(v, str) for v in item.get(key, [])):
                raise ValueError(f"confirmed {key} must be a list of names")
        if candidate.get("kind") == "picture":
            if item.get("whole") is not True:
                raise ValueError("a picture review applies to the whole image")
            continue
        start, end = item.get("start"), item.get("end")
        if not all(isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(t) for t in (start, end)) \
                or not 0 <= start < end:
            raise ValueError("review ranges need finite increasing source times")
        duration = candidate["measurements"]["duration"]
        if duration is not None and end > duration + .02:
            raise ValueError("review range extends beyond the source duration")
    accepted = [r for r in candidate.get("ranges", []) if r["status"] == "accepted"]
    rejected = [r for r in candidate.get("ranges", []) if r["status"] == "rejected"]
    if accepted and rejected and (candidate.get("kind") == "picture" or
            any(a["start"] < r["end"] and a["end"] > r["start"] for a in accepted for r in rejected)):
        raise ValueError("accepted and rejected ranges overlap; split the decision explicitly")


def update(file, expected, action):
    file = Path(file).resolve()
    file.parent.mkdir(parents=True, exist_ok=True)
    lock = file.with_name(file.name + ".edit.lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(descriptor)
    pending = None
    try:
        actual = file_hash(file) if file.exists() else "new"
        if actual != expected:
            raise ValueError("stale library: inspect its current SHA-256 before editing")
        data = read(file) if file.exists() else {"version": 1, "candidates": {}, "history": []}
        action(data)
        for candidate in data["candidates"].values():
            validate(candidate)
        data.setdefault("history", []).append({"previous_sha256": actual, "at": datetime.now(timezone.utc).isoformat()})
        fd, path = tempfile.mkstemp(prefix=file.name + ".", suffix=".tmp", dir=file.parent)
        pending = Path(path)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if (file_hash(file) if file.exists() else "new") != actual:
            raise ValueError("library changed during edit; inspect and retry")
        os.replace(pending, file)
    finally:
        if pending:
            pending.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
    return file_hash(file)


def review(data, key, record):
    candidate = data["candidates"][key]
    decision(record)
    prior = copy.deepcopy(candidate)
    common = {k: record[k] for k in ("reviewer", "date", "reason")}
    fields = {k: v for k, v in record.get("metadata", {}).items()
              if k in {"url", "title", "author", "license", "license_url", "source_id", "source_offset"}}
    if any(candidate.get(k) != value for k, value in fields.items()) and "rights" not in record:
        candidate["rights"] = {"status": "unknown"}
    candidate.update(fields)
    if "rights" in record:
        candidate["rights"] = {**common, **record["rights"]}
    if "ranges" in record:
        candidate["ranges"] = [{**common, **r} for r in record["ranges"]]
    candidate.setdefault("reviews", []).append({"record": record, "previous_rights": prior["rights"], "previous_ranges": prior["ranges"]})
    validate(candidate)


def resolve_asset(asset, folder, load=None):
    if "library" not in asset:
        return asset
    allowed = {"library", "candidate", "range", "fit", "plain_background", "brand_mark"}
    if set(asset) - allowed:
        raise RecordingRefused("library media inherits provenance and confirmed identities; only visual fit/brand overrides are allowed")
    catalogue = (Path(folder) / asset["library"]).resolve()
    data = load(str(catalogue)) if load else read(catalogue)
    candidate = data["candidates"][asset["candidate"]]
    validate(candidate)
    if candidate["rights"]["status"] != "approved":
        raise RecordingRefused(f"{asset['candidate']}: library rights are {candidate['rights']['status']}; explicit review is required")
    selected = next((r for r in candidate["ranges"] if r["id"] == asset["range"]), None)
    if selected is None or selected["status"] != "accepted":
        raise RecordingRefused(f"{asset['candidate']}: select an accepted library range")
    file = (catalogue.parent / candidate["file"]).resolve()
    if file_hash(file) != candidate["sha256"]:
        raise RecordingRefused(f"{asset['candidate']}: library media changed; import and review the current bytes")
    inherited = {k: candidate[k] for k in ("url", "title", "author", "license", "license_url", "retrieved_at", "provenance", "source_id", "source_offset")
                 if candidate.get(k) is not None}
    return {**inherited, "file": str(file), "people": selected.get("people", []), "events": selected.get("events", []),
            "categories": selected.get("categories", []),
            **{k: asset[k] for k in ("fit", "plain_background", "brand_mark") if k in asset},
            "library_binding": {"catalogue": str(catalogue), "candidate": asset["candidate"], "range": selected,
                                "sha256": candidate["sha256"], "rights": candidate["rights"], "kind": candidate["kind"]}}


def resolve(document, folder, load=None):
    result = copy.deepcopy(document)
    result["media"] = {key: resolve_asset(asset, folder, load) for key, asset in result.get("media", {}).items()}
    for beats in result.get("scenes", {}).values():
        for beat in beats:
            binding = result["media"].get(beat.get("asset"), {}).get("library_binding")
            if binding:
                beat.setdefault("at", binding["range"].get("start", 0))
    return result


def source_start(beat, asset):
    return beat.get("at", asset.get("library_binding", {}).get("range", {}).get("start", 0))


def check_range(beat, asset, frames):
    binding = asset.get("library_binding")
    if not binding:
        return
    selected = binding["range"]
    if beat.get("layout") != ("footage" if binding["kind"] == "video" else "picture"):
        raise RecordingRefused("a library video needs footage layout; a library picture needs picture layout")
    at = source_start(beat, asset)
    if binding["kind"] == "video" and (at < selected["start"] - .0001 or at + frames / 30 > selected["end"] + .0001):
        raise RecordingRefused(f"library range {selected['id']}: beat exceeds its accepted source interval")
    if file_hash(asset["file"]) != binding["sha256"]:
        raise RecordingRefused("library media changed after resolution; import and review current bytes")


def delegate(operation, root, **parameters):
    args = [sys.executable, "-m", "polyweave", operation, "--root", str(Path(root).resolve()), "--json"]
    for name, value in parameters.items():
        if isinstance(value, bool):
            if value:
                args += ["--" + name]
        elif value is not None:
            args += ["--" + name, str(value)]
    run = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    if run.returncode:
        raise RuntimeError(f"{operation} refused: {run.stderr or run.stdout}")
    result = json.loads(run.stdout)
    if result.get("ok") is False or result.get("error"):
        raise RuntimeError(f"{operation} refused: {json.dumps(result, ensure_ascii=False)}")
    return result


def add(data, key, candidate):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
        raise ValueError("candidate ID needs letters, digits, hyphens or underscores")
    if key in data["candidates"]:
        raise ValueError("candidate already exists; a new source revision needs a new ID")
    data["candidates"][key] = candidate


def preview(file, key, root, out, rate):
    catalogue = Path(file).resolve()
    candidate = read(catalogue)["candidates"][key]
    source = (catalogue.parent / candidate["file"]).resolve()
    if file_hash(source) != candidate["sha256"]:
        raise RecordingRefused("candidate changed; import current bytes before previewing")
    if candidate["kind"] == "picture":
        return {"source_sha256": candidate["sha256"], "images": [{"file": str(source), "sha256": candidate["sha256"]}]}
    name = f"library-{key}-{candidate['sha256'][:12]}"
    delegate("reference.register", root, video=str(source), name=name)
    record = delegate("reference.frames", root, video=name, rate=rate, out=out)
    folder = (Path(root) / out).resolve()
    manifest = json.loads((folder / "frames.json").read_text("utf-8"))
    images = [{"file": str(folder / path), "sha256": file_hash(folder / path)} for path in manifest["sheets"]]
    if not images:
        raise RuntimeError("reference.frames produced no contact sheets")
    return {"source_sha256": candidate["sha256"], "images": images, "record": record, "manifest": manifest}


def sheet(file, output):
    file, output = Path(file).resolve(), Path(output).resolve()
    data = read(file)
    esc = lambda value: html.escape(str(value), quote=True)
    rows = []
    for key, candidate in data["candidates"].items():
        source = (file.parent / candidate["file"]).resolve()
        current = source.is_file() and file_hash(source) == candidate["sha256"]
        url = esc(source.as_uri())
        native = (f'<video controls preload="metadata" src="{url}"></video>' if candidate["kind"] == "video"
                  else f'<img src="{url}">') if current else '<b>Source missing or changed</b>'
        images = "".join(f'<a href="{esc(Path(image["file"]).as_uri())}"><img src="{esc(Path(image["file"]).as_uri())}"></a>'
                         for image in candidate.get("preview", {}).get("images", [])
                         if Path(image["file"]).is_file() and file_hash(image["file"]) == image["sha256"])
        details = {k: candidate.get(k) for k in ("url", "author", "license", "rights", "measurements", "ranges")}
        rows.append(f'<article><h2>{esc(key)} · {esc(candidate.get("title") or "Untitled candidate")}</h2>{native}{images}'
                    f'<pre>{esc(json.dumps(details, ensure_ascii=False, indent=2))}</pre></article>')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('<!doctype html><meta charset="utf-8"><title>Media library</title>'
                      '<style>body{font:16px system-ui;margin:2rem}article{border-top:1px solid #ccc;padding:1rem 0}'
                      'img,video{max-width:720px;width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
                      '<h1>Media candidates and recorded reviews</h1>' + "".join(rows), encoding="utf-8")
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("catalogue", type=Path)
    inspect.add_argument("--query", default="")
    migrate = commands.add_parser("import-storyboard")
    migrate.add_argument("catalogue", type=Path)
    migrate.add_argument("--source", type=Path, required=True)
    migrate.add_argument("--expected-sha256", required=True)
    for name in ("import", "fetch", "review", "preview"):
        command = commands.add_parser(name)
        command.add_argument("catalogue", type=Path)
        command.add_argument("--id", required=True)
        command.add_argument("--expected-sha256", required=True, help="inspect's SHA-256, or new for the first import")
        if name in {"import", "fetch"}:
            command.add_argument("--metadata", type=Path, help="explicit source metadata; approval stays unknown")
        if name == "import":
            command.add_argument("--file", type=Path, required=True)
        if name in {"fetch", "preview"}:
            command.add_argument("--root", type=Path, required=True, help="the Polyweave project")
            command.add_argument("--out", required=True, help="output under the Polyweave root")
        if name == "fetch":
            command.add_argument("--stock-id", type=int, required=True)
            command.add_argument("--service", choices=["pixabay", "pexels"], default="pixabay")
            command.add_argument("--kind", choices=["picture", "video"], default="video")
        if name == "review":
            command.add_argument("--record", type=Path, required=True)
        if name == "preview":
            command.add_argument("--rate", type=float, default=.2)
    page = commands.add_parser("sheet")
    page.add_argument("catalogue", type=Path)
    page.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "inspect":
        data = read(args.catalogue)
        data["candidates"] = {k: c for k, c in data["candidates"].items()
                              if args.query.casefold() in json.dumps([k, c], ensure_ascii=False).casefold()}
        print(json.dumps({"sha256": file_hash(args.catalogue), "data": data}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "sheet":
        print(sheet(args.catalogue, args.out))
        return 0
    actual = file_hash(args.catalogue) if args.catalogue.exists() else "new"
    if actual != args.expected_sha256:
        raise ValueError("stale library; inspect before downloading, previewing or reviewing")
    if args.command == "import-storyboard":
        original = json.loads(args.source.read_text("utf-8-sig"))
        imported_rows = {key: imported(args.source.parent / asset["file"], asset, args.catalogue)
                         for key, asset in original.get("media", {}).items()}
        def insert(data):
            for key, candidate in imported_rows.items():
                add(data, key, candidate)
        result = update(args.catalogue, actual, insert)
    elif args.command in {"import", "fetch"}:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.id) or (args.catalogue.exists() and args.id in read(args.catalogue)["candidates"]):
            raise ValueError("choose an unused simple candidate ID before importing or fetching")
        metadata = json.loads(args.metadata.read_text("utf-8-sig")) if args.metadata else {}
        if args.command == "fetch":
            if (args.root / args.out).exists():
                raise ValueError("fetch output already exists; choose an unused path to preserve prior media")
            fetched = delegate("stock.fetch", args.root, id=args.stock_id, service=args.service, kind=args.kind, out=args.out)
            credits = delegate("provenance.credits", args.root, all=True)
            source = args.root / args.out
            relative = os.path.relpath(source.resolve(), args.root.resolve()).replace("\\", "/")
            metadata = {**metadata, "fetch_record": fetched,
                        "credits_record": [row for row in credits.get("artefacts", []) if row.get("file") == relative]}
        else:
            source = args.file
        candidate = imported(source, metadata, args.catalogue)
        result = update(args.catalogue, actual, lambda data: add(data, args.id, candidate))
    elif args.command == "review":
        candidate = read(args.catalogue)["candidates"][args.id]
        if file_hash(args.catalogue.parent / candidate["file"]) != candidate["sha256"]:
            raise RecordingRefused("candidate changed; import current bytes before recording approval")
        record = json.loads(args.record.read_text("utf-8-sig"))
        result = update(args.catalogue, actual, lambda data: review(data, args.id, record))
    else:
        result_preview = preview(args.catalogue, args.id, args.root, args.out, args.rate)
        result = update(args.catalogue, actual, lambda data: data["candidates"][args.id].update(preview=result_preview))
    print(f"library sha256 {result} {args.catalogue}")
    return 0
