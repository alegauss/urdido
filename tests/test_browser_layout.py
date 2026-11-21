"""Cards draw with Playwright's Chromium unless a channel is declared, and thumbnail
layouts load by contract (UR29)."""

import sys
from pathlib import Path

import pytest

from urdido.cards import render
from urdido.thumbnail import layout

SOURCE = Path(__file__).resolve().parents[1] / "src" / "urdido"


def test_no_channel_means_playwrights_own_chromium(monkeypatch):
    monkeypatch.delenv("E2E_CHANNEL", raising=False)
    assert render.browser_channel() is None
    monkeypatch.setenv("E2E_CHANNEL", "chrome")
    assert render.browser_channel() == "chrome"
    token = render.DECLARED.set("msedge")
    try:
        assert (
            render.browser_channel() == "msedge"
        )  # the declaration's, over the environment
        assert render.browser_channel("chrome") == "chrome"  # the caller's, over both
    finally:
        render.DECLARED.reset(token)


def test_no_module_defaults_to_edge():
    for file in SOURCE.rglob("*.py"):
        text = file.read_text(encoding="utf-8")
        assert '"E2E_CHANNEL", "msedge"' not in text, file.name


def test_a_layout_loads_as_a_module_function_or_a_path(tmp_path, monkeypatch):
    package = tmp_path / "brandpkg"
    package.mkdir()
    (package / "__init__.py").write_text(
        "def thumbnail(**fields):\n    return fields['out']\n"
        "def wide(**fields):\n    return 'wide'\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    assert layout("brandpkg")(out="a.jpg") == "a.jpg"
    assert layout("brandpkg:wide")(out="a.jpg") == "wide"
    (tmp_path / "brand.py").write_text(
        "def thumbnail(**f):\n    return 'file'\n", encoding="utf-8"
    )
    assert layout("./brand.py", tmp_path)(out="x") == "file"
    with pytest.raises(ValueError, match="no entry point"):
        layout("no_such_layout_module")
    with pytest.raises(ValueError, match="has no missing"):
        layout("brandpkg:missing")
    sys.modules.pop("brandpkg", None)
