"""VM46: a successful build identifies the exact declarations it read."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from urdido.build import Build
from urdido.sources.model import RecordingRefused


def fixture(tmp_path):
    declaration = tmp_path / "video.toml"
    declaration.write_text('[video]\nname="test"\nlanguages={en="eng"}\n', encoding="utf-8")
    return Build(declaration, SimpleNamespace(language="en"))


def test_manifest_hashes_actual_bytes_and_refuses_later_edits_vm46(tmp_path, monkeypatch):
    build = fixture(tmp_path)
    script = tmp_path / "script.json"
    script.write_bytes(b'\xef\xbb\xbf{"intro":"current"}\r\n')
    build.load("script.json")
    manifest = json.loads(build.write_inputs().read_text())
    row = next(r for r in manifest["declarations"] if r["file"] == str(script))
    assert row["sha256"] == hashlib.sha256(script.read_bytes()).hexdigest()
    script.write_text('{"intro":"replacement"}', encoding="utf-8")
    with pytest.raises(RecordingRefused, match="changed during build"):
        build.write_inputs()
    with pytest.raises(RecordingRefused, match="changed during build"):
        build.load("script.json")
