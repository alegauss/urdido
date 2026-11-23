"""VM52: platform budgets never silently delete attribution obligations."""
from pathlib import Path

import pytest

from urdido.publish.description import (
    format_description,
    illustrated,
    short_url,
    write,
)


def test_an_english_build_writes_an_english_description_ur27():
    from urdido.publish.strings import strings

    document = {
        "description": "WordPress in five minutes.",
        "credits": "Thanks.",
        "scenes": {"intro": [{"asset": "own", "source": "site"}, {"asset": "old", "source": "site"}]},
        "media": {"own": {"file": "a.webm", "license": "Own recording", "url": "https://wp.test/x",
                          "author": "Us", "title": "Capture"},
                  "old": {"file": "b.png", "license": "Public domain; scanned", "url": "https://archive.test/b",
                          "author": "Someone", "title": "Old photo"}},
        "sources": {"site": {"label": "WordPress", "url": "https://wordpress.org"}},
    }
    text, _ = illustrated(document, ["0:00 Introduction", "0:30 Install"], {}, "en")
    for english in ("Chapters", "Sources and demonstrations", "Own captures", "Images — Public domain",
                    "Narration and music generated with ElevenLabs."):
        assert english in text, english
    for portuguese in ("Capítulos", "Fontes", "Capturas", "Imagens", "Domínio", "Narração"):
        assert portuguese not in text, portuguese
    pt, _ = illustrated(document, [], {}, "pt-BR")
    assert "Capítulos" in pt and "Capturas próprias" in pt and "Domínio público" in pt
    assert strings("pt-BR", {"chapters": "Capítulos do vídeo"})["chapters"] == "Capítulos do vídeo"
    with pytest.raises(ValueError, match="has no chaptres"):
        strings("en", {"chaptres": "x"})


def test_no_portuguese_literal_outside_the_pt_table_ur27():
    import re

    source = Path(__file__).resolve().parents[1] / "src" / "urdido"
    for file in (source / "publish" / "description.py", source / "sources" / "illustrated.py"):
        text = file.read_text(encoding="utf-8")
        for word in ("Capítulos", "Introdução", "Fontes e demonstrações", "Apoio", "Capturas próprias",
                     "Imagens", "Trecho", "Domínio público", "Direitos reservados", "Narração"):
            assert not re.search(re.escape(word), text), (file.name, word)


def test_the_target_owns_the_limit_and_the_refused_characters_ur27():
    from urdido.publish.strings import Target

    tiny = Target("Tiny", 40, ("#",))
    with pytest.raises(ValueError, match="limit 40"):
        format_description("x" * 50, [], [], target=tiny)
    with pytest.raises(ValueError, match="# , which Tiny|#, which Tiny"):
        format_description("a #tag", [], [], target=tiny)
    assert short_url("https://www.youtube.com/watch?v=abc", tiny) == "https://www.youtube.com/watch?v=abc"


def test_required_notice_and_changes_survive_grouping_vm52():
    credit = {"title": "Full work title", "author": "Creator", "url": "https://www.youtube.com/watch?v=abc&t=30",
              "license": "CC BY 3.0", "license_url": "https://creativecommons.org/licenses/by/3.0/",
              "copyright": "Copyright Creator", "notice": "Notice one", "disclaimer": "Declared disclaimer", "changes": "Cropped."}
    text = format_description("Summary", [], [credit, {**credit, "notice": "Notice two"}])
    assert all(value in text for value in ("Full work title", "Creator", "Copyright Creator", "Notice one", "Notice two", "Declared disclaimer", "Cropped."))
    assert "https://youtu.be/abc?t=30" in text
    assert text.count(credit["license_url"]) == 1


def test_missing_licence_and_overflow_are_refused_without_overwrite_vm52(tmp_path):
    credit = {"title": "A", "author": "B", "url": "https://example.test", "license": "CC BY"}
    with pytest.raises(ValueError, match="no version is inferred"):
        format_description("Summary", [], [credit])
    with pytest.raises(ValueError, match="limit 5000"):
        format_description("Summary", [], [{**credit, "license_url": "https://example.test/license", "title": "X" * 5001}])
    file = tmp_path / "v.description.txt"
    file.write_text("Last good copy", encoding="utf-8")
    with pytest.raises(ValueError):
        write(tmp_path, "v", "X" * 5001, {})
    assert file.read_text() == "Last good copy"


