"""A video built as a variant of another, sharing its files without copying (UR5)."""

import json
import os
from types import SimpleNamespace

import pytest

from urdido.errors import DeclarationError
from urdido.project import Project


def base(folder):
    (folder / "narration" / "en").mkdir(parents=True)
    for take in ("intro", "chapter-1", "outro"):
        (folder / "narration" / "en" / f"{take}.mp3").write_bytes(
            f"base {take}".encode()
        )
    (folder / "footage").mkdir()
    (folder / "footage" / "big.mp4").write_bytes(b"0" * 4096)
    story = {
        "title": "Published",
        "scenes": {"intro": [{"title": "old opening"}], "outro": [{"title": "end"}]},
        "media": {"big": {"file": "footage/big.mp4"}},
    }
    (folder / "storyboard.json").write_text(json.dumps(story), encoding="utf-8")
    (folder / "video").mkdir()
    (folder / "video" / "published.mp4").write_bytes(b"render")
    (folder / "video.toml").write_text(
        '[video]\nname = "wordpress"\nlanguages = { en = "eng" }\n'
        '[source]\nkind = "illustrated"\ndeclaration = "storyboard.json"\n'
        '[narration]\nscript = "script.json"\ntakes = "narration"\ntempo = 1.0\n',
        encoding="utf-8",
    )


def variant(folder):
    (folder / "narration" / "en").mkdir(parents=True)
    (folder / "narration" / "en" / "intro.mp3").write_bytes(b"new intro")
    (folder / "storyboard.json").write_text(
        json.dumps({"scenes": {"intro": [{"title": "new opening"}]}}), encoding="utf-8"
    )
    (folder / "video.toml").write_text(
        '[video]\nname = "wordpress2"\nlanguages = { en = "eng" }\n'
        'base = "../wordpress"\n'
        "[narration]\ntempo = 1.1\n",
        encoding="utf-8",
    )
    return folder / "video.toml"


@pytest.fixture
def pair(tmp_path, monkeypatch):
    base(tmp_path / "wordpress")
    toml = variant(tmp_path / "wordpress2")
    return tmp_path, Project(
        toml, SimpleNamespace(language="en", cut="full", vertical=False)
    )


def test_a_variant_overrides_what_it_holds_and_shares_the_rest(pair):
    root, project = pair
    takes = project.here / "narration" / "en"
    assert (takes / "intro.mp3").read_bytes() == b"new intro"
    assert (takes / "outro.mp3").read_bytes() == b"base outro"
    footage = project.here / "footage" / "big.mp4"
    assert os.path.samefile(
        footage, root / "wordpress" / "footage" / "big.mp4"
    )  # linked
    story = project.load("storyboard.json")
    assert story["scenes"] == {
        "intro": [{"title": "new opening"}],
        "outro": [{"title": "end"}],
    }
    assert story["media"]["big"]["file"] == "footage/big.mp4"


def test_the_declarations_merge_and_the_variant_builds_into_its_own_folder(pair):
    root, project = pair
    assert project.name == "wordpress2"
    assert project.decl["narration"] == {
        "script": "script.json",
        "takes": "narration",
        "tempo": 1.1,
    }
    assert project.decl["source"]["kind"] == "illustrated"
    assert project.out == (root / "wordpress2" / "video").resolve()
    assert not (
        project.here / "video" / "published.mp4"
    ).exists()  # the base's renders stay out


def test_a_fix_in_the_base_reaches_the_variant_on_the_next_build(pair, monkeypatch):
    root, _ = pair
    (root / "wordpress" / "narration" / "en" / "chapter-1.mp3").write_bytes(b"fixed")
    again = Project(
        root / "wordpress2" / "video.toml",
        SimpleNamespace(language="en", cut="full", vertical=False),
    )
    assert (again.here / "narration" / "en" / "chapter-1.mp3").read_bytes() == b"fixed"


def test_a_missing_base_or_a_chain_of_variants_is_refused(tmp_path, monkeypatch):
    args = SimpleNamespace(language="en", cut="full", vertical=False)
    lone = tmp_path / "lone"
    lone.mkdir()
    (lone / "video.toml").write_text(
        '[video]\nname = "x"\nlanguages = { en = "eng" }\nbase = "../nowhere"\n',
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError, match="no video.toml"):
        Project(lone / "video.toml", args)
    base(tmp_path / "wordpress")
    variant(tmp_path / "wordpress2")
    third = tmp_path / "wordpress3"
    third.mkdir()
    (third / "video.toml").write_text(
        '[video]\nname = "w3"\nlanguages = { en = "eng" }\nbase = "../wordpress2"\n',
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError, match="cannot itself be a variant"):
        Project(third / "video.toml", args)
