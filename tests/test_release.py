"""The release script's version arithmetic and the notes it publishes."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = _load("release")
release_notes = _load("release_notes")


@pytest.mark.parametrize(
    ("version", "asked", "expected"),
    [
        ("0.1.0", "patch", "0.1.1"),
        ("0.1.0", "minor", "0.2.0"),
        ("0.1.3", "major", "1.0.0"),
        ("0.1.0", "0.3.0", "0.3.0"),
        ("0.1.0.dev0", "0.1.0", "0.1.0"),
        ("0.1.0.dev0", "patch", "0.1.0"),
        ("0.1.0.dev0", "minor", "0.2.0"),
    ],
)
def test_bumped(version, asked, expected):
    assert release.bumped(version, asked) == expected


@pytest.mark.parametrize(
    ("version", "asked"),
    [("0.1.0", "0.1.0"), ("0.2.0", "0.1.9"), ("0.1.0", "next"), ("0.1.0", "1.0")],
)
def test_bumped_refuses(version, asked):
    with pytest.raises(release.Refused):
        release.bumped(version, asked)


def test_the_package_version_parses_and_rewrites():
    text = (ROOT / "src" / "urdido" / "__init__.py").read_text("utf-8")
    now = release.current(text)
    assert release.current(release.rewritten(text, "9.8.7")) == "9.8.7"
    assert release.current(release.rewritten(text, now)) == now


def test_notes_list_the_shipped_entries():
    diff = "+- ✅ **UR1** **a** — b.\n+- 📋 **UR2** open\n context\n"
    said = release_notes.notes("v0.2.0", "v0.1.0", release_notes.entries(diff))
    assert "pip install urdido==0.2.0" in said
    assert "## Since v0.1.0" in said
    assert "- ✅ **UR1** **a** — b." in said
    assert "UR2" not in said


def test_first_release_points_at_the_changelog():
    said = release_notes.notes("v0.1.0", "", [])
    assert "The first release" in said
