"""The pages a video's cards are drawn from, in its theme (VM6).

Ported from the first demo's `story-video.mjs` (`style`, `card`, `linksCard`, the backdrop
and the hills). The module holds the layout; the theme (fonts, colours, backdrop, the ridges of
the parallax and how fast they slide) and every word are the video's declaration, such as
the first demo's `cards.json`. Each page here is byte for byte the one the JS builds for the
same video and language, which `tests/test_cards.py` holds against the goldens.
"""

from __future__ import annotations

import base64
import math
import os
from dataclasses import dataclass
from typing import Mapping, Sequence
from urllib.parse import quote

from urdido.captions import Chapter, chapter_title

# The closing card's icons, drawn in the line's colour.
ICONS = {
    "store": '<path d="M4 9l2-5h12l2 5M4 9v11h16V9M4 9h16M9 20v-6h6v6"/>',
    "docs": '<path d="M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2zM4 17a2 2 0 0 1 2-2h12M8 7h6"/>',
    "code": '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M14 5l-4 14"/>',
}

DOCTYPE = '<!doctype html><meta charset="utf-8">'


def _round(x: float) -> int:
    """Math.round: halves go up."""
    return math.floor(x + 0.5)


def encode_uri_component(text: str) -> str:
    return quote(text, safe="-_.!~*'()")


def font_url(path: str) -> str:
    with open(path, "rb") as f:
        return "data:font/woff2;base64," + base64.b64encode(f.read()).decode("ascii")


def resolve(path: str, roots: Mapping[str, str]) -> str:
    """A declared path with its `<name>` root replaced."""
    for name, root in roots.items():
        path = path.replace(f"<{name}>", root)
    return os.path.normpath(path)


@dataclass(frozen=True)
class Frame:
    width: int
    height: int

    @property
    def vertical(self) -> bool:
        return self.height > self.width


@dataclass
class Theme:
    """A declared theme, with its fonts read once."""

    data: Mapping
    fonts: Mapping[str, str]  # display-600, display-700, text: their data URLs

    @classmethod
    def load(cls, data: Mapping, roots: Mapping[str, str], font=font_url) -> "Theme":
        fonts = data["fonts"]
        folder = resolve(fonts["dir"], roots)
        urls = {f"display-{w}": font(os.path.join(folder, f)) for w, f in fonts["display"]["files"].items()}
        urls["text"] = font(os.path.join(folder, fonts["text"]["file"]))
        return cls(data, urls)

    @property
    def colors(self) -> Mapping[str, str]:
        return self.data["colors"]

    def ridge(self, which: str) -> str:
        ridge = self.data["ridges"][which]
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1920 420" preserveAspectRatio="none">'
            f'<polygon {ridge["fill"]} points="{ridge["points"]}"/></svg>'
        )
        return "data:image/svg+xml," + encode_uri_component(svg)

    def hills_box(self, frame: Frame) -> Frame:
        share = self.data["ridges"]["height"]["portrait" if frame.vertical else "landscape"]
        return Frame(_round(frame.width * 1.6), _round(frame.height * share))

    def drift(self, which: str) -> float:
        return self.data["ridges"]["drift"][which]


