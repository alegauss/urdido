"""A thumbnail's pictures are crops of the video's own sources, declared by box (VM51)."""
import pytest

from urdido.thumbnail import crop_filter
from urdido.thumbnail import fit_title


def test_a_box_of_fractions_becomes_an_ffmpeg_crop():
    assert crop_filter([0.25, 0.0, 0.75, 0.5]) == "crop=iw*0.5000:ih*0.5000:iw*0.2500:ih*0.0000"


def test_a_box_outside_the_frame_is_refused():
    with pytest.raises(ValueError, match="between 0 and 1"):
        crop_filter([0.5, 0.0, 0.4, 1.0])


def rules(findings, severity="refuse"):
    return {row["rule"] for row in findings if row["severity"] == severity}


def test_the_scion_pair_is_refused_for_repeating_and_running_long_ur1():
    from urdido.thumbnail import check_pair

    title = "30 mil merges por dia: o Git não aguentou e a Anthropic reescreveu tudo"
    words = {"top": "O Git não aguentou", "bottom": "30 mil merges por dia", "title_size": 104}
    found = check_pair(title, words, "pt-BR")
    assert rules(found) == {"title.length", "pair.repeats"}
    repeats = next(row for row in found if row["rule"] == "pair.repeats")["message"]
    for word in ("30", "git", "aguentou", "merges", "dia"):
        assert word in repeats
    assert "nao" not in repeats and " por" not in repeats


def test_a_pair_that_adds_what_the_title_leaves_out_passes_ur1():
    from urdido.thumbnail import check_pair

    found = check_pair("Como a Anthropic trocou o Git", {"top": "30 mil por dia", "accent": 1}, "pt-BR")
    assert rules(found) == set()
    assert rules(found, "advise") == {"thumbnail.words"}


def test_a_vague_shouting_title_is_refused_ur1():
    from urdido.thumbnail import check_pair

    found = check_pair("um resultado INCRÍVEL que NINGUÉM VIU AINDA", {}, "pt-BR")
    assert rules(found) == {"title.concrete", "title.capitals", "title.superlative"}
    assert rules(check_pair("the ultimate guide to docker", {}, "en")) == {"title.concrete", "title.superlative"}


def test_a_feed_length_title_is_advised_not_refused_ur1():
    from urdido.thumbnail import check_pair

    found = check_pair("Docker em 2026: o que mudou para quem roda servidores", {}, "pt-BR")
    assert rules(found) == set() and rules(found, "advise") == {"title.feed"}


def test_declared_words_and_drawn_fields_steer_the_check_ur1():
    from urdido.thumbnail import check_pair

    spec = {"stopwords": ["docker"], "drawn": ["top"]}
    found = check_pair("Docker em 2026 sem servidor", {"top": "docker 2027", "accent": "servidor"}, "pt-BR", spec)
    assert rules(found) == set()
    with pytest.raises(ValueError, match="drawn"):
        check_pair("Docker em 2026", {}, "pt-BR", {"drawn": "top"})


def test_the_cli_check_refuses_before_drawing_and_says_an_undeclared_title_is_unchecked(tmp_path, capsys):
    from urdido.thumbnail import main

    toml = tmp_path / "video.toml"
    toml.write_text('[thumbnail]\nlayout = "missing.py"\n[thumbnail.words.pt-BR]\ntop = "O Git parou"\n'
                    '[thumbnail.title]\npt-BR = "O Git parou em 2026"\n', encoding="utf-8")
    assert main([str(toml), "--language", "pt-BR", "--check"]) == 1
    assert "pair.repeats" in capsys.readouterr().err
    toml.write_text('[thumbnail]\nlayout = "missing.py"\n[thumbnail.words.pt-BR]\ntop = "30 mil por dia"\n',
                    encoding="utf-8")
    assert main([str(toml), "--language", "pt-BR", "--check"]) == 0
    assert "unchecked" in capsys.readouterr().err


def test_translated_title_fits_both_lines_away_from_subject_vm54():
    import os

    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch(channel=os.environ.get("E2E_CHANNEL", "msedge"))
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.set_content('<style>h1{position:absolute;right:44px;top:34px;font: bold 104px/.98 Arial;white-space:nowrap}'
                             'em{display:block;font-style:normal}</style><h1>1 COMMENT<em>39% OF THE WEB</em></h1>')
            report = fit_title(page, (520, 0, 1236, 280), max_size=104)
            assert 64 <= report["font_size"] < 104
            assert len(report["lines"]) == 2
            assert all(line["x"] >= 520 and line["x"] + line["width"] <= 1236 for line in report["lines"])
            page.locator("em").evaluate("el => el.textContent = 'W'.repeat(100)")
            with pytest.raises(ValueError, match="subject-free column"):
                fit_title(page, (520, 0, 1236, 280), max_size=104)
        finally:
            browser.close()