def test_short_url_preserves_time_and_emoji_budget_is_conservative_vm52():
    assert short_url("https://www.youtube.com/watch?v=abc&t=12#fragment") == "https://youtu.be/abc?t=12#fragment"
    assert short_url("https://example.test/watch?v=abc") == "https://example.test/watch?v=abc"
    with pytest.raises(ValueError, match="limit"):
        format_description("😀" * 2500, [], [])


def test_grouping_cannot_discard_explicit_attribution_obligations_vm52():
    credit = {"title": "Protected stock", "author": "Creator", "url": "https://pixabay.com/videos/id-1/",
              "license": "Pixabay Content License", "kind": "pixabay", "attribution_required": True,
              "license_url": "https://pixabay.com/service/license-summary/"}
    text = format_description("Summary", [], [credit])
    assert credit["title"] in text and credit["author"] in text and credit["url"] in text
    cc = {**credit, "kind": "own", "attribution_required": False, "license": "CC BY 3.0",
          "license_url": "https://creativecommons.org/licenses/by/3.0/"}
    assert cc["title"] in format_description("Summary", [], [cc])


SCRIPT = {
    "introTitle": {"pt-BR": "Abertura"},
    "chapters": {"1": {"title": {"pt-BR": "Instalar"}}, "2": {"title": {"pt-BR": "Buscar"}}},
}


def test_scene_chapters_are_dated_by_their_own_take_not_their_position_ur9():
    from urdido.publish.description import chapter_lines

    spoken = [
        {"file": "takes/pt-BR/intro.mp3", "at": 0.0},
        {"file": "takes/pt-BR/chapter-1.mp3", "at": 12.6},
        {"file": "takes/pt-BR/tempo-1.1/chapter-2.mp3", "at": 75.3},
        {"file": "takes/pt-BR/chapter-2-result.mp3", "at": 90.0},
    ]
    assert chapter_lines(SCRIPT, spoken, "pt-BR") == ["0:00 Abertura", "0:12 Instalar", "1:14 Buscar"]
    with pytest.raises(ValueError, match="chapter-2 is not heard"):
        chapter_lines(SCRIPT, spoken[:2], "pt-BR")


def test_a_scenes_video_writes_its_description_from_the_declaration_ur9():
    from urdido.publish.description import scenes

    plan = {"spoken": {"pt-BR": [{"file": "chapter-1.mp3", "at": 5.0}, {"file": "chapter-2.mp3", "at": 61.0}]}}
    options = {"summary": "O Shio em três minutos.", "notes": "Mais em shio.dev",
               "sources": [{"label": "Shio", "url": "https://github.com/openviglet/shio"}]}
    text, record = scenes(SCRIPT, plan, "pt-BR", options)
    assert text.startswith("O Shio em três minutos.\n")
    assert "0:04 Instalar\n1:00 Buscar" in text
    assert "Shio: https://github.com/openviglet/shio" in text and "Mais em shio.dev" in text
    assert record["chapters"][0] == "0:00 Abertura"
    with pytest.raises(ValueError, match="summary"):
        scenes(SCRIPT, plan, "pt-BR", {})


def test_a_scenes_description_is_declared_per_language_ur68():
    from urdido.publish.description import scenes

    plan = {"spoken": {"pt-BR": [{"file": "chapter-1.mp3", "at": 5.0}, {"file": "chapter-2.mp3", "at": 61.0}]}}
    options = {"summary": {"pt-BR": "O Shio em três minutos.", "en": "Shio in three minutes."},
               "notes": {"pt-BR": "Mais em shio.dev", "en": "More at shio.dev"},
               "sources": [{"label": {"pt-BR": "Código", "en": "Code"}, "url": "https://github.com/openviglet/shio"}]}
    text, _ = scenes(SCRIPT, plan, "pt-BR", options)
    assert text.startswith("O Shio em três minutos.\n")
    assert "Mais em shio.dev" in text and "Código: https://github.com/openviglet/shio" in text
    assert "More at" not in text
    with pytest.raises(ValueError, match="summary has no pt-BR entry"):
        scenes(SCRIPT, plan, "pt-BR", {"summary": {"en": "Shio in three minutes."}})
