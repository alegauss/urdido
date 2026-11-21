"""The declaration loader stands apart from the pipelines (UR33)."""

import json
from types import SimpleNamespace

import pytest

from urdido.build import Build
from urdido.errors import DeclarationError
from urdido.project import Project


def declared(tmp_path, extra=""):
    toml = tmp_path / "video.toml"
    toml.write_text(
        '[video]\nname = "demo"\nlanguages = { en = "eng" }\n' + extra, encoding="utf-8"
    )
    return toml


def args(**more):
    return SimpleNamespace(language="en", cut="full", vertical=False, **more)


def test_a_project_loads_its_declaration_roots_and_folders(tmp_path, monkeypatch):
    monkeypatch.delenv("STORY_VIDEO_DIR", raising=False)
    project = Project(declared(tmp_path, '[output]\nfolder = "built"\n'), args())
    assert project.name == "demo"
    assert project.parts == (tmp_path / "built" / "parts").resolve()
    (tmp_path / "words.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert project.load("words.json") == {"a": 1}
    assert project.portable(str(tmp_path / "built" / "x.mp4")) == "<video>/x.mp4"
    assert project.frame().width == 1920


def test_a_side_file_edited_during_the_build_is_refused(tmp_path, monkeypatch):
    from urdido.sources import RecordingRefused

    monkeypatch.delenv("STORY_VIDEO_DIR", raising=False)
    project = Project(declared(tmp_path), args())
    side = tmp_path / "words.json"
    side.write_text("{}", encoding="utf-8")
    project.load("words.json")
    side.write_text('{"edited": true}', encoding="utf-8")
    with pytest.raises(RecordingRefused, match="changed during build"):
        project.load("words.json")


def test_the_build_is_a_project_with_pipelines(tmp_path, monkeypatch):
    monkeypatch.delenv("STORY_VIDEO_DIR", raising=False)
    build = Build(declared(tmp_path), args())
    assert isinstance(build, Project)
    assert callable(build.chaptered) and callable(build.scenes)
    with pytest.raises(DeclarationError, match="frame must be"):
        Project(declared(tmp_path, "frame = [100, 101]\n"), args()).frame()
