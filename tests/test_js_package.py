"""The JavaScript helpers are one npm package, versioned with the Python one (UR30)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import urdido

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import release  # noqa: E402

PACKAGE = json.loads((ROOT / "js" / "package.json").read_text(encoding="utf-8"))


def test_the_npm_version_is_the_python_one_in_npms_spelling():
    assert PACKAGE["version"] == release.npm_version(urdido.__version__)
    assert release.npm_version("0.1.0.dev2") == "0.1.0-dev.2"
    assert release.npm_version("1.2.3") == "1.2.3"


def test_a_release_rewrites_the_package_version_and_nothing_else():
    text = (ROOT / "js" / "package.json").read_text(encoding="utf-8")
    again = release.repackaged(text, "0.2.0")
    assert json.loads(again)["version"] == "0.2.0"
    assert json.loads(again)["exports"] == PACKAGE["exports"]
    assert again.replace('"0.2.0"', f'"{PACKAGE["version"]}"') == text


def test_every_export_is_a_file_the_package_ships():
    for name, target in PACKAGE["exports"].items():
        assert (ROOT / "js" / target).is_file(), name


@pytest.mark.skipif(not shutil.which("node"), reason="node is not on PATH")
def test_the_helpers_import_by_package_name():
    code = (
        "const t = await import('urdido-record/terminal-replay');"
        "const o = await import('urdido-record/narration/opening');"
        "console.log(typeof t.sessionLines, typeof o.checkOpening);"
    )
    run = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        cwd=ROOT / "js",  # a package resolves its own name from inside it
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert run.stdout.strip() == "function function", run.stderr
