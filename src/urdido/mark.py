"""The brand mark in a corner through the whole video (VM, `[mark]` in video.toml).

An illustrated video draws its header (logo, brand) into every page; a video made of filmed
scenes had no way to carry one. `[mark]` declares it once, for any source:

    [mark]
    logo = "<shio>/shio-react/public/favicon.svg"   # svg or png
    text = "Viglet Shio"                            # beside the logo; "" for the logo alone
    corner = "top-left"                             # top-left, top-right, bottom-left, bottom-right
    size = 44                                       # the logo's height at 1080 lines
    margin = [70, 50]                               # from the corner's sides, at 1080 lines
    opacity = 0.9
    font = "<shio>/marketplace/quilhara/assets/fonts/inter-400.woff2"   # optional
    background = "rgba(0,0,0,.55)"   # optional: a rounded plate behind it, so it reads on a light page

The defaults put it where the Japode videos' header sits (70 px from the left, 50 from the top).
The mark is drawn once as a transparent picture and laid over the joined video.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from html import escape
from pathlib import Path

CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")


@dataclass(frozen=True)
class Mark:
    logo: Path
    text: str = ""
    corner: str = "top-left"
    size: int = 44
    margin: tuple[int, int] = (70, 50)
    opacity: float = 0.9
    font: Path | None = None
    background: str = ""


def declared(decl: dict, resolve) -> Mark:
    """The `[mark]` table, checked: a value the build cannot honour refuses before anything renders."""
    unknown = set(decl) - {"logo", "text", "corner", "size", "margin", "opacity", "font", "background"}
    if unknown:
        raise SystemExit(f"videomaker build: [mark] does not take {', '.join(sorted(unknown))}")
    if not decl.get("logo"):
        raise SystemExit("videomaker build: [mark] needs logo, an svg or png")
    logo = Path(resolve(decl["logo"]))
    if logo.suffix.lower() not in {".svg", ".png"} or not logo.is_file():
        raise SystemExit(f"videomaker build: [mark] logo must be an existing svg or png, got {logo}")
    corner = decl.get("corner", "top-left")
    if corner not in CORNERS:
        raise SystemExit(f"videomaker build: [mark] corner must be one of {', '.join(CORNERS)}, got {corner!r}")
    margin = decl.get("margin", [70, 50])
    if not (isinstance(margin, list) and len(margin) == 2 and all(isinstance(v, int) and v >= 0 for v in margin)):
        raise SystemExit(f"videomaker build: [mark] margin must be [x, y] in pixels, got {margin!r}")
    size = decl.get("size", 44)
    if not isinstance(size, int) or not 12 <= size <= 300:
        raise SystemExit(f"videomaker build: [mark] size must be 12 to 300 pixels, got {size!r}")
    opacity = float(decl.get("opacity", 0.9))
    if not 0 < opacity <= 1:
        raise SystemExit(f"videomaker build: [mark] opacity must be above 0 and at most 1, got {opacity}")
    font = Path(resolve(decl["font"])) if decl.get("font") else None
    if font and not font.is_file():
        raise SystemExit(f"videomaker build: [mark] font {font} does not exist")
    background = decl.get("background", "")
    if not isinstance(background, str) or any(c in background for c in ";{}<>"):
        raise SystemExit(f"videomaker build: [mark] background must be one CSS colour, got {background!r}")
    return Mark(logo, str(decl.get("text", "")), corner, size, (margin[0], margin[1]), opacity, font, background)


def page(mark: Mark, scale: float) -> str:
    """The mark as a page whose only visible element is `#mark`, on a transparent body."""
    mime = "image/svg+xml" if mark.logo.suffix.lower() == ".svg" else "image/png"
    logo = f"data:{mime};base64," + base64.b64encode(mark.logo.read_bytes()).decode()
    size = round(mark.size * scale)
    face = family = ""
    if mark.font:
        fmt = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}.get(mark.font.suffix.lower(), "woff2")
        data = base64.b64encode(mark.font.read_bytes()).decode()
        face = f"@font-face{{font-family:MarkFont;src:url(data:font/{fmt};base64,{data}) format('{fmt}');font-weight:100 900}}"
        family = "MarkFont,"
    text = f"<b>{escape(mark.text)}</b>" if mark.text else ""
    plate = f"background: {mark.background}; border-radius: {round(size * .3)}px;" if mark.background else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{face}
  * {{ margin: 0; box-sizing: border-box; }}
  html, body {{ background: transparent; }}
  #mark {{ display: inline-flex; align-items: center; gap: {round(size * .36)}px; padding: {round(size * .3)}px;
    font-family: {family}Inter, 'Segoe UI', sans-serif; {plate} }}
  #mark img {{ height: {size}px; width: auto; filter: drop-shadow(0 2px {round(6 * scale)}px rgba(0,0,0,.6)); }}
  #mark b {{ color: #fff; font-size: {round(size * .62)}px; font-weight: 700; letter-spacing: {max(1, round(size * .07))}px;
    text-transform: uppercase; text-shadow: 0 2px {round(8 * scale)}px rgba(0,0,0,.75); }}
</style></head><body><div id="mark"><img src="{logo}">{text}</div></body></html>"""


def render(mark: Mark, parts: Path, height: int) -> Path:
    """Draw the mark once, scaled to the frame's height, as a transparent png."""
    from playwright.sync_api import sync_playwright

    out = parts / "mark.png"
    html = page(mark, height / 1080)
    (parts / "mark.html").write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            view = browser.new_page(viewport={"width": 1600, "height": 600})
            view.set_content(html, wait_until="networkidle")
            view.evaluate("document.fonts.ready")
            view.locator("#mark img").evaluate("img => img.decode()")
            view.locator("#mark").screenshot(path=str(out), omit_background=True)
        finally:
            browser.close()
    return out


def position(mark: Mark, height: int) -> tuple[str, str]:
    """ffmpeg overlay x and y for the corner. The margin counts from the drawn mark's padding,
    which `page` adds around the logo for its shadow, so the logo itself lands on the margin."""
    scale = height / 1080
    pad = round(round(mark.size * scale) * .3)
    mx, my = round(mark.margin[0] * scale) - pad, round(mark.margin[1] * scale) - pad
    vertical, horizontal = mark.corner.split("-")
    x = str(mx) if horizontal == "left" else f"W-w-{mx}"
    y = str(my) if vertical == "top" else f"H-h-{my}"
    return x, y


def overlay(joined: str, mark: Mark, parts: Path, encoder: str, height: int) -> str:
    """Lay the mark over the joined video for its whole length."""
    from videomaker import cache
    from videomaker import media

    picture = render(mark, parts, height)
    x, y = position(mark, height)
    output = str(parts / "marked.mp4")
    graph = f"[1]format=rgba,colorchannelmixer=aa={mark.opacity:g}[m];[0][m]overlay={x}:{y}:format=auto"
    args = ["-i", joined, "-i", str(picture), "-filter_complex", graph,
            *media.video_codec(encoder, 20), "-pix_fmt", "yuv420p", "-an", output]
    cache.run("mark", [output], args, lambda: media.ffmpeg(args),
              inputs=[__file__, media.__file__, joined, str(picture)], tools=["ffmpeg"])
    return output
