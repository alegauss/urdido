"""The opening's site screens are declared, not selectors in the code (UR28)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from urdido.build import Build
from urdido.errors import DeclarationError

SOURCE = Path(__file__).resolve().parents[1] / "src" / "urdido"


def build(tmp_path, monkeypatch):
    monkeypatch.delenv("STORE_URL", raising=False)
    toml = tmp_path / "video.toml"
    toml.write_text(
        '[video]\nname = "demo"\nlanguages = { en = "eng" }\n', encoding="utf-8"
    )
    args = SimpleNamespace(
        language="en", cut="full", vertical=False, refresh_screens=False
    )
    return Build(toml, args)


def test_kept_screens_are_reused_without_a_sequence(tmp_path, monkeypatch):
    made = build(tmp_path, monkeypatch)
    kept = made.out / "screens" / "en"
    kept.mkdir(parents=True)
    (kept / "screen-0.png").write_bytes(b"png")
    assert made.screens({"store": {"en": "http://shop.test"}}) == [
        str(kept / "screen-0.png")
    ]


def test_a_store_without_declared_screens_is_refused(tmp_path, monkeypatch):
    made = build(tmp_path, monkeypatch)
    with pytest.raises(DeclarationError, match=r"declare \[opening\] screens"):
        made.screens({"store": {"en": "http://shop.test"}})
    bad = {
        "store": {"en": "http://shop.test"},
        "screens": [{"path": "/", "follow": "a"}],
    }
    with pytest.raises(DeclarationError, match="a path .* or a follow selector"):
        made.screens(bad)


def test_no_module_names_a_shop_plugin_or_its_selectors():
    for file in SOURCE.rglob("*.py"):
        text = file.read_text(encoding="utf-8").lower()
        for word in ("woocommerce", "post_type=product", "/produto/"):
            assert word not in text, (file.name, word)
