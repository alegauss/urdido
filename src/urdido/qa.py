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


#: The size frames are compared at, grey: enough for a picture change, cheap for a long cut.
SCAN = (32, 18)


def difference(a: bytes, b: bytes) -> float:
    """Mean absolute difference of two grey frames, 0 to 255."""
    return sum(abs(x - y) for x, y in zip(a, b, strict=True)) / len(a)


def flashes(frames: list[bytes], fps: float, *, threshold: float = 6.0, longest: int = 2) -> list[dict]:
    """UR14: changes that last a frame or two and come back, by picture difference.

    A flash at frame i is a run of 1..`longest` frames that each differ from frame i-1 by at
    least `threshold`, while the frame after the run is back near frame i-1 (within a third
    of the jump): a white page between dark frames, or a different picture of the same
    brightness. A cut changes and stays changed, so it is not one."""
    found, i = [], 1
    while i < len(frames) - 1:
        jump = difference(frames[i - 1], frames[i])
        if jump < threshold:
            i += 1
            continue
        hit = None
        for run in range(1, longest + 1):
            after = i + run
            if after >= len(frames):
                break
            if any(difference(frames[i - 1], frames[k]) < threshold for k in range(i, after)):
                break
            back = difference(frames[i - 1], frames[after])
            if back <= jump / 3:
                hit = {"at": round(i / fps, 3), "frames": run, "jump": round(jump, 1), "back": round(back, 1)}
                break
        if hit:
            found.append(hit)
            i += hit["frames"] + 1
        else:
            i += 1
    return found


def scan_frames(file: Path) -> tuple[list[bytes], float]:
    """Every frame of the file, grey at SCAN size, and its frame rate."""
    width, height = SCAN
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=avg_frame_rate",
         "-of", "json", str(file)], check=True, capture_output=True, text=True, encoding="utf-8").stdout)
    fps = float(Fraction(probe["streams"][0]["avg_frame_rate"]))
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(file), "-map", "0:v:0", "-an", "-sn", "-fps_mode", "passthrough",
         "-vf", f"scale={width}:{height}:flags=area,format=gray", "-f", "rawvideo", "-"],
        check=True, capture_output=True).stdout
    size = width * height
    return [raw[k:k + size] for k in range(0, len(raw) - size + 1, size)], fps


def clip_at(clips: list[dict], at: float) -> str | None:
    for clip in clips:
        if clip["start"] <= at < clip["end"]:
            return clip["file"]
    return None


def check_flashes(found: list[dict], clips: list[dict], action: str) -> None:
    if not found or action == "off":
        return
    rows = [f"{f['at']:.3f} s ({f['frames']} frame(s), change {f['jump']} then {f['back']})"
            + (f" in {Path(c).name}" if (c := clip_at(clips, f["at"])) else "") for f in found]
    message = "QA: the cut flashes: " + "; ".join(rows) + "; trim the clip's blank frame and rebuild"
    if action == "error":
        raise RuntimeError(message)
    import warnings

    warnings.warn(message, UserWarning, stacklevel=2)


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
           assets: dict | None = None, text_files=(), peak_ceiling: float | None = None,
           clips: list[dict] = (), flash_action: str = "error") -> Path:
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
        if flash_action not in {"error", "warn", "off"}:
            raise ValueError("QA: [qa] flashes is error, warn or off")
        flashed = []
        if flash_action != "off":
            flashed = flashes(*scan_frames(file))
            check_flashes(flashed, list(clips), flash_action)
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
                "opening": opening_frames(decoded), "flashes": flashed, "editorial": editorial(edit, highlights, assets), "texts": texts}
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
