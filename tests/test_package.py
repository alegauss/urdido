"""The package installs, answers its version, and refuses a missing extra by name."""

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

import urdido
from urdido import cli, extras

ROOT = Path(__file__).resolve().parents[1]


def test_version_answers(capsys):
    with pytest.raises(SystemExit) as done:
        cli.main(["--version"])
    assert done.value.code == 0
    assert capsys.readouterr().out.strip() == f"urdido {urdido.__version__}"


def test_module_entry_point_answers_version():
    ran = subprocess.run(
        [sys.executable, "-m", "urdido", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert ran.stdout.strip() == f"urdido {urdido.__version__}"


def test_no_arguments_answers_the_usage():
    said = cli.main([])
    assert isinstance(said, str) and said.startswith("usage: urdido build")


def test_a_command_runs_its_module_main(monkeypatch):
    seen = []
    fake = type("Module", (), {"main": staticmethod(lambda argv: seen.append(argv))})
    monkeypatch.setattr(cli.importlib, "import_module", lambda name: fake)
    cli.main(["claims", "video.toml"])
    assert seen == [["video.toml"]]


def test_every_command_names_an_imported_module():
    for module in cli.COMMANDS.values():
        assert (ROOT / "src" / Path(*module.split("."))).with_suffix(".py").is_file()


def test_every_extra_is_declared_in_pyproject():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    assert set(extras.EXTRAS) <= set(project["optional-dependencies"])
    assert project["scripts"]["urdido"] == "urdido.cli:main"


def test_missing_extra_names_its_install(monkeypatch):
    monkeypatch.setitem(extras.EXTRAS, "ghost", ("urdido_no_such_module",))
    with pytest.raises(extras.MissingExtra) as refused:
        extras.require("ghost")
    assert refused.value.remedy == "pip install urdido[ghost]"
    assert "urdido_no_such_module" in str(refused.value)


def test_present_extra_imports(monkeypatch):
    monkeypatch.setitem(extras.EXTRAS, "stdlib", ("json",))
    assert extras.require("stdlib").__name__ == "json"


def test_module_outside_its_extra_is_refused():
    with pytest.raises(KeyError):
        extras.require("narration", "playwright")
