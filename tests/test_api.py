"""The declared Python API: check, load and make, without argparse (UR49)."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

import urdido
from test_preflight import cut  # noqa: F401
from urdido.preflight import PreflightRefused


def test_import_urdido_loads_only_the_errors():
    probe = (
        "import sys, urdido; "
        "print(sorted(m for m in sys.modules if m.startswith('urdido')))"
    )
    loaded = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    ).stdout
    assert loaded.strip() == "['urdido', 'urdido.errors']"
    assert {"check", "load", "make"} <= set(urdido.__all__)


def test_check_load_and_make_a_plan(cut):  # noqa: F811
    cut.cards["words"] = {"en": {}}
    cut.write("cards.json", cut.cards)
    cut.story.update(description="A fixture.", credits="")
    cut.write("story.json", cut.story)
    assert urdido.check(cut.declaration) == []
    project = urdido.load(cut.declaration)
    assert project.language == "en"
    assert project.decl["source"]["kind"] == "illustrated"
    assert Path(project.roots["root"]) == cut.folder.resolve()
    assert urdido.make(cut.declaration, "en", plan=True, progress="off") == 0
    assert list((cut.folder / "video").rglob("*.plan.json"))


def test_make_refuses_as_the_command_does(cut):  # noqa: F811
    cut.write("translations.json", {"outro": ["Tchau"]})
    with pytest.raises(PreflightRefused, match="missing take translation"):
        urdido.make(cut.declaration, "en", plan=True, progress="off")
    with pytest.raises(TypeError, match="no option plna"):
        urdido.make(cut.declaration, "en", plna=True)


def test_check_names_a_problem_and_refuses_an_unreadable_file(tmp_path):
    toml = tmp_path / "video.toml"
    toml.write_text('[video]\nname = "x"\nlanguage = "en"\n', encoding="utf-8")
    assert any("did you mean languages" in p for p in urdido.check(toml))
    with pytest.raises(urdido.DeclarationError):
        urdido.check(tmp_path / "missing.toml")


def test_no_module_imports_another_modules_underscored_name():
    source = Path(__file__).resolve().parents[1] / "src" / "urdido"
    crossing = []
    for file in source.rglob("*.py"):
        text = file.read_text("utf-8")
        for names in re.findall(r"^\s*from urdido[\w.]* import ([^\n(]+)", text, re.M):
            for name in names.split(","):
                imported = name.split(" as ")[0].strip()
                if imported.startswith("_") and imported != "__version__":
                    crossing.append(f"{file.name}: {imported}")
    assert crossing == []
