"""urdido.cards builds, byte for byte, the card pages story-video.mjs draws (VM6).

The golden pages are `expected/<variant>/cards/*.html`, written by the JS build with each inlined
font named `<font:file>`; the theme here inlines the same placeholder, so the comparison is of
everything but the font bytes, which the theme names by the same files.
"""

import json
import os
from pathlib import Path

import pytest

from fonts import card_theme
from urdido.cards import html

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




@pytest.fixture(scope="module")
def theme(tmp_path_factory):
    """A theme on generated fonts, for what does not compare with a golden (UR31)."""
    pytest.importorskip("fontTools")
    made, _ = card_theme(tmp_path_factory.mktemp("fonts"))
    return html.Theme.load(made, {}, font=named_font)




def test_ridge_is_encoded_as_encode_uri_component(theme):
    ridge = theme.ridge("near")
    assert ridge.startswith("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org")
    assert "'" not in ridge.split(",", 1)[1].replace("%27", "")


def test_parallax_slides_each_range_at_its_speed(theme):
    frame = html.Frame(1920, 1080)
    args = html.parallax_args(theme, frame, lambda n: f"{n}.png", 3, 2.5, "card-3.mp4", ["-c:v", "libx264"])
    graph = args[args.index("-filter_complex") + 1]
    assert "overlay=x='-min(t*24,1152)':y=713" in graph
    assert "overlay=x='-min(t*64,1152)':y=713" in graph
    assert args[-1] == "card-3.mp4"
    assert "card-3-text.png" in args


def _png_size(file: Path) -> tuple[int, int]:
    head = file.read_bytes()[16:24]
    return int.from_bytes(head[:4], "big"), int.from_bytes(head[4:], "big")




def test_a_card_renders_in_a_generated_theme(tmp_path):
    pytest.importorskip("fontTools")
    pytest.importorskip("playwright.sync_api")
    from urdido.cards.render import render

    made, words = card_theme(tmp_path / "fonts")
    theme = html.Theme.load(made, {})
    frame = html.Frame(1920, 1080)
    css = html.style(theme, frame)
    page = html.card(css, f"{words['chapter']} 1", "One command", words["store"], pill=True)
    assert "One command" in page and "Urdido Test Display" in page
    files = render({"card-1": page, "card-backdrop": html.backdrop(css)}, frame, str(tmp_path / "out"))
    assert [Path(f).name for f in files] == ["card-1.png", "card-1-text.png", "card-backdrop.png"]
    assert _png_size(tmp_path / "out" / "card-1.png") == (1920, 1080)






def test_a_path_at_an_undeclared_root_is_refused_by_name():
    from urdido.cards.html import resolve
    from urdido.errors import DeclarationError

    assert resolve("<plugin>/demo/fonts", {"plugin": "/p"}).replace("\\", "/") == "/p/demo/fonts"
    with pytest.raises(DeclarationError, match="starts at <turing>, which the declaration"):
        resolve("<turing>/demo/fonts", {"plugin": "/p"})
