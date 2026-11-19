"""The brand mark a video carries in a corner (`[mark]` in video.toml)."""

from pathlib import Path

import pytest

from urdido import mark

SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#7C3AED"/></svg>'


@pytest.fixture
def logo(tmp_path: Path) -> Path:
    file = tmp_path / "logo.svg"
    file.write_text(SVG, encoding="utf-8")
    return file


def resolve(tmp_path: Path):
    return lambda declared: str(tmp_path / declared)


def test_defaults_sit_where_the_japode_header_sits(tmp_path, logo):
    m = mark.declared({"logo": "logo.svg", "text": "Viglet Shio"}, resolve(tmp_path))
    assert (m.corner, m.margin, m.size) == ("top-left", (70, 50), 44)
    # the logo lands on the margin: the drawn padding (0.3 of the logo) is taken back
    assert mark.position(m, 1080) == ("57", "37")


def test_other_corners_count_from_the_far_sides(tmp_path, logo):
    m = mark.declared({"logo": "logo.svg", "corner": "bottom-right", "margin": [40, 30], "size": 40}, resolve(tmp_path))
    assert mark.position(m, 1080) == ("W-w-28", "H-h-18")


def test_a_smaller_frame_scales_the_margin(tmp_path, logo):
    m = mark.declared({"logo": "logo.svg"}, resolve(tmp_path))
    assert mark.position(m, 720) == ("38", "24")


@pytest.mark.parametrize("decl, words", [
    ({}, "needs logo"),
    ({"logo": "missing.svg"}, "existing svg or png"),
    ({"logo": "logo.svg", "corner": "middle"}, "corner must be"),
    ({"logo": "logo.svg", "margin": [70]}, "margin must be"),
    ({"logo": "logo.svg", "size": 4}, "size must be"),
    ({"logo": "logo.svg", "opacity": 0}, "opacity must be"),
    ({"logo": "logo.svg", "colour": "red"}, "does not take colour"),
    ({"logo": "logo.svg", "font": "none.woff2"}, "does not exist"),
])
def test_a_value_the_build_cannot_honour_refuses(tmp_path, logo, decl, words):
    with pytest.raises(SystemExit, match=words):
        mark.declared(decl, resolve(tmp_path))


def test_the_page_carries_the_logo_and_the_escaped_text(tmp_path, logo):
    m = mark.declared({"logo": "logo.svg", "text": "A & B"}, resolve(tmp_path))
    html = mark.page(m, 1.0)
    assert "data:image/svg+xml;base64," in html
    assert "<b>A &amp; B</b>" in html


def test_no_text_draws_the_logo_alone(tmp_path, logo):
    m = mark.declared({"logo": "logo.svg", "text": ""}, resolve(tmp_path))
    assert "<b>" not in mark.page(m, 1.0)


def test_a_background_draws_a_rounded_plate(tmp_path, logo):
    m = mark.declared({"logo": "logo.svg", "background": "rgba(0,0,0,.55)"}, resolve(tmp_path))
    assert "background: rgba(0,0,0,.55); border-radius:" in mark.page(m, 1.0)
    assert "border-radius" not in mark.page(mark.declared({"logo": "logo.svg"}, resolve(tmp_path)), 1.0)


def test_a_background_is_one_colour_not_more_css(tmp_path, logo):
    with pytest.raises(SystemExit, match="one CSS colour"):
        mark.declared({"logo": "logo.svg", "background": "red; display:none"}, resolve(tmp_path))