def style(theme: Theme, frame: Frame) -> str:
    """The stylesheet every card page shares."""
    c, v = theme.colors, frame.vertical
    display = theme.data["fonts"]["display"]["family"]
    text = theme.data["fonts"]["text"]["family"]
    weights = sorted(theme.data["fonts"]["display"]["files"], key=int)
    box = theme.hills_box(frame)
    hills_at = f"{box.width}px {box.height}px"
    glow = theme.data["glow"]
    glow_css = (
        f"radial-gradient(ellipse 50% 55% at {glow['portrait' if v else 'landscape']}, "
        f"{glow['color']}, transparent 70%)"
    )
    background = theme.data["background"]
    faces = "".join(
        f"@font-face {{ font-family: {display}; font-weight: {w}; src: url({theme.fonts[f'display-{w}']}); }}\n"
        for w in weights
    )
    return (
        "\n"
        + faces
        + f"@font-face {{ font-family: {text}; src: url({theme.fonts['text']}); }}\n"
        f"html, body {{ margin: 0; width: {frame.width}px; height: {frame.height}px; }}\n"
        "body { display: flex; flex-direction: column; justify-content: center;\n"
        f"\tpadding: 0 {90 if v else 160}px {120 if v else 60}px;\n"
        "\tbox-sizing: border-box;\n"
        "\tbackground:\n"
        f'\t\turl("{theme.ridge("near")}") left bottom / {hills_at} no-repeat,\n'
        f'\t\turl("{theme.ridge("far")}") left bottom / {hills_at} no-repeat,\n'
        f"\t\t{glow_css}, {background};\n"
        f"\tcolor: {c['text']}; font-family: {text}, sans-serif; }}\n"
        "/* The layers a card's video is put together from (parallax). */\n"
        "body.layer-text { background: transparent; }\n"
        f"body.layer-backdrop {{ background: {glow_css}, {background}; }}\n"
        f".ridge {{ width: {box.width}px; height: {box.height}px;\n"
        "\tbackground-size: 100% 100%; }\n"
        f"small {{ font-family: {display}, sans-serif; font-weight: {weights[0]}; font-size: {42 if v else 46}px; "
        f"letter-spacing: .1em; text-transform: uppercase; color: {c['muted']}; }}\n"
        f"h1 {{ font-family: {display}, sans-serif; font-weight: {weights[-1]}; font-size: {112 if v else 128}px; "
        "line-height: 1; margin: 24px 0 28px; text-transform: uppercase; letter-spacing: .01em;\n"
        "\ttext-shadow: 0 6px 28px rgba(0, 0, 0, .35); }\n"
        f"h1 em {{ color: {c['accent']}; font-style: normal; }}\n"
        f"p {{ font-size: {40 if v else 48}px; margin: 0; color: {c['muted']}; overflow-wrap: anywhere; }}\n"
        f"small.pill {{ align-self: flex-start; background: {c['accent']}; color: {c['ink']}; border-radius: 999px;\n"
        "\tpadding: 6px 26px 8px; letter-spacing: .08em; }\n"
        ".badges { display: flex; gap: 20px; margin-top: 48px; }\n"
        f".badge {{ font-family: {display}, sans-serif; font-weight: {weights[-1]}; font-size: 52px; line-height: 1;\n"
        f"\tpadding: 16px 30px; border-radius: 14px; background: {c['text']}; color: {c['ink']};\n"
        "\tbox-shadow: 0 10px 30px rgba(0, 0, 0, .25); }\n"
        f".badge.hot {{ background: {c['hot']}; color: {c['hotText']}; }}"
    )


def card(css: str, kicker: str, title: str, line: str, pill: bool = False, badges: Sequence = ()) -> str:
    """A card: the kicker above (an amber pill or plain), the title, the line, any badges."""
    row = (
        '<div class="badges">'
        + "".join(f'<span class="badge{" hot" if hot else ""}">{text}</span>' for text, hot in badges)
        + "</div>"
        if badges
        else ""
    )
    return (
        f"{DOCTYPE}<style>{css}</style>"
        f'<body><small class="{"pill" if pill else ""}">{kicker}</small><h1>{title}</h1>'
        f"<p>{line}</p>{row}</body>"
    )


def links_card(theme: Theme, css: str, frame: Frame, kicker: str, title: str, links: Sequence[Mapping]) -> str:
    """The closing card: one tile per address with what it is above it, the main one first."""
    c, v, n = theme.colors, frame.vertical, len(links)
    url_size = (72 if v else 88) if n == 1 else (54 if v else 46)
    display = theme.data["fonts"]["display"]["family"]
    columns = "1fr" if v else f"repeat({n}, 1fr)"
    single = ".links { justify-items: start; } .link { padding: 44px 56px 52px; }" if n == 1 else ""
    tiles = "".join(
        f'<div class="link{" main" if i == 0 else ""}"><div class="label">'
        f'<svg viewBox="0 0 24 24">{ICONS[link["icon"]]}</svg>{link["label"]}</div>'
        f'<div class="url">{link["url"].replace("/", "/<wbr>")}</div></div>'
        for i, link in enumerate(links)
    )
    return (
        f"{DOCTYPE}<style>{css}\n"
        f"\th1 {{ font-size: {104 if v else 112}px; margin: 20px 0 {56 if v else 64}px; }}\n"
        f"\t.links {{ display: grid; gap: {32 if v else 36}px;\n"
        f"\t\tgrid-template-columns: {columns}; }}\n"
        f"\t.link {{ background: {c['tile']}; border: 2px solid {c['tileBorder']};\n"
        f"\t\tborder-radius: 28px; padding: {'36px 40px' if v else '40px 40px 44px'}; }}\n"
        f"\t.link.main {{ background: {c['hot']}; border-color: {c['hot']}; }}\n"
        f"\t.label {{ display: flex; align-items: center; gap: 18px; font-size: {36 if v else 34}px;\n"
        f"\t\tcolor: {c['muted']}; margin-bottom: 18px; }}\n"
        f"\t.main .label {{ color: {c['mainLabel']}; }}\n"
        "\t.label svg { width: 48px; height: 48px; flex: none; fill: none; stroke: currentColor;\n"
        "\t\tstroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }\n"
        f"\t.url {{ font-family: {display}, sans-serif; font-size: {url_size}px; line-height: 1.15; "
        f"color: {c['text']}; overflow-wrap: anywhere; }}\n"
        f"\t{single}</style>"
        f'<body><small class="pill">{kicker}</small><h1>{title}</h1><div class="links">{tiles}</div></body>'
    )


