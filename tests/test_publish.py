"""A video publishes only where its declaration says (VM15), on a fixture (UR31)."""

import os
from pathlib import Path

from urdido import publish

SCRIPT = {
    "intro": {"en": "[calm] Hello  there.", "pt-BR": "Olá."},
    "chapters": {
        "2": {"card": {"en": "Second."}, "result": {"en": "Done twice."}},
        "1": {"card": {"en": "[excited] First."}, "result": {"en": "Done once."}},
    },
    "outro": {"en": "Bye.", "pt-BR": "Tchau."},
}
DECLARED = {
    "transcript": {
        "languages": [["en", "English"]],
        "module": {
            "path": "<site>/transcript.ts",
            "header": ["// generated"],
            "const": "TRANSCRIPT",
        },
        "page": {
            "path": "<site>/index.md",
            "find": "<!-- transcript -->",
            "start": "<!-- transcript -->",
            "end": "<!-- /transcript -->",
        },
    },
    "stills": {"story": "story", "language": "en", "to": "<site>/chapter-{n}.webp"},
}


def test_the_transcript_drops_voice_directions_in_chapter_order():
    assert publish.transcript(SCRIPT, "en") == [
        "Hello there.",
        "First.",
        "Done once.",
        "Second.",
        "Done twice.",
        "Bye.",
    ]
    assert publish.transcript(SCRIPT, "pt-BR") == ["Olá.", "Tchau."]


def test_the_transcript_targets_hold_what_the_declaration_writes(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.md").write_text(
        "# Demo\n\n<!-- transcript -->\nold\n<!-- /transcript -->\n", encoding="utf-8"
    )
    roots = {"site": str(site)}
    outputs = publish.transcript_outputs(DECLARED["transcript"], SCRIPT, roots)
    assert [Path(p).name for p, _ in outputs] == ["transcript.ts", "index.md"]
    assert publish.write_outputs(outputs) == [
        str(site / "transcript.ts"),
        str(site / "index.md"),
    ]
    module = (site / "transcript.ts").read_text(encoding="utf-8")
    assert module.startswith("// generated\nexport const TRANSCRIPT")
    page = (site / "index.md").read_text(encoding="utf-8")
    assert "old" not in page and "<summary>Transcript (English)</summary>" in page
    again = publish.transcript_outputs(DECLARED["transcript"], SCRIPT, roots)
    assert (
        publish.write_outputs(again, check=True) == []
    )  # what the site holds is current


def test_stills_go_only_where_declared(tmp_path):
    still = tmp_path / "chapter-1.webp"
    still.write_bytes(b"webp")
    roots = {"site": str(tmp_path / "site")}
    declared = DECLARED["stills"]
    assert publish.publish_stills(declared, [str(still)], "story", "pt-BR", roots) == []
    assert (
        publish.publish_stills(declared, [str(still)], "developer", "en", roots) == []
    )
    written = publish.publish_stills(declared, [str(still)], "story", "en", roots)
    assert written == [os.path.normpath(str(tmp_path / "site" / "chapter-1.webp"))]
    assert Path(written[0]).read_bytes() == b"webp"
