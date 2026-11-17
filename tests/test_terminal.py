"""The Viglet Shio promo's terminal chapters come from its declaration (VM11).

Every line on screen traces to the session record or the prompt file: the declared chapters
equal the selection the promo's script made by hand, except chapter 3's typed note, which is now
the session's own init line, carrying only the plugin the scene is about.
"""

import json
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

HERE = Path(__file__).parent
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node is not on PATH")


@lru_cache(maxsize=1)
def replay() -> dict:
    out = subprocess.run(["node", str(HERE / "js" / "terminal.mjs")], capture_output=True, text=True,
                         check=True, encoding="utf-8")
    return json.loads(out.stdout)


def test_chapters_equal_the_hand_selection_but_the_typed_note():
    data = replay()
    declared, before = data["declared"], data["before"]
    assert sorted(declared) == ["chapter-3", "chapter-4", "chapter-5", "chapter-6"]
    assert declared["chapter-3"][0]["kind"] == "init"
    assert declared["chapter-3"][1:] == before["chapter-3"]
    for chapter in ("chapter-4", "chapter-5", "chapter-6"):
        assert declared[chapter] == before[chapter], chapter


def test_no_line_is_typed_by_hand():
    data = replay()
    record = data["record"]
    prompt = data["declared"]["chapter-4"][0]["text"]
    for chapter, lines in data["declared"].items():
        for line in lines:
            assert line["kind"] in {"init", "prompt", "call", "answer", "error", "text"}, chapter
            if line["kind"] == "text":
                # the agent's own words, as the record holds them (JSON-escaped, accents kept)
                assert json.dumps(line["text"], ensure_ascii=False)[1:-1][:60] in record, chapter
            if line["kind"] == "prompt":
                assert line["text"] == prompt


def test_the_init_line_shows_the_plugin_and_nothing_of_the_machine():
    init = replay()["init"]
    assert init["text"].startswith("plugin shio ")
    assert "MCP plugin:shio:shio" in init["text"]
    for private in ("claude.ai", "\\", "/", "memory", "cowork", "Adobe", "Slack"):
        assert private not in init["text"], private


def test_markdown_formatting_with_stable_report_vm65():
    import re

    shown = replay()["formattedFixture"]
    assert "<table>" in shown and "<th>Trilha</th>" in shown
    assert "<b>Verificação:</b>" in shown and shown.count("<li>") >= 8
    assert "<code>/trilhas/pedra-do-vigia</code>" in shown
    words = re.sub(r"<[^>]+>", " ", shown)
    for raw in ("**", "|---", "| Trilha", "- **", "`"):
        assert raw not in words, raw
    assert "<h4>Relatório</h4>" in shown
    assert "<i>rascunho</i>" in shown
    assert "<ol><li>Revisar</li><li>Publicar</li></ol>" in shown
    assert '<script>' not in shown
    assert '&lt;script&gt;alert("teste")&lt;/script&gt; &amp; revisão.' in shown


def test_current_report_keeps_its_words_vm11_vm65():
    import html
    import re

    data = replay()
    report = data["declared"]["chapter-6"][-1]
    assert report["kind"] == "text"
    # Compare visible words independently of which Markdown structures the agent used.
    source = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-*]\s+|\d+\.\s+)", "", report["text"])
    source = source.replace("**", "").replace("`", "")
    # a table's pipes and its separator row are its structure, drawn as the table itself
    source = re.sub(r"(?m)^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-*:?\s*$", "", source).replace("|", " ")
    visible = html.unescape(re.sub(r"<[^>]+>", " ", data["shown"]))
    assert "".join(source.split()) == "".join(visible.split())
