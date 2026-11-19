"""urdido.cards builds, byte for byte, the card pages story-video.mjs draws (VM6).

The golden pages are `expected/<variant>/cards/*.html`, written by the JS build with each inlined
font named `<font:file>`; the theme here inlines the same placeholder, so the comparison is of
everything but the font bytes, which the theme names by the same files.
"""

import json
import os
from pathlib import Path

import pytest

from urdido import captions
from urdido.cards import html
from golden_plans import main_plan
from marketing import GOLDEN, MARKETING, module_needs_marketing

module_needs_marketing()

WORDPRESS = MARKETING / "turing" / "wordpress"
NARRATION = WORDPRESS / "demo" / "narration"

VARIANTS = {
    "story-en": ("story", "story", "script.json"),
    "story-pt-BR": ("story", "story", "script.json"),
    "developer": ("developer", "developer", "developer.json"),
    "chapter-2": ("story", "story", "script.json"),
    "vertical-chapter-2": ("story", "story-vertical", "script.json"),
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def named_font(path: str) -> str:
    return f"<font:{os.path.basename(path)}>"


DECLARATION = load(WORDPRESS / "demo" / "cards.json")
THEME = html.Theme.load(DECLARATION["theme"], {"turing": "turing"}, font=named_font)


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_pages_equal_the_js_cards(variant):
    story, fixture, script_file = VARIANTS[variant]
    folder = GOLDEN / "expected" / variant
    expected = {f.stem: f.read_bytes().decode("utf-8") for f in (folder / "cards").glob("*.html")}
    assert expected, f"no golden cards for {variant}: run the golden check with --update"
    plan = load(main_plan(folder))
    frame = html.Frame(plan["size"]["width"], plan["size"]["height"])
    words = DECLARATION["words"][story][plan["language"]]
    chapters = captions.chapters_of(load(GOLDEN / "fixtures" / f"{fixture}.json"))

    built = html.pages(
        THEME, frame, words, chapters, load(NARRATION / script_file), plan["language"],
        clip_chapter=plan.get("chapter"),
    )
    assert sorted(built) == sorted(expected)
    for name, page in expected.items():
        assert built[name] == page, name


def test_ridge_is_encoded_as_encode_uri_component():
    ridge = THEME.ridge("near")
    assert ridge.startswith("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org")
    assert "'" not in ridge.split(",", 1)[1].replace("%27", "")


def test_parallax_slides_each_range_at_its_speed():
    frame = html.Frame(1920, 1080)
    args = html.parallax_args(THEME, frame, lambda n: f"{n}.png", 3, 2.5, "card-3.mp4", ["-c:v", "libx264"])
    graph = args[args.index("-filter_complex") + 1]
    assert "overlay=x='-min(t*24,1152)':y=713" in graph
    assert "overlay=x='-min(t*64,1152)':y=713" in graph
    assert args[-1] == "card-3.mp4"
    assert "card-3-text.png" in args


SHIO = Path(os.environ.get("SHIO_REPO", r"D:\Git\viglet\shio\latest"))
SHIO_CARDS = MARKETING / "shio" / "promo" / "demo" / "cards.json"
SHIO_SCRIPT = MARKETING / "shio" / "promo" / "demo" / "narration" / "script.json"


def _png_size(file: Path) -> tuple[int, int]:
    head = file.read_bytes()[16:24]
    return int.from_bytes(head[:4], "big"), int.from_bytes(head[4:], "big")


@pytest.mark.skipif(
    not (SHIO / "marketplace" / "quilhara" / "assets" / "fonts").exists(),
    reason="the Viglet Shio repository (its Quilhara fonts) is not on this machine",
)
def test_a_viglet_shio_card_renders_in_its_theme(tmp_path):
    from urdido.cards.render import render

    declaration = load(SHIO_CARDS)
    theme = html.Theme.load(declaration["theme"], {"shio": str(SHIO)})
    frame = html.Frame(1920, 1080)
    script = load(SHIO_SCRIPT)
    words = declaration["words"]["pt-BR"]
    chapter = captions.Chapter("1", "One command")
    css = html.style(theme, frame)
    page = html.card(
        css, f"{words['chapter']} 1", captions.chapter_title(script, chapter, "pt-BR"), words["store"], pill=True
    )
    # the purples of Viglet Shio's logo since 2026-11-17, Quilhara's fonts
    assert "Fraunces" in page and "#3B1A78" in page and "Um comando" in page
    assert "Barlow" not in page and "Tarnfell" not in page

    try:
        files = render({"card-1": page, "card-backdrop": html.backdrop(css)}, frame, str(tmp_path))
    except Exception as error:  # no browser channel on this machine
        pytest.skip(f"Playwright could not draw: {error}")
    assert [Path(f).name for f in files] == ["card-1.png", "card-1-text.png", "card-backdrop.png"]
    assert _png_size(tmp_path / "card-1.png") == (1920, 1080)
    # the words alone weigh less than the card over its backdrop
    assert (tmp_path / "card-1-text.png").stat().st_size < (tmp_path / "card-1.png").stat().st_size


# The JS build's own card pictures, which the golden check leaves in its work folder.
GOLDEN_WORK = Path(os.environ.get("URDIDO_GOLDEN_WORK", Path(os.environ.get("TEMP", "/tmp")) / "video-maker-golden"))
TURING_WORDPRESS = Path(os.environ.get("TURING_WORDPRESS", r"D:\Git\viglet\turing\latest\wordpress"))


def _differing_share(a: Path, b: Path) -> float:
    """The share of pixels where any channel differs by more than 24 of 255."""
    from PIL import Image, ImageChops

    x, y = Image.open(a).convert("RGBA"), Image.open(b).convert("RGBA")
    assert x.size == y.size, f"{a.name}: {x.size} != {y.size}"
    diff = ImageChops.difference(x, y).point(lambda v: 255 if v > 24 else 0)
    mask = diff.convert("L").point(lambda v: 255 if v else 0)
    return mask.histogram()[255] / (x.size[0] * x.size[1])


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_pictures_match_the_js_cards(variant, tmp_path):
    pytest.importorskip("PIL")
    js_parts = GOLDEN_WORK / variant / "video" / "parts"
    if not (js_parts / "card-0.png").exists() or not TURING_WORDPRESS.exists():
        pytest.skip("run the golden check first: its work folder holds the JS cards' pictures")
    from urdido.cards.render import render

    story, fixture, script_file = VARIANTS[variant]
    plan = load(main_plan(GOLDEN / "expected" / variant))
    frame = html.Frame(plan["size"]["width"], plan["size"]["height"])
    theme = html.Theme.load(DECLARATION["theme"], {"turing": str(TURING_WORDPRESS)})
    pages = html.pages(
        theme, frame, DECLARATION["words"][story][plan["language"]],
        captions.chapters_of(load(GOLDEN / "fixtures" / f"{fixture}.json")),
        load(NARRATION / script_file), plan["language"], clip_chapter=plan.get("chapter"),
    )
    try:
        files = render(pages, frame, str(tmp_path))
    except Exception as error:  # no browser channel on this machine
        pytest.skip(f"Playwright could not draw: {error}")
    worst = max((_differing_share(Path(f), js_parts / Path(f).name), Path(f).name) for f in files)
    # Two browsers may anti-alias a few glyph edges apart; a layout or colour change moves far more.
    assert worst[0] < 0.005, worst
