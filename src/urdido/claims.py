"""VM64 / PW716: narrated claims, declared evidence and human review freshness."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import tempfile
import tomllib
import warnings
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from urdido import keywords
from urdido.cache import file_hash
from urdido.narration import Takes
from urdido.sources.model import RecordingRefused

KINDS = {"historical", "statistic", "editorial", "footage"}
DATES = ("source_date", "event_date", "published_at", "retrieved_at")


def iso(value):
    if value is not None:
        return date.fromisoformat(value)


def url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("claim evidence needs an HTTP(S) source URL without credentials")
    return value


def read(file):
    data = json.loads(Path(file).read_text("utf-8-sig"))
    if data.get("version") != 1 or not isinstance(data.get("claims"), list):
        raise ValueError("claims need version=1 and a claims array")
    return data


def inspect(data, takes, language, document, folder, *, action="warn", today=None):
    if data.get("version") != 1 or not isinstance(data.get("claims"), list):
        raise ValueError("claims need version=1 and a claims array")
    if action not in {"off", "warn", "error"}:
        raise ValueError("claims.action must be off, warn or error")
    today = today or date.today()
    report = {"action": action, "as_of": today.isoformat(), "coverage": "declared claims only", "claims": [], "findings": []}
    seen = set()
    for claim in data["claims"]:
        key = claim["id"]
        if not isinstance(key, str) or not key.strip() or key in seen or claim.get("kind") not in KINDS:
            raise ValueError("claim needs a unique nonempty id and kind historical/statistic/editorial/footage")
        seen.add(key)
        if claim.get("language") != language:
            continue
        take = claim["take"]
        if take not in takes.lines or not isinstance(claim.get("text"), str) or not claim["text"].strip():
            raise ValueError(f"{key}: unknown take or missing claim text")
        if not claim.get("anchor"):
            raise ValueError(f"{key}: declare an exact narration word anchor")
        spoken = takes.lines[take][language]
        evidence = []
        for item in claim.get("evidence", []):
            source = document.get("sources", {}).get(item.get("source"), {})
            source_url = item.get("url", source.get("url"))
            if not source_url or not item.get("note"):
                raise ValueError(f"{key}: evidence needs a source URL and excerpt or note")
            for field in DATES:
                iso(item.get(field))
            row = {**item, "url": url(source_url), "label": item.get("label", source.get("label", key)), "source_record": source}
            if item.get("file"):
                row["snapshot_sha256"] = file_hash(Path(folder) / item["file"])
            evidence.append(row)
        illustrations = []
        for item in claim.get("illustrations", []):
            asset = document.get("media", {}).get(item["asset"])
            if asset is None:
                raise ValueError(f"{key}: unknown illustrative asset")
            for field in DATES:
                iso(item.get(field))
            illustrations.append({**item, "media_record": asset, "sha256": file_hash(Path(folder) / asset["file"])})
        payload = {"claim": {k: v for k, v in claim.items() if k not in {"review", "reviews"}},
                   "narration": spoken, "evidence": evidence, "illustrations": illustrations,
                   "aliases": keywords.aliases(takes.script, language)}
        audio = Path(takes.take_file(language, take))
        payload["audio_sha256"] = file_hash(audio) if audio.is_file() else None
        payload["words_sha256"] = file_hash(audio.with_suffix(".words.json")) if audio.with_suffix(".words.json").is_file() else None
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        reasons = []
        try:
            anchor = keywords.anchor(Path(takes.take_file(language, take)), claim["anchor"], aliases=keywords.aliases(takes.script, language))
            if not takes.current(takes.take_file(language, take), language, spoken):
                anchor = None
                reasons.append("narration take is stale; prepare current audio before reviewing")
        except (RecordingRefused, OSError, ValueError) as exc:
            anchor = None
            reasons.append(f"unresolved narration anchor: {exc}")
        review = claim.get("review", {})
        status = review.get("status", "unreviewed")
        if status not in {"unreviewed", "approved", "rejected"}:
            raise ValueError(f"{key}: invalid review status")
        if status != "unreviewed":
            if not all(isinstance(review.get(k), str) and review[k].strip() for k in ("reviewer", "date", "reason", "fingerprint")):
                raise ValueError(f"{key}: review needs reviewer, date, reason and fingerprint")
            reviewed = iso(review["date"])
            deadline = iso(review.get("valid_until"))
            if reviewed > today:
                reasons.append("review date is in the future")
            if deadline is not None and (deadline < reviewed or today > deadline):
                reasons.append("review has expired or has an invalid deadline")
            if claim["kind"] == "statistic" and deadline is None:
                reasons.append("changing statistic needs an explicit review deadline")
            if review["fingerprint"] != fingerprint:
                reasons.append("claim, narration or evidence changed since review")
        if not evidence:
            reasons.append("no supporting evidence declared; an editorial conclusion still needs its rationale")
        if any(not item.get("retrieved_at") for item in evidence):
            reasons.append("evidence retrieval date is unknown")
        effective = "needs_review" if reasons else status
        if status != "approved" or effective != "approved":
            report["findings"].append({"id": key, "status": effective, "reasons": reasons or [f"human review is {status}"]})
        report["claims"].append({**claim, "evidence": evidence, "illustrations": illustrations, "fingerprint": fingerprint,
                                  "narration": spoken, "take_seconds": anchor, "effective_status": effective,
                                  "review_reasons": reasons})
    return report


def enforce(report):
    if not report["findings"] or report["action"] == "off":
        return
    message = "claim review:\n" + "\n".join(f"{r['id']}: {r['status']} - {'; '.join(r['reasons'])}" for r in report["findings"])
    if report["action"] == "error":
        raise RecordingRefused(message)
    warnings.warn(message, UserWarning, stacklevel=2)


def citations(report):
    return [{"label": row["id"] + ": " + item["label"], "url": item["url"]}
            for row in report["claims"] if row["effective_status"] == "approved" for item in row["evidence"]]


def publish(report, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    esc = lambda value: html.escape(str(value))
    rows = []
    for row in report["claims"]:
        evidence = "".join(f'<p><a href="{esc(item["url"])}">{esc(item["label"])}</a><br>{esc(item["note"])}<br>'
                           + " · ".join(f"{field}: {esc(item.get(field) or 'unknown')}" for field in DATES) + "</p>" for item in row["evidence"])
        illustrations = "".join(f'<p>{esc(item["asset"])}: event {esc(item.get("event_date") or "unknown")}; '
                                f'publication {esc(item.get("published_at") or "unknown")}<br>{esc(item.get("note", ""))}</p>' for item in row["illustrations"])
        review = row.get("review", {})
        rows.append(f'<tr><td><b>{esc(row["id"])}</b><br>{esc(row["kind"])}<br>{esc(row["take"])} + {esc(row["take_seconds"])}s</td>'
                    f'<td>{esc(row["text"])}<details><summary>Full narration</summary>{esc(row["narration"])}</details></td>'
                    f'<td>{evidence}{illustrations}</td><td><b>{esc(row["effective_status"])}</b><br>'
                    f'Recorded: {esc(review.get("status", "unreviewed"))}<br>'
                    f'{esc(review.get("reviewer", ""))} {esc(review.get("date", ""))}<br>{esc(review.get("reason", ""))}<br>'
                    f'Valid until: {esc(review.get("valid_until") or "not declared")}<br>'
                    f'{esc("; ".join(row["review_reasons"]))}<details><summary>Review fingerprint</summary>{row["fingerprint"]}</details></td></tr>')
    output.write_text('<!doctype html><meta charset="utf-8"><title>Claim review</title><style>'
                      'body{font:16px/1.5 system-ui;margin:32px;color:#18251f}table{border-collapse:collapse;width:100%;table-layout:fixed}'
                      'td,th{border:1px solid #bdcbc2;padding:14px;vertical-align:top;overflow-wrap:anywhere}th{text-align:left;background:#edf4ef}'
                      'p{margin:0 0 14px}details{margin-top:12px}h1{margin-bottom:4px}</style><h1>Narrative claim review</h1>'
                      f'<p>As of {esc(report["as_of"])}. Declared claims only. A URL is not proof; footage publication is separate from event date.</p>'
                      '<table><tr><th>Claim / anchor</th><th>Narrated statement</th><th>Evidence / illustrative footage</th><th>Human review</th></tr>'
                      + "".join(rows) + '</table>', encoding="utf-8")
    return output


def context(declaration, language):
    path = Path(declaration).resolve()
    spec = tomllib.loads(path.read_text("utf-8-sig"))
    folder = path.parent
    source = json.loads((folder / spec["source"]["declaration"]).read_text("utf-8-sig"))
    from urdido.library import resolve

    source = resolve(source, folder)
    script = json.loads((folder / spec["narration"]["script"]).read_text("utf-8-sig"))
    file = folder / spec["claims"]["declaration"]
    takes = Takes(script, str(folder / spec["narration"]["takes"]), spec["narration"].get("tempo", 1.0))
    report = inspect(read(file), takes, language, source, folder, action=spec["claims"].get("action", "warn"))
    return file, report


def record_review(file, expected, key, report, review):
    if review.get("status") not in {"approved", "rejected"} or not all(isinstance(review.get(k), str) and review[k].strip()
                                                                 for k in ("reviewer", "date", "reason", "fingerprint")):
        raise ValueError("review needs approved/rejected, reviewer, date, reason and current fingerprint")
    reviewed = iso(review["date"])
    deadline = iso(review.get("valid_until"))
    row = next(r for r in report["claims"] if r["id"] == key)
    if review["fingerprint"] != row["fingerprint"]:
        raise ValueError("review fingerprint is stale; inspect current narration and evidence")
    if reviewed > date.today() or (deadline is not None and deadline < reviewed):
        raise ValueError("review date or deadline is invalid")
    if review["status"] == "approved" and deadline is not None and deadline < date.today():
        raise ValueError("cannot approve an already expired review")
    if review["status"] == "approved" and (not row["evidence"] or row["take_seconds"] is None
            or any(not e.get("retrieved_at") for e in row["evidence"]) or (row["kind"] == "statistic" and deadline is None)):
        raise ValueError("approval needs resolved narration, dated evidence and a statistic review deadline")
    file = Path(file)
    lock = file.with_name(file.name + ".review.lock")
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    pending = None
    try:
        if file_hash(file) != expected:
            raise ValueError("stale claims: inspect current SHA-256 before reviewing")
        data = read(file)
        claim = next(c for c in data["claims"] if c["id"] == key)
        claim.setdefault("reviews", []).append(claim.get("review", {"status": "unreviewed"}))
        claim["review"] = {**review, "fingerprint": row["fingerprint"]}
        fd, name = tempfile.mkstemp(prefix=file.name + ".", suffix=".tmp", dir=file.parent)
        pending = Path(name)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        if file_hash(file) != expected:
            raise ValueError("claims changed during review")
        os.replace(pending, file)
    finally:
        if pending:
            pending.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
    return file_hash(file)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["inspect", "report", "review"])
    parser.add_argument("declaration")
    parser.add_argument("--language", required=True)
    parser.add_argument("--out")
    parser.add_argument("--id")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--review-file", help="explicit human review JSON, never inferred from evidence URLs")
    args = parser.parse_args(argv)
    file, report = context(args.declaration, args.language)
    if args.command == "inspect":
        print(json.dumps({"sha256": file_hash(file), **report}, ensure_ascii=False, indent=2))
    elif args.command == "report":
        if not args.out:
            parser.error("report needs --out HTML")
        print(publish(report, args.out))
    else:
        if not all((args.id, args.expected_sha256, args.review_file)):
            parser.error("review needs --id, --expected-sha256 and --review-file")
        record = json.loads(Path(args.review_file).read_text("utf-8-sig"))
        print(record_review(file, args.expected_sha256, args.id, report, record))
    return 0
