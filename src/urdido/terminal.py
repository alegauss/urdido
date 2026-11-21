"""A terminal scene recorded for real, from the commands a video declares (UR53).

    urdido terminal <video.toml>                 every declared scene
    urdido terminal <video.toml> --scene parcial  one of them

Nothing on screen is written by hand: each command runs in a throwaway folder, and the
session keeps what it really printed. `js/film-terminal.mjs` films that session with
the terminal replay's window, typing each command and showing its output:

    [terminal]
    work = "terminal/work"             # cleared before every run (the default)
    session = "terminal/session.json"  # what the film reads (the default)
    title = "Terminal"                 # the window's title bar
    keep = { "git clone" = '^(Cloning into|remote: Total|.*, done\\.$|real\\t)' }

    [terminal.scenes.parcial]
    commands = ["git clone --filter=blob:none --sparse https://... repo", "du -sh repo"]

    [[record.step]]
    name = "terminal"
    command = ["urdido", "terminal", "video.toml"]
    makes = ["terminal/session.json"]

`keep` maps a command's opening words to the printed lines a long output shows, so a
clone's progress (hundreds of rewrites of one line) is shown as each phase's last line.
The commands run in `shell -c` (bash, Git Bash on Windows, unless `shell` names
another); a command that fails leaves the session written and refuses the run, since a
failed session is not fit to film.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
import tomllib
from pathlib import Path

from urdido.errors import DeclarationError, MissingTool, Refused

WORK = "terminal/work"
SESSION = "terminal/session.json"
GIT_BASH = Path(r"C:\Program Files\Git\bin\bash.exe")


def shell_of(declared: str | None) -> str:
    """The shell the commands run in: the declared one, else bash (Git Bash on
    Windows), so the commands are the ones a Linux or macOS viewer would type."""
    if declared:
        found = shutil.which(declared) or (
            declared if Path(declared).is_file() else None
        )
        if not found:
            raise MissingTool(f"terminal: the declared shell {declared} is not found")
        return found
    if os.name == "nt" and GIT_BASH.is_file():
        return str(GIT_BASH)
    found = shutil.which("bash")
    if not found:
        raise MissingTool(
            "terminal: bash is not found",
            "install Git for Windows (its bash.exe) or declare [terminal] shell",
        )
    return found


def scenes_of(spec: dict) -> dict[str, list[str]]:
    scenes = spec.get("scenes") or {}
    if not scenes:
        raise DeclarationError(
            "terminal: [terminal] declares no [terminal.scenes.<name>]"
        )
    out = {}
    for name, scene in scenes.items():
        commands = (scene or {}).get("commands")
        if not (
            isinstance(commands, list)
            and commands
            and all(isinstance(c, str) and c.strip() for c in commands)
        ):
            raise DeclarationError(
                f"terminal: [terminal.scenes.{name}] commands is a list of commands"
            )
        out[name] = commands
    return out


def shown(command: str, output: str, keep: dict[str, str]) -> list[str]:
    """The printed lines a scene shows: all of them, unless `keep` names a pattern for
    the command's opening words, and then each matching line once, in order."""
    lines = [line.rstrip() for line in output.split("\n")] if output else []
    for prefix, pattern in keep.items():
        if command.startswith(prefix) or command.startswith(f"time {prefix}"):
            wanted = re.compile(pattern)
            return list(dict.fromkeys(line for line in lines if wanted.search(line)))
    return lines


def run(shell: str, command: str, work: Path, keep: dict[str, str]) -> dict:
    started = time.monotonic()
    done = subprocess.run(
        [shell, "-c", command],
        cwd=work,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "LC_ALL": "C", "GIT_TERMINAL_PROMPT": "0"},
    )
    # A progress line rewrites itself with carriage returns; each state is its own line.
    output = done.stdout + done.stderr
    output = output.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    return {
        "command": command,
        "output": output,
        "exit": done.returncode,
        "seconds": round(time.monotonic() - started, 2),
        "shown": shown(command, output, keep),
    }


def clear(path: Path) -> None:
    """The last run's folder removed; Git's pack files are read-only on Windows."""

    def writable(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    if path.exists():
        shutil.rmtree(path, onexc=writable)


def capture(declaration: Path, only: str | None = None) -> Path:
    """Run the declared scenes and write the session; returns its path."""
    document = tomllib.loads(declaration.read_text(encoding="utf-8-sig"))
    spec = document.get("terminal")
    if not spec:
        raise DeclarationError(f"terminal: {declaration.name} declares no [terminal]")
    here = declaration.resolve().parent
    scenes = scenes_of(spec)
    if only is not None:
        if only not in scenes:
            raise DeclarationError(
                f"terminal: no scene {only}; the scenes are {', '.join(scenes)}"
            )
        scenes = {only: scenes[only]}
    shell = shell_of(spec.get("shell"))
    keep = dict(spec.get("keep") or {})
    work = here / spec.get("work", WORK)
    session_file = here / spec.get("session", SESSION)
    clear(work)
    work.mkdir(parents=True)
    session = {}
    if only is not None and session_file.is_file():
        session = json.loads(session_file.read_text(encoding="utf-8"))
    for name, commands in scenes.items():
        session[name] = [run(shell, command, work, keep) for command in commands]
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(
        json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    failed = []
    for name in scenes:
        for step in session[name]:
            took = f"exit {step['exit']}, {step['seconds']} s"
            print(f"[{name}] {step['command']} -> {took}")
            if step["exit"] != 0:
                failed.append(f"[{name}] {step['command']} (exit {step['exit']})")
    if failed:
        raise Refused(
            "terminal: a command failed, so the session is not fit to film: "
            + "; ".join(failed),
            "fix the command or what it runs against, then record again",
        )
    return session_file


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="urdido terminal",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("declaration", help="the video's .toml")
    p.add_argument("--scene", help="record one scene, keeping the others' session")
    a = p.parse_args(argv)
    written = capture(Path(a.declaration), a.scene)
    print(f"terminal: {written}", file=sys.stderr)
    return 0
