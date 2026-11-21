"""VM59 / PW712: declared visual repetition budgets, measured before encoding."""
from __future__ import annotations

import json
import math
import warnings
from collections import defaultdict
from pathlib import Path

from urdido.cache import file_hash
from urdido.declaration import BEAT, held
from urdido.sources.model import RecordingRefused

RULES = {"overlap", "gap", "adjacent", "source_seconds", "category_share"}


def number(value, field, *, share=False, integer=False):
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or value < 0 \
            or (share and value > 1) or (integer and (not isinstance(value, int) or value < 1)):
        raise ValueError(f"repetition.{field}: invalid nonnegative {'share' if share else 'limit'}")
    return value


def inspect(document, edit, folder, opening=0):
    spec = document.get("repetition", {})
    action = spec.get("action", "warn" if spec else "off")
    if action not in {"warn", "error", "off"}:
        raise ValueError("repetition.action must be warn, error or off")
    assets = document.get("media", {})
    source_rules = spec.get("sources", {})
    if not isinstance(spec.get("replace_file_counts", False), bool):
        raise ValueError("repetition.replace_file_counts must be boolean")
    if set(source_rules) - set(assets):
        raise ValueError("repetition.sources names an unknown media asset")
    for limits in [spec, *source_rules.values()]:
        for field in ("max_overlap_seconds", "min_gap_seconds", "max_source_seconds", "max_adjacent"):
            number(limits.get(field), field, integer=field == "max_adjacent")
    category_rules = spec.get("max_category_share", {})
    for key, limit in category_rules.items():
        number(limit, f"max_category_share.{key}", share=True)
    if spec.get("replace_file_counts") and not category_rules and not any(
            limits.get(field) is not None for limits in [spec, *source_rules.values()]
            for field in ("max_overlap_seconds", "min_gap_seconds", "max_source_seconds", "max_adjacent")):
        raise ValueError("replacing file counts requires at least one declared repetition budget")
    beats = {f"{take}-{i}": (take, beat) for take, values in document["scenes"].items() for i, beat in enumerate(values)}
    parent, known_hashes, known_ids, paths, identity = {}, {}, {}, {}, {}

    def find(key):
        parent.setdefault(key, key)
        if parent[key] != key:
            parent[key] = find(parent[key])
        return parent[key]

    selected_assets = {beat.get("asset") for _, beat in beats.values()}
    for key, asset in assets.items():
        # A budget's named alias still identifies its source when another alias is selected.
        if key not in selected_assets and key not in source_rules:
            continue
        path = (Path(folder) / asset["file"]).resolve()
        if path not in paths:
            paths[path] = file_hash(path)
        sha = paths[path]
        parent[key] = key
        if sha in known_hashes:
            parent[find(key)] = find(known_hashes[sha])
        known_hashes[sha] = key
        canonical = asset.get("source_id")
        if canonical is not None and (not isinstance(canonical, str) or not canonical.strip()):
            raise ValueError("source_id must be an explicitly declared nonempty name")
        if canonical:
            if canonical in known_ids:
                parent[find(key)] = find(known_ids[canonical])
            known_ids[canonical] = key
        offset = number(asset.get("source_offset", 0), "source_offset")
        if offset is None:
            raise ValueError("source_offset must be finite and nonnegative")
        identity[key] = (sha, canonical, offset)
    rows, category_rows = [], []
    for index, shot in enumerate(edit["beats"]):
        take, beat = beats[shot["beat"]]
        key = beat.get("asset")
        asset = assets.get(key, {})
        categories = beat.get("categories", asset.get("categories", []))
        if not isinstance(categories, list) or not all(isinstance(c, str) and c.strip() for c in categories):
            raise ValueError(f"{shot['beat']}: categories must be a list of declared names")
        category_rows.append({"beat": beat.get("id", shot["beat"]), "seconds": shot["seconds"], "categories": sorted(set(categories))})
        if key not in identity:
            continue
        sha, canonical, offset = identity[key]
        at = held(beat, BEAT, "at")
        rows.append({"beat": beat.get("id", shot["beat"]), "take": take, "asset": key,
                     "index": index, "group": find(key), "sha256": sha, "source_id": canonical,
                     "source_offset": offset, "source_start": at, "source_end": at + shot["seconds"],
                     "start": opening + shot["at"], "end": opening + shot["at"] + shot["seconds"],
                     "seconds": shot["seconds"], "picture": beat.get("layout") == "picture",
                     "categories": sorted(set(categories))})
    total = opening + sum(s["seconds"] for s in edit["beats"])
    findings, overlaps, summaries = [], [], []
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["group"]].append(row)

    def finding(rule, affected, observed, limit, detail):
        item = {"rule": rule, "beats": [r["beat"] for r in affected], "observed": observed,
                "limit": limit, "detail": detail}
        findings.append(item)
        return item

    for key, uses in grouped.items():
        aliases = sorted(alias for alias in identity if find(alias) == key)
        def limit(field, aliases=aliases):
            specific = {source_rules[a][field] for a in aliases if field in source_rules.get(a, {})}
            if len(specific) > 1:
                raise ValueError(f"aliases {aliases} have conflicting repetition.{field} limits")
            return next(iter(specific)) if specific else spec.get(field)
        seconds = sum(r["seconds"] for r in uses)
        summaries.append({"aliases": aliases, "beats": [r["beat"] for r in uses], "screen_seconds": seconds})
        maximum = limit("max_source_seconds")
        if maximum is not None and seconds > maximum + 1e-7:
            finding("source_seconds", uses, seconds, maximum, f"source {aliases} screen time")
        maximum = limit("max_adjacent")
        run = []
        adjacency = None
        for use in uses:
            if run and use["index"] == run[-1]["index"] + 1:
                run.append(use)
            else:
                run, adjacency = [use], None
            if maximum is not None and len(run) > maximum:
                if adjacency:
                    adjacency.update(beats=[r["beat"] for r in run], observed=len(run))
                else:
                    adjacency = finding("adjacent", run, len(run), maximum, f"source {aliases} consecutive appearances")
        for i, right in enumerate(uses):
            if i:
                left = uses[i - 1]
                gap = right["start"] - left["end"]
                minimum = limit("min_gap_seconds")
                if minimum is not None and gap < minimum - 1e-7:
                    finding("gap", [left, right], gap, minimum, f"source {aliases} reuse gap in seconds")
            for left in uses[:i]:
                overlap_start = overlap_end = None
                basis = "picture"
                if left["picture"] or right["picture"]:
                    overlap = min(left["seconds"], right["seconds"]) if left["picture"] and right["picture"] and left["sha256"] == right["sha256"] else 0
                elif left["sha256"] == right["sha256"]:
                    basis = "source bytes"
                    overlap_start = max(left["source_start"], right["source_start"])
                    overlap_end = min(left["source_end"], right["source_end"])
                    overlap = overlap_end - overlap_start
                elif left["source_id"] and left["source_id"] == right["source_id"]:
                    basis = "declared source"
                    overlap_start = max(left["source_start"] + left["source_offset"], right["source_start"] + right["source_offset"])
                    overlap_end = min(left["source_end"] + left["source_offset"], right["source_end"] + right["source_offset"])
                    overlap = overlap_end - overlap_start
                else:
                    overlap = 0
                if overlap > 1e-7:
                    overlaps.append({"beats": [left["beat"], right["beat"]], "seconds": overlap,
                                     "basis": basis, "source_start": overlap_start, "source_end": overlap_end})
                    maximum = limit("max_overlap_seconds")
                    if maximum is not None and overlap > maximum + 1e-7:
                        interval = f" {overlap_start:g}..{overlap_end:g}" if overlap_start is not None else " (picture)"
                        finding("overlap", [left, right], overlap, maximum, f"repeated source interval{interval} in seconds")
    category_usage = {}
    for category in {c for row in category_rows for c in row["categories"]}:
        selected = [row for row in category_rows if category in row["categories"]]
        seconds = sum(r["seconds"] for r in selected)
        share = seconds / total if total else 0
        category_usage[category] = {"seconds": seconds, "share": share, "beats": [r["beat"] for r in selected]}
        maximum = category_rules.get(category)
        if maximum is not None and share > maximum + 1e-7:
            finding("category_share", selected, share, maximum, f"category {category!r} share of the full cut")
    available = {beat.get("id", key) for key, (_, beat) in beats.items()}
    for exception in spec.get("exceptions", []):
        if exception.get("rule") not in RULES or not isinstance(exception.get("reason"), str) or not exception["reason"].strip() \
                or not exception.get("beats") or not set(exception["beats"]) <= available:
            raise ValueError("repetition exceptions need a known rule, existing beat IDs and an explicit reason")
        for item in findings:
            if item["rule"] == exception["rule"] and set(item["beats"]) <= set(exception["beats"]):
                item["exception"] = exception["reason"]
    return {"action": action, "total_seconds": total, "shots": rows, "sources": summaries,
            "overlaps": overlaps, "categories": category_usage, "findings": findings,
            "unclassified_media_seconds": sum(r["seconds"] for r in rows if not r["categories"])}


def enforce(report):
    failed = [f for f in report["findings"] if "exception" not in f]
    if not failed or report["action"] == "off":
        return
    message = "repetition budget:\n" + "\n".join(
        f"{', '.join(f['beats'])}: {f['detail']} = {f['observed']:g}; limit {f['limit']:g}" for f in failed)
    if report["action"] == "error":
        raise RecordingRefused(message)
    warnings.warn(message, UserWarning, stacklevel=2)


def publish(report, path):
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
