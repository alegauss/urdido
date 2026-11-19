"""VM61: malformed text, missing glyphs and actual protected-token line breaks."""
import json
import os
from pathlib import Path

import pytest

from urdido import cache, textcheck
from urdido.cards.html import Frame, Theme
from urdido.cards.render import render
from urdido.sources.model import RecordingRefused
from test_preflight import cut


def test_bad_accents_are_reported_but_questions_and_url_query_strings_stay_valid():
    assert textcheck.corruption("Uma hist?ria")
    assert textcheck.corruption("Uma hist\ufffdria")
    assert textcheck.corruption("histÃ³ria")
    assert textcheck.corruption("Sério? Você já usou WordPress? https://example.org/path?value=x") == []
    assert textcheck.corruption("Café, música — não?") == []


def test_missing_glyph_and_corrupted_text_fail_before_any_renderer_or_encoder(cut):
    from urdido.build import main
    from urdido.preflight import PreflightRefused

    cut.story["scenes"]["outro"][0].update(caption="Uma hist?ria", text="漢")
    cut.write("story.json", cut.story)
    with pytest.raises(PreflightRefused) as failure:
        main([str(cut.declaration), "--language", "en"])
    assert any(f["field"] == "scenes.outro.0.caption" and "question mark" in f["message"] for f in failure.value.findings)
    assert any("U+6F22" in f["message"] for f in failure.value.findings)
    assert not (cut.folder / "video/parts/illustrated").exists()


def test_font_coverage_uses_the_declared_font_not_a_guessed_fallback(cut):
    cards = json.loads((cut.folder / "cards.json").read_text())
    theme = Theme.load(cards["theme"], {"root": str(cut.folder)})
    found = textcheck.inputs(cut.story, cut.script, "en", theme, textcheck.Policy("error"))
    assert found == []
    cut.story["scenes"]["outro"][0]["caption"] = "漢"
    found = textcheck.inputs(cut.story, cut.script, "en", theme, textcheck.Policy("error"))
    assert next(f["font_role"] for f in found if f["rule"] == "glyph") == "display-800"


def test_font_coverage_observes_the_renderer_uppercase_kicker(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(textcheck, "glyphs", lambda url: {ord(c) for c in "FÓO"})
    document = {"brand_mark": "none", "scenes": {"intro": [{"title": "semantic", "caption": "", "kicker": "fóo", "source": "own"}]}, "sources": {"own": {}}}
    theme = SimpleNamespace(fonts={"display-800": "fixture", "text": "fixture"})
    assert textcheck.inputs(document, {}, "en", theme, textcheck.Policy("error")) == []


def test_wordpress_wrap_fails_with_exact_field_and_preview_before_production_png(tmp_path):
    pytest.importorskip("playwright.sync_api")
    page = '<style>h1{font:48px/1.3 Arial;width:100px;overflow-wrap:anywhere}</style><h1>WordPress</h1>'
    with textcheck.configured({"protected_tokens": ["WordPress"]}):
        with pytest.raises(RecordingRefused, match="protected token"):
            render({"card": page}, Frame(400, 300), str(tmp_path))
    report = json.loads((tmp_path / "text-checks.json").read_text("utf-8"))
    issue = next(f for f in report["findings"] if f["rule"] == "protected_break")
    assert issue["field"] == "h1" and issue["token"] == "WordPress"
    assert Path(issue["preview"]).is_file()
    assert not (tmp_path / "card.png").exists()


def test_clipping_is_measured_at_multiple_target_sizes_and_hidden_text_is_ignored(tmp_path):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(channel=os.environ.get("E2E_CHANNEL", "msedge"))
        try:
            for width, height in ((320, 180), (640, 360)):
                page = browser.new_page(viewport={"width": width, "height": height})
                page.set_content('<style>h1{width:90px;height:20px;overflow:auto;white-space:nowrap;font:40px Arial}</style>'
                                 '<h1>Overflow</h1><p style="display:none">WordPress</p><div style="opacity:0"><p>WordPress</p></div>')
                with textcheck.configured({"protected_tokens": ["WordPress"]}):
                    findings = textcheck.measure(page, Frame(width, height), "card", "full")
                assert any(f["rule"] == "clipping" for f in findings)
                assert all(f["text"] != "WordPress" for f in findings)
                page.close()
        finally:
            browser.close()


def test_warned_layout_report_survives_cache_hits_and_keeps_a_real_preview(tmp_path, monkeypatch):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import BrowserType

    content = '<style>h1{font:48px/1.3 Arial;width:100px;overflow-wrap:anywhere}</style><h1>WordPress</h1>'
    with textcheck.configured({"action": "warn", "protected_tokens": ["WordPress"]}):
        with pytest.warns(UserWarning, match="text checks"):
            with cache.configured(tmp_path / "cache.json"):
                render({"card": content}, Frame(400, 300), str(tmp_path))
        for preview in (tmp_path / "text-check").glob("*.png"):
            preview.write_bytes(b"tampered diagnostic")
        with monkeypatch.context() as cached:
            cached.setattr(BrowserType, "launch", lambda *a, **k: pytest.fail("unchanged layout launched a browser"))
            with pytest.warns(UserWarning, match="text checks"):
                with cache.configured(tmp_path / "cache.json") as session:
                    render({"card": content}, Frame(400, 300), str(tmp_path))
        assert all(e["hit"] for e in session.events)
    report = json.loads((tmp_path / "text-checks.json").read_text("utf-8"))
    assert all(Path(f["preview"]).is_file() for f in report["findings"])
    assert all(cache.file_hash(f["preview"]) == f["preview_sha256"] for f in report["findings"])


def test_illustrated_cards_command_checks_all_layers_without_video_encoding(cut):
    from urdido.build import main

    with pytest.warns(UserWarning, match="caption safe area"):
        assert main([str(cut.declaration), "--language", "en", "--cards"]) == 0
    folder = cut.folder / "video/parts/illustrated"
    assert (folder / "intro-0.png").exists() and (folder / "intro-0-text.png").exists()
    assert not list(folder.glob("*.mp4"))
    assert json.loads((folder / "text-checks.json").read_text())["findings"] == []


def test_corrupted_translation_is_reported_with_its_file_and_field(cut):
    from urdido.build import main
    from urdido.preflight import PreflightRefused

    cut.write("translations.json", {"intro": ["Uma hist?ria"], "outro": ["Tchau"]})
    with pytest.raises(PreflightRefused) as failure:
        main([str(cut.declaration), "--language", "en", "--plan"])
    assert any(f["field"] == "captions.translations.pt.intro.0" and f["file"].endswith("translations.json")
               for f in failure.value.findings)
