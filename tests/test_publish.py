"""A video publishes only where its declaration says (VM15)."""

import json
import os
from pathlib import Path

import pytest

from videomaker import publish

WORDPRESS = Path(__file__).parent.parent.parent / "turing" / "wordpress"
DECLARED = json.loads((WORDPRESS / "demo" / "publish.json").read_text(encoding="utf-8"))
SCRIPT = json.loads((WORDPRESS / "demo" / "narration" / "script.json").read_text(encoding="utf-8"))
TURING = Path(os.environ.get("TURING_REPO", r"D:\Git\viglet\turing\latest"))


def test_the_transcript_drops_voice_directions():
    lines = publish.transcript(SCRIPT, "pt-BR")
    assert lines
    assert not any("[" in line or "  " in line for line in lines)
    assert len(lines) == 2 + 2 * len(SCRIPT["chapters"])


@pytest.mark.skipif(not (TURING / "frontend").exists(), reason="the Turing repository is not beside this one")
def test_the_transcript_targets_hold_what_the_declaration_writes():
    outputs = publish.transcript_outputs(DECLARED["transcript"], SCRIPT, {"turing": str(TURING)})
    assert [Path(p).name for p, _ in outputs] == ["wordpress-transcript.ts", "index.md"]
    assert publish.write_outputs(outputs, check=True) == []  # what Turing holds is current


def test_stills_go_only_where_declared(tmp_path):
    still = tmp_path / "chapter-1.webp"
    still.write_bytes(b"webp")
    declared = {**DECLARED["stills"], "to": "<turing>/site/chapter-{n}.webp"}
    roots = {"turing": str(tmp_path / "turing")}
    assert publish.publish_stills(declared, [str(still)], "story", "pt-BR", roots) == []
    assert publish.publish_stills(declared, [str(still)], "developer", "en", roots) == []
    written = publish.publish_stills(declared, [str(still)], "story", "en", roots)
    assert written == [os.path.normpath(str(tmp_path / "turing" / "site" / "chapter-1.webp"))]
    assert Path(written[0]).read_bytes() == b"webp"
