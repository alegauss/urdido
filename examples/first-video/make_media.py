"""Make the first video's media: two narration takes and one clip of footage.

    python examples/first-video/make_media.py

Media is never versioned, so the example makes its own with ffmpeg: a tone stands in for
each narration take and a test pattern for the footage. A real video buys its takes
(`urdido prepare`) and fetches or films its footage.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TAKES = {"intro": (440, 2.4), "outro": (550, 2.0)}


def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def main(folder: Path = HERE) -> int:
    takes = folder / "narration" / "en"
    takes.mkdir(parents=True, exist_ok=True)
    for name, (frequency, seconds) in TAKES.items():
        ffmpeg(
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:duration={seconds}",
            str(takes / f"{name}.mp3"),
        )
    footage = folder / "footage" / "src"
    footage.mkdir(parents=True, exist_ok=True)
    ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30:duration=12",
        "-pix_fmt",
        "yuv420p",
        str(footage / "pattern.mp4"),
    )
    print(f"media made under {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else HERE))
