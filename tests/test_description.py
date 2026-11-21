"""VM52: platform budgets never silently delete attribution obligations."""
import json
import tomllib
from pathlib import Path

import pytest

from urdido.publish.description import format_description, illustrated, scion, short_url, units, write
from marketing import MARKETING, needs_marketing

ROOT = MARKETING


@needs_marketing
def test_wordpress_case_fits_with_declared_notes_and_preserves_credits_vm52():
    root = ROOT / "japode/wordpress"
    document = json.loads((root / "storyboard.json").read_text(encoding="utf-8"))
    script = json.loads((root / "narration/script.json").read_text(encoding="utf-8"))
    options = tomllib.loads((root / "video.toml").read_text(encoding="utf-8"))["description"]
    chapters = ["0:00 Introdução"] + [f"{i}:00 {c['title']['pt-BR']}" for i, c in enumerate(script["chapters"].values(), 1)]
    text, proof = illustrated(document, chapters, options)
    assert units(text) <= 5000
    assert text.startswith(document["description"])
    assert document["title"] + "\n\n" not in text[:100]
    assert "Tom Marcello" in text and "CC BY-SA 2.0" in text
    assert "https://creativecommons.org/licenses/by-sa/2.0/" in text
    assert "24:50–25:10" in text and "sem áudio original" in text
    assert "Kevin MacLeod" in text and "Wallpaper" in text
    assert "Apoio: Pixabay" in text and "vinyl-close" not in text
    used = {b["asset"] for beats in document["scenes"].values() for b in beats if b.get("asset")}
    assert len(proof["assets"]) == len(used)
    assert proof["sources"] == document["sources"]


@needs_marketing
def test_scion_legacy_case_keeps_all_33_sources_and_titles_vm52():
    root = ROOT / "japode/scion"
    sources = json.loads((root / "sources.json").read_text(encoding="utf-8-sig"))
    shots = json.loads((root / "shots.json").read_text(encoding="utf-8"))
    script = json.loads((root / "narration/script.json").read_text(encoding="utf-8"))
    publishing = json.loads((root / "publishing.json").read_text(encoding="utf-8"))
    plan = {"shots": [shot for segment in shots["segments"] for shot in segment["shots"]],
            "script": script, "segments": [{"chapter": int(n), "start": 25 + i * 30}
                                          for i, n in enumerate(script["chapters"])]}
    text, proof = scion(plan, sources, publishing)
    assert units(text) <= 5000 and len(proof["assets"]) == 33
    assert text.startswith(publishing["summary"])
    for credit in proof["assets"]:
        assert credit["title"] in text and credit["author"] in text
        assert short_url(credit["url"]) in text
    assert "0:25 " in text and publishing["license_url"] in text


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
