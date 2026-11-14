"""A video's YouTube thumbnail, declared in its video.toml and drawn by its channel's layout.

    python -m videomaker thumbnail <video.toml> --language pt-BR

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
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
import tomllib
from pathlib import Path

from videomaker import media


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


def layout(path: Path):
    spec = importlib.util.spec_from_file_location("channel_layout", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.thumbnail


def make(declaration: Path, language: str) -> Path:
    here = declaration.parent
    decl = tomllib.loads(declaration.read_text(encoding="utf-8"))["thumbnail"]
    words = dict(decl["words"][language])
    work = here / "video" / "parts" / "thumbnail"
    work.mkdir(parents=True, exist_ok=True)
    fields = {**words, "picture": still(here, decl["picture"], work / "picture.png")}
    if "proof" in decl:
        fields["proof"] = still(here, decl["proof"], work / "proof.png")
    if "badges" in fields:
        fields["badges"] = tuple(fields["badges"])
    out = here / decl.get("out", "video/thumbnail.{language}.jpg").format(language=language)
    return layout((here / decl["layout"]).resolve())(**fields, out=out)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="python -m videomaker thumbnail")
    p.add_argument("declaration")
    p.add_argument("--language", required=True)
    args = p.parse_args(argv)
    out = make(Path(args.declaration).resolve(), args.language)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
