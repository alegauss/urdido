"""One pipeline per source kind, in its own module; a package can add kinds (UR33)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from urdido import declaration, pipelines
from urdido.build import Build
from urdido.errors import DeclarationError
from urdido.pipelines.chaptered import Chaptered
from urdido.pipelines.finishing import Finishing
from urdido.pipelines.scenes import Scenes

SOURCE = Path(__file__).resolve().parents[1] / "src" / "urdido"


class Plugin:
    """An entry point as `importlib.metadata` gives one."""

    name = "slides"

    @staticmethod
    def load():
        return lambda build: f"slides for {build.name}"


def test_each_pipeline_lives_in_its_own_module_and_build_composes_them():
    assert issubclass(Build, Scenes) and issubclass(Build, Chaptered)
    assert issubclass(Scenes, Finishing) and issubclass(Chaptered, Finishing)
    assert "def chaptered(" not in (SOURCE / "build.py").read_text(encoding="utf-8")
    assert "def scenes(" not in (SOURCE / "build.py").read_text(encoding="utf-8")


def test_built_in_kinds_dispatch_to_their_pipelines():
    build = SimpleNamespace(chaptered=lambda: "c", scenes=lambda: "s")
    assert pipelines.pipeline(build, "chaptered")() == "c"
    assert pipelines.pipeline(build, "scenes")() == "s"
    assert pipelines.pipeline(build, "illustrated")() == "s"


def test_a_package_adds_a_kind_through_the_entry_point_group(monkeypatch):
    monkeypatch.setattr(pipelines, "registered", lambda: {"slides": Plugin})
    build = SimpleNamespace(name="deck")
    assert pipelines.pipeline(build, "slides")() == "slides for deck"
    document = {
        "video": {"name": "x", "languages": {"en": "eng"}},
        "source": {"kind": "slides"},
    }
    assert declaration.check(document) == []


def test_an_unknown_kind_is_refused_by_the_schema_and_the_dispatch(monkeypatch):
    monkeypatch.setattr(pipelines, "registered", dict)
    with pytest.raises(DeclarationError, match="no pipeline builds a 'film' source"):
        pipelines.pipeline(SimpleNamespace(), "film")
    document = {
        "video": {"name": "x", "languages": {"en": "eng"}},
        "source": {"kind": "film"},
    }
    assert "kind is 'film'" in declaration.check(document)[0]
