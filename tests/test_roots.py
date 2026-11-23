"""A declaration names its roots and output; the code knows no sibling path (UR22)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from urdido.build import Build, roots_of
from urdido.errors import DeclarationError


def test_only_the_project_roots_exist_without_a_declaration(tmp_path):
    roots = roots_of(tmp_path, {}, env={})
    assert roots == {
        "root": str(tmp_path),
        "video": str((tmp_path / "video").resolve()),
        "recordings": str(tmp_path / "recordings"),
    }


def test_declared_roots_are_relative_paths_or_environment_variables(tmp_path):
    decl = {
        "roots": {"plugin": "../turing/wordpress", "shio": "${SHIO_HOME}"},
        "output": {"folder": "out"},
    }
    roots = roots_of(tmp_path, decl, env={"SHIO_HOME": str(tmp_path / "shio")})
    assert roots["plugin"] == str((tmp_path / "../turing/wordpress").resolve())
    assert roots["shio"] == str((tmp_path / "shio").resolve())
    assert roots["video"] == str((tmp_path / "out").resolve())


def test_an_unset_variable_or_a_reserved_name_is_refused(tmp_path):
    with pytest.raises(DeclarationError, match=r"reads \$NOPE, which is not set"):
        roots_of(tmp_path, {"roots": {"shio": "$NOPE"}}, env={})
    with pytest.raises(DeclarationError, match="root and video are not declared there"):
        roots_of(tmp_path, {"roots": {"video": "x"}}, env={})


def test_no_environment_variable_fills_an_undeclared_root_ur46(tmp_path):
    env = {
        "STORY_VIDEO_DIR": str(tmp_path / "elsewhere"),
        "STORY_RECORDINGS": str(tmp_path / "r"),
        "TURING_WORDPRESS": str(tmp_path / "wp"),
        "SHIO_REPO": str(tmp_path / "s"),
    }
    roots = roots_of(tmp_path, {"roots": {"shio": "mine"}}, env=env)
    assert roots == {
        "root": str(tmp_path),
        "video": str((tmp_path / "video").resolve()),
        "recordings": str(tmp_path / "recordings"),
        "shio": str((tmp_path / "mine").resolve()),
    }


def test_a_path_at_an_undeclared_root_is_refused_by_name(tmp_path):
    toml = tmp_path / "video.toml"
    toml.write_text(
        '[video]\nname = "demo"\nlanguages = { en = "eng" }\n'
        '[output]\nfolder = "built"\nparts = "work"\n',
        encoding="utf-8",
    )
    build = Build(toml, SimpleNamespace(language="en", cut="full", vertical=False))
    assert build.parts == (tmp_path / "built" / "work").resolve()
    assert build.path("<root>/a.json") == str(Path(tmp_path / "a.json"))
    with pytest.raises(
        DeclarationError, match=r"<plugin>, which the declaration does not declare"
    ):
        build.path("<plugin>/cards.json")


def test_no_module_names_a_sibling_checkout():
    source = Path(__file__).resolve().parents[1] / "src" / "urdido"
    for file in source.rglob("*.py"):
        text = file.read_text(encoding="utf-8")
        assert '"turing" / "latest"' not in text and '"shio" / "latest"' not in text, (
            file
        )
