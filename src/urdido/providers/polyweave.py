"""polyweave behind urdido's provider seam (UR25): the one module that runs it.

polyweave's stable contract is its command line, `python -m polyweave <operation>
... --root <project> --json`, not its modules, so this stays a subprocess. Every
answer is parsed here: a non-zero exit, `"ok": false` or an `"error"` is a
`ProviderRefused` naming the operation. Its project file (`polyweave.toml`) and work
folder (`.polyweave/`) are read and named here and nowhere else.

`RUN` is the subprocess call; a test replaces it with a fake that answers as polyweave
would, so nothing else needs polyweave installed to be tested. Without the polyweave
extra, the real call refuses with the `pip install` that fixes it.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from urdido.errors import Refused

CONFIG = "polyweave.toml"
WORK = ".polyweave"
EXTRA = "polyweave"


class ProviderRefused(Refused, RuntimeError):
    """polyweave refused an operation, or answered that it failed."""


def _run(args: list[str], **options):
    if importlib.util.find_spec("polyweave") is None:
        from urdido.extras import MissingExtra

        raise MissingExtra("polyweave", "polyweave")
    return subprocess.run(args, **options)


#: The subprocess call, replaceable by a fake in tests.
RUN = _run


def available() -> bool:
    """Whether polyweave can be run here (always, with a fake installed)."""
    return RUN is not _run or importlib.util.find_spec("polyweave") is not None


def flags(parameters: dict) -> list[str]:
    """Keyword parameters as polyweave flags: a true boolean is a bare flag, a list
    repeats its values after one flag, None is left out."""
    args = []
    for name, value in parameters.items():
        flag = "--" + name
        if isinstance(value, bool):
            if value:
                args.append(flag)
        elif isinstance(value, (list, tuple)):
            args += [flag, *map(str, value)]
        elif value is not None:
            args += [flag, str(value)]
    return args


def operation(name: str, root, **parameters) -> dict:
    """Run one polyweave operation in the project at `root` and return its answer."""
    args = [
        sys.executable,
        "-m",
        "polyweave",
        name,
        *flags(parameters),
        "--root",
        str(Path(root).resolve()),
        "--json",
    ]
    done = RUN(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    if done.returncode:
        raise ProviderRefused(f"{name} refused: {done.stderr or done.stdout}")
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        raise ProviderRefused(f"{name} answered no JSON: {done.stdout[:200]}") from None
    if isinstance(answer, dict) and (answer.get("ok") is False or answer.get("error")):
        raise ProviderRefused(
            f"{name} refused: {json.dumps(answer, ensure_ascii=False)}"
        )
    return answer


def config_file(root) -> Path:
    return Path(root) / CONFIG


def config(root) -> dict:
    """The project's polyweave configuration."""
    return tomllib.loads(config_file(root).read_text("utf-8-sig"))


def work_dir(root, *parts: str) -> Path:
    """A folder of urdido's own under the project's polyweave work folder."""
    return Path(root).joinpath(WORK, *parts)
