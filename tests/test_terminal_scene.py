"""A terminal scene's commands run for real, and the film reads what they printed
(UR53)."""

import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from urdido import terminal
from urdido.declaration import check
from urdido.errors import DeclarationError, MissingTool, Refused

ROOT = Path(__file__).resolve().parents[1]


def declare(folder: Path, scenes: str, extra: str = "") -> Path:
    # The Python interpreter stands in for bash: `python -c <command>` is a real run.
    shell = sys.executable.replace("\\", "/")
    toml = folder / "video.toml"
    toml.write_text(
        f'[video]\nname = "t"\nlanguages = {{ en = "eng" }}\n'
        f'[terminal]\nshell = "{shell}"\n{extra}{scenes}',
        encoding="utf-8",
    )
    return toml


def test_each_command_runs_in_a_cleared_folder_and_keeps_what_it_printed(tmp_path):
    stale = tmp_path / "terminal" / "work" / "stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("from the last run")
    toml = declare(
        tmp_path,
        "[terminal.scenes.listing]\ncommands = [\n"
        "  \"import os; print(sorted(os.listdir('.')))\",\n"
        "  \"print('Cloning into x'); print('50%'); print('100%, done.')\",\n"
        "]\n",
        extra="keep = { \"print('Cloning\" = '(Cloning into|done\\.$)' }\n",
    )
    session_file = terminal.capture(toml)
    session = json.loads(session_file.read_text(encoding="utf-8"))
    first, second = session["listing"]
    assert first["output"] == "[]" and first["exit"] == 0  # the folder was cleared
    assert second["output"].split("\n") == ["Cloning into x", "50%", "100%, done."]
    assert second["shown"] == ["Cloning into x", "100%, done."]
    assert not stale.exists()


def test_a_failed_command_refuses_the_session_but_writes_it(tmp_path):
    toml = declare(
        tmp_path, '[terminal.scenes.bad]\ncommands = ["import sys; sys.exit(3)"]\n'
    )
    with pytest.raises(Refused, match=r"\[bad\] import sys; sys.exit\(3\) \(exit 3\)"):
        terminal.capture(toml)
    assert (tmp_path / "terminal" / "session.json").is_file()


def test_one_scene_is_recorded_again_and_the_others_kept(tmp_path):
    toml = declare(
        tmp_path,
        "[terminal.scenes.a]\ncommands = [\"print('a')\"]\n"
        "[terminal.scenes.b]\ncommands = [\"print('b')\"]\n",
    )
    terminal.capture(toml)
    again = json.loads(terminal.capture(toml, "b").read_text(encoding="utf-8"))
    assert set(again) == {"a", "b"}
    with pytest.raises(DeclarationError, match="no scene c; the scenes are a, b"):
        terminal.capture(toml, "c")


def test_the_declaration_is_checked_and_a_missing_shell_named(tmp_path):
    toml = declare(tmp_path, "[terminal.scenes.a]\ncomands = [\"print('a')\"]\n")
    found = check(tomllib.loads(toml.read_text(encoding="utf-8")))
    assert any("unknown key comands; did you mean commands?" in f for f in found)
    with pytest.raises(MissingTool, match="no-such-shell"):
        terminal.shell_of("no-such-shell")


@pytest.mark.skipif(not shutil.which("node"), reason="node is not on PATH")
def test_the_film_types_each_command_and_shows_its_kept_lines():
    steps = [
        {"command": "git clone x", "shown": ["Cloning into x", "done."]},
        {"command": "true", "shown": []},
    ]
    code = (
        "const t = await import('urdido-record/terminal-replay');"
        "await import('urdido-record/film-terminal');"
        f"console.log(JSON.stringify(t.commandLines({json.dumps(steps)})));"
    )
    run = subprocess.run(
        ["node", "--input-type=module", "-e", code],
        cwd=ROOT / "js",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert json.loads(run.stdout) == [
        {"kind": "prompt", "text": "git clone x"},
        {"kind": "answer", "text": "Cloning into x\ndone."},
        {"kind": "prompt", "text": "true"},
    ], run.stderr
