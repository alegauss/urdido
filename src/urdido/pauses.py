"""VM62 / PW707: sampled pauses in selected screen recordings, without edits."""
from __future__ import annotations

import json
import math
import subprocess
import tempfile
import warnings
from datetime import date
from pathlib import Path

from urdido.cache import file_hash
from urdido.declaration import BEAT, held
from urdido.sources.model import RecordingRefused


def settings(spec):
    result = {"action": "warn" if spec else "off", "max_pause_seconds": 3.0,
              "sample_fps": 5, "width": 320, "height": 180, "pixel_delta": 12,
              "min_changed_share": .002, "cursor_motion": "ignore-small", "all_footage": False,
              **spec}
    if result["action"] not in {"off", "warn", "error"} or result["cursor_motion"] not in {"count", "ignore-small"}:
        raise ValueError("pauses needs action off/warn/error and cursor_motion count/ignore-small")
    for field, low, high in (("max_pause_seconds", 0, 86400), ("sample_fps", 1, 30),
                             ("width", 16, 1920), ("height", 16, 1080), ("pixel_delta", 0, 255),
                             ("min_changed_share", 0, 1)):
        value = result[field]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"pauses.{field} is outside {low}..{high}")
        if field in {"width", "height", "pixel_delta"} and not isinstance(value, int):
            raise ValueError(f"pauses.{field} must be an integer")
    if not isinstance(result["all_footage"], bool):
        raise ValueError("pauses.all_footage must be boolean")
    return result


def intervals(samples, duration, spec):
    """Adjacent low-change samples delimit observed holds; no semantic cursor detection."""
    previous, start, last, rows, count = None, None, 0, [], 0
    for index, current in enumerate(samples):
        at = min(index / spec["sample_fps"], duration)
        if previous is not None:
            changed = sum(abs(a - b) > spec["pixel_delta"] for a, b in zip(previous, current, strict=False))
            share = changed / len(current)
            moving = changed > 0 if spec["cursor_motion"] == "count" else share >= spec["min_changed_share"] and changed > 0
            if not moving and start is None:
                start = last
            if moving and start is not None:
                rows.append({"start": start, "end": last, "seconds": last - start})
                start = None
        previous, last, count = current, at, count + 1
    if count < max(1, math.floor(duration * spec["sample_fps"]) - 1):
        raise RecordingRefused("pause measurement decoded too few samples")
    if start is not None:
        rows.append({"start": start, "end": duration, "seconds": duration - start})
    return {"samples": count, "intervals": rows, "longest_seconds": max((r["seconds"] for r in rows), default=0)}


def measure(file, start, duration, spec):
    """Read a bounded gray sample stream; stderr never shares or blocks the raw pipe."""
    signature = file_hash(file)
    args = ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(start), "-i", str(file), "-t", str(duration),
            "-map", "0:v:0", "-an", "-sn", "-vf",
            f"fps={spec['sample_fps']}:start_time=0,scale={spec['width']}:{spec['height']},format=gray",
            "-f", "rawvideo", "pipe:1"]
    size = spec["width"] * spec["height"]
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errors)
        def samples():
            while True:
                data = bytearray()
                while len(data) < size:
                    block = process.stdout.read(size - len(data))
                    if not block:
                        break
                    data.extend(block)
                if not data:
                    return
                if len(data) != size:
                    raise RecordingRefused("pause measurement decoded an incomplete sample")
                yield bytes(data)
        try:
            result = intervals(samples(), duration, spec)
            code = process.wait()
            if code:
                errors.seek(0)
                raise RecordingRefused("pause measurement failed: " + errors.read(2000).decode("utf-8", "replace"))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            process.stdout.close()
    if file_hash(file) != signature:
        raise RecordingRefused("screen recording changed during pause measurement")
    return {**result, "sha256": signature}


def inspect(document, edit, folder, opening=0):
    spec = settings(document.get("pauses", {}))
    report = {"settings": spec, "shots": [], "findings": [], "resolution_seconds": 1 / spec["sample_fps"]}
    if spec["action"] == "off":
        return report
    beats = {f"{take}-{i}": beat for take, values in document["scenes"].items() for i, beat in enumerate(values)}
    ids = {beat.get("id", key) for key, beat in beats.items()}
    exceptions = spec.get("exceptions", [])
    for exception in exceptions:
        if exception.get("beat") not in ids or not all(isinstance(exception.get(k), str) and exception[k].strip()
                                                       for k in ("reviewer", "date", "reason", "sha256")):
            raise ValueError("pause holds need an existing beat, reviewer, date, reason and source sha256")
        date.fromisoformat(exception["date"])
        start, end = exception.get("start"), exception.get("end")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, end)) or not 0 <= start < end:
            raise ValueError("pause hold needs a finite increasing source interval")
    measured = {}
    for shot in edit["beats"]:
        beat = beats[shot["beat"]]
        asset = document.get("media", {}).get(beat.get("asset"), {})
        selected = beat.get("screen_recording", asset.get("screen_recording", spec["all_footage"]))
        if not isinstance(selected, bool):
            raise ValueError("screen_recording must be boolean")
        if beat.get("layout") != "footage" or not selected:
            continue
        path = (Path(folder) / asset["file"]).resolve()
        at, duration = held(beat, BEAT, "at"), shot["seconds"]
        key = (str(path), at, duration)
        if key not in measured:
            measured[key] = measure(path, at, duration, spec)
        result = measured[key]
        row = {"beat": beat.get("id", shot["beat"]), "asset": beat["asset"], "file": str(path),
               "source_start": at, "source_end": at + duration, "timeline_start": opening + shot["at"],
               **result}
        report["shots"].append(row)
        for pause in result["intervals"]:
            if pause["seconds"] <= spec["max_pause_seconds"] + 1e-7:
                continue
            finding = {"beat": row["beat"], "file": str(path), "sha256": row["sha256"],
                       "seconds": pause["seconds"], "limit": spec["max_pause_seconds"],
                       "source_start": at + pause["start"], "source_end": at + pause["end"],
                       "timeline_start": row["timeline_start"] + pause["start"],
                       "timeline_end": row["timeline_start"] + pause["end"]}
            for exception in exceptions:
                if exception["beat"] == row["beat"] and exception["sha256"] == row["sha256"] \
                        and exception["start"] <= finding["source_start"] + 1e-7 and exception["end"] >= finding["source_end"] - 1e-7:
                    finding["reviewed_hold"] = exception
            report["findings"].append(finding)
    return report


def enforce(report):
    findings = [row for row in report["findings"] if "reviewed_hold" not in row]
    if not findings:
        return
    message = "screen recording pauses:\n" + "\n".join(
        f"{r['beat']} ({r['file']}): source {r['source_start']:.3f}..{r['source_end']:.3f}s; "
        f"timeline {r['timeline_start']:.3f}..{r['timeline_end']:.3f}s; {r['seconds']:.3f}s > {r['limit']:g}s" for r in findings)
    if report["settings"]["action"] == "error":
        raise RecordingRefused(message)
    warnings.warn(message, UserWarning, stacklevel=2)


def publish(report, path):
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
