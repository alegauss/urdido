"""VM39 / PW707: measurements bound to the exact exported MP4, never a prior cut."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
from fractions import Fraction
from pathlib import Path

from urdido import media


def sha256(file: Path) -> str:
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def opening_frames(log: str) -> dict:
    """Decoded frame hashes and presentation times; repeated frames are not camera judder."""
    base = re.search(r"#tb 0: (\d+/\d+)", log)
    if not base:
        raise RuntimeError("QA: decoded opening has no time base")
    tick = float(Fraction(base[1]))
    rows = [line.split(",") for line in log.splitlines() if line and not line.startswith("#")]
    times = [int(row[2]) * tick for row in rows]
    if not times:
        raise RuntimeError("QA: no opening video frames decoded")
    intervals = [round(b - a, 9) for a, b in zip(times, times[1:])]
    repeats = []
    start = 0
    for end in range(1, len(rows) + 1):
        if end < len(rows) and rows[end][-1].strip() == rows[start][-1].strip():
            continue
        if end - start > 1:
            repeats.append({"from": times[start], "to": times[end - 1], "frames": end - start})
        start = end
    return {"decoded_frames": len(rows), "presentation_times": times,
            "intervals": intervals, "nonpositive_intervals": sum(t <= 0 for t in intervals),
            "identical_frame_runs": repeats}


def editorial(edit: dict | None, highlights: dict | None, assets: dict | None = None) -> dict | None:
    if edit is None:
        return None
    beats = edit["beats"]
    used = {b["asset"] for b in beats if b.get("asset")}
    sources = {(assets or {}).get(key, {}).get("file", key) for key in used}
    return {"shots": len(beats), "assets": len(used), "source_files": len(sources),
            "static_seconds": sum(b["seconds"] for b in beats if b["static"]),
            "highlights": sum(len(v) for v in highlights.get("lines", {}).values()) if highlights else 0}


def report(file: str | Path, *, edit: dict | None = None, highlights: dict | None = None,
           assets: dict | None = None, text_files=(), peak_ceiling: float | None = None) -> Path:
    """Fail if any measurement fails or the MP4 changes. Write a sidecar and decoded first frame.

    The bounded opening sample covers at most 120 frames. It measures decoded repetition and
    timestamp cadence, without deciding whether movement is artistically appropriate.
    """
    file = Path(file)
    output = file.with_suffix(".qa.json")
    image = file.with_suffix(".first.png")
    pending = output.with_suffix(".json.tmp")
    for stale in (output, image, pending):
        stale.unlink(missing_ok=True)
    try:
        signature = sha256(file)
        probe = json.loads(subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(file)],
            check=True, capture_output=True, text=True, encoding="utf-8").stdout)
        if not any(s["codec_type"] == "video" for s in probe["streams"]):
            raise RuntimeError("QA: output has no video stream")
        levels = [{"stream": s["index"], "language": s.get("tags", {}).get("language"),
                   "measurement": media.measure_loudness([
                       "-i", str(file), "-map", f"0:{s['index']}", "-vn", "-sn",
                       "-af", "loudnorm=print_format=json"])}
                  for s in probe["streams"] if s["codec_type"] == "audio"]
        if peak_ceiling is not None:
            check_true_peak(levels, peak_ceiling)
        # PW702: decode from the beginning without seeking to an approximate thumbnail timestamp.
        media.ffmpeg(["-i", str(file), "-map", "0:v:0", "-frames:v", "1", str(image)])
        decoded = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(file), "-map", "0:v:0", "-an", "-sn",
             "-frames:v", "120", "-fps_mode", "passthrough", "-f", "framemd5", "-"],
            check=True, capture_output=True, text=True, encoding="utf-8").stdout
        texts = []
        for path in text_files:
            path = Path(path)
            path.read_text(encoding="utf-8", errors="strict")
            texts.append({"file": str(path), "sha256": sha256(path), "utf8": True})
        data = {"schema": 1, "file": str(file.resolve()), "sha256": signature,
                "bytes": file.stat().st_size, "duration": float(probe["format"]["duration"]),
                "streams": probe["streams"], "loudness": levels,
                "peak_ceiling": peak_ceiling,
                "first_frame": {"file": image.name, "sha256": sha256(image), "video_sha256": signature},
                "opening": opening_frames(decoded), "editorial": editorial(edit, highlights, assets), "texts": texts}
        if sha256(file) != signature:
            raise RuntimeError("QA: output changed during measurement; build again")
        pending.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(pending, output)
        return output
    except BaseException:
        for stale in (output, image, pending):
            stale.unlink(missing_ok=True)
        raise


def check_true_peak(levels: list[dict], ceiling: float) -> None:
    """VM47 / PW697: hold every encoded audio stream to the mix's promised ceiling."""
    if not math.isfinite(ceiling) or ceiling > 0:
        raise ValueError("QA: peak ceiling must be finite and at most 0 dBTP")
    breaches = []
    for level in levels:
        try:
            peak = float(level["measurement"]["input_tp"])
            if math.isnan(peak):
                raise ValueError("NaN")
        except (KeyError, TypeError, ValueError):
            raise RuntimeError(f"QA: audio stream {level['stream']} has no valid encoded true-peak measurement") from None
        if peak > ceiling:
            breaches.append(f"stream {level['stream']} ({level.get('language') or 'und'}): {peak:.2f} dBTP > {ceiling:.2f} dBTP")
    if breaches:
        raise RuntimeError("QA: encoded true peak exceeds the declared ceiling: " + "; ".join(breaches)
                           + "; increase [audio].margin and rebuild")
