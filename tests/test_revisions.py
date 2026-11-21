"""VM40: a failed build must leave the previous package and pointer usable."""
import json
from pathlib import Path

import pytest

from urdido import build
from urdido.revisions import Revision


def package(revision):
    file = revision.folder / "test.en.mp4"
    for suffix in (".mp4", ".srt", ".vtt", ".qa.json", ".first.png", ".description.txt"):
        file.with_suffix(suffix).write_text(suffix, encoding="utf-8")
    return str(file)


def test_revisions_preserve_packages_and_refuse_overwrite_vm40(tmp_path):
    first = Revision(tmp_path, "test", "en", "full", "v1")
    file = package(first)
    pointer = first.complete([file])
    old = pointer.read_bytes()
    second = Revision(tmp_path, "test", "en", "full", "v2")
    assert pointer.read_bytes() == old
    assert (second.folder / "INCOMPLETE").exists()
    with pytest.raises(RuntimeError, match="missing"):
        second.complete([str(second.folder / "missing.mp4")])
    assert pointer.read_bytes() == old
    second.complete([package(second)])
    data = json.loads(pointer.read_text())
    assert data["revision"] == "v2"
    review = (tmp_path / data["review"]).read_text()
    assert "test.en.mp4" in review and "test.en.qa.json" in review
    assert "test.en.description.txt" in review
    assert Path(file).read_text() == ".mp4"
    assert (first.folder / "test.en.description.txt").is_file()
    assert not (second.folder / "INCOMPLETE").exists()
    with pytest.raises(FileExistsError):
        Revision(tmp_path, "test", "en", "full", "v1")


@pytest.mark.parametrize("value", ["../escape", "v1/child", "v1\\child", "", ".", "v1. "])
def test_revision_refuses_unsafe_identifiers_vm40(tmp_path, value):
    with pytest.raises(ValueError):
        Revision(tmp_path, "test", "en", "full", value)
    assert not list(tmp_path.iterdir())


def test_build_promotes_only_after_entire_build_succeeds_vm40(tmp_path, monkeypatch):
    declaration = tmp_path / "video.toml"
    declaration.write_text('[video]\nname="test"\nlanguages={en="eng"}\nrevision="v1"\n'
                           '[source]\nkind="scenes"\nlisting="scenes.json"\n', encoding="utf-8")
    monkeypatch.setenv("STORY_VIDEO_DIR", str(tmp_path / "video"))

    def render(self):
        self.checked.append(package(self.revision))
        return 0

    monkeypatch.setattr(build.Build, "scenes", render)
    args = [str(declaration), "--language", "en"]
    assert build.main(args) == 0
    pointer = tmp_path / "video" / "test.en.full.current.json"
    old = pointer.read_bytes()

    def fail(self):
        render(self)
        raise RuntimeError("late export failure")

    monkeypatch.setattr(build.Build, "scenes", fail)
    with pytest.raises(RuntimeError, match="late export"):
        build.main(args + ["--revision", "v2"])
    assert pointer.read_bytes() == old
    assert (tmp_path / "video/revisions/test.en.full/v2/INCOMPLETE").exists()


def test_plan_does_not_reserve_or_promote_revision_vm40(tmp_path, monkeypatch):
    declaration = tmp_path / "video.toml"
    declaration.write_text('[video]\nname="test"\nlanguages={en="eng"}\nrevision="v1"\n'
                           '[source]\nkind="scenes"\nlisting="scenes.json"\n', encoding="utf-8")
    monkeypatch.setenv("STORY_VIDEO_DIR", str(tmp_path / "video"))
    monkeypatch.setattr(build.Build, "scenes", lambda self: 0)
    assert build.main([str(declaration), "--language", "en", "--plan"]) == 0
    assert not (tmp_path / "video/revisions").exists()


def test_pointer_replace_failure_preserves_previous_pointer_vm40(tmp_path, monkeypatch):
    import os

    first = Revision(tmp_path, "test", "en", "full", "v1")
    pointer = first.complete([package(first)])
    before = pointer.read_bytes()
    second = Revision(tmp_path, "test", "en", "full", "v2")

    def fail(*args):
        raise PermissionError("pointer busy")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(PermissionError):
        second.complete([package(second)])
    assert pointer.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))