def backdrop(css: str) -> str:
    """The layer behind every card's words: the background and its glow."""
    return f'{DOCTYPE}<style>{css}</style><body class="layer-backdrop"></body>'


def hills(theme: Theme, css: str, which: str) -> str:
    """One range of hills alone, for the parallax to slide."""
    return (
        f"{DOCTYPE}<style>{css}\n"
        "\t\thtml, body { background: transparent; width: auto; height: auto; padding: 0; }</style>"
        f"<body><div class=\"ridge\" style=\"background-image:url('{theme.ridge(which)}')\"></div></body>"
    )


def pages(
    theme: Theme,
    frame: Frame,
    words: Mapping,
    chapters: Sequence[Chapter],
    script: Mapping,
    language: str,
    clip_chapter: int | None = None,
) -> dict[str, str]:
    """Every page a video's cards are drawn from, by layer name: `card-<n>` for each card in
    order (the opening, one per chapter, the closing, and a clip's own two), then the backdrop and
    the two ranges of hills."""
    css = style(theme, frame)
    cards = [
        card(
            css,
            words.get("openKicker", words["what"]),
            words.get("openTitle", words["brand"]),
            words["line"],
            badges=words.get("badges", []),
        ),
        *(
            card(
                css,
                f"{words['chapter']} {ch.number}",
                chapter_title(script, ch, language),
                words["store"],
                pill=True,
            )
            for ch in chapters
        ),
        links_card(theme, css, frame, words["tryIt"], words["tryTitle"], words["tryLinks"]),
    ]
    if clip_chapter is not None:
        ch = chapters[clip_chapter - 1]
        cards += [
            card(css, words["brand"], chapter_title(script, ch, language), words["what"]),
            links_card(theme, css, frame, words["fullIt"], words["fullTitle"], words["tryLinks"]),
        ]
    out = {f"card-{i}": html for i, html in enumerate(cards)}
    out["card-backdrop"] = backdrop(css)
    out["card-hills-far"] = hills(theme, css, "far")
    out["card-hills-near"] = hills(theme, css, "near")
    return out


def parallax_args(
    theme: Theme, frame: Frame, layer, index: int, length: float, file: str, codec: Sequence[str]
) -> list[str]:
    """A card as a parallax video: the backdrop still, the far hills sliding slowly, the near ones
    faster, the words still over them; its first frame is the card's still."""
    box = theme.hills_box(frame)
    held = ["-loop", "1", "-t", f"{length:.3f}", "-i"]

    def slide(speed: float) -> str:
        return f"x='-min(t*{speed:g},{box.width - frame.width})':y={frame.height - box.height}"

    return [
        *held, layer("card-backdrop"),
        *held, layer("card-hills-far"),
        *held, layer("card-hills-near"),
        *held, layer(f"card-{index}-text"),
        "-filter_complex",
        f"[0:v][1:v]overlay={slide(theme.drift('far'))}:shortest=1[a];"
        f"[a][2:v]overlay={slide(theme.drift('near'))}:shortest=1[b];"
        "[b][3:v]overlay=0:0:shortest=1,fps=30,format=yuv420p[v]",
        "-map", "[v]",
        *codec,
        "-an",
        file,
    ]

