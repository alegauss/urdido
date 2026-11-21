"""The `urdido` command line.

Each command is a module's own `main(argv)`, imported only when that command runs, so
`urdido --version` loads none of them. UR24 replaces this table with subcommands that
`--help` lists.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence

from urdido import __version__

#: Each command, and the module whose `main(argv)` runs it.
COMMANDS = {
    "build": "urdido.build",
    "thumbnail": "urdido.thumbnail",
    "shorts": "urdido.shorts",
    "record": "urdido.record",
    "claims": "urdido.claims",
    "prepare": "urdido.prepare",
    "library": "urdido.library",
    "storyboard": "urdido.storyboard",
    "instance": "urdido.instances",
}

USAGE = (
    "urdido build <video.toml> --language <l> [--cut full|chapter:N|short:C] ...\n"
    "       urdido thumbnail <video.toml> --language <l>\n"
    f"       urdido {{{','.join(COMMANDS)}}} ...\n"
    "       urdido --version"
)


def parser() -> argparse.ArgumentParser:
    """The parser for what comes before a command: today `--version` alone."""
    built = argparse.ArgumentParser(
        prog="urdido",
        description="Build a narrated video from a declaration.",
        usage=USAGE,
    )
    built.add_argument("--version", action="version", version=f"urdido {__version__}")
    return built


def main(argv: Sequence[str] | None = None) -> int | str | None:
    """Run the command line; the return is what `sys.exit` takes."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in COMMANDS:
        module = importlib.import_module(COMMANDS[args[0]])
        return module.main(args[1:])
    parser().parse_args(args)
    return f"usage: {USAGE}"
