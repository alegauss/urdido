"""The `urdido` command line (UR24).

Each command is a module's own `main(argv)`, imported only when that command runs, so
`urdido --version` loads none of them. `urdido --help` lists every command. The library
raises `urdido.errors.UrdidoError` and never exits; this is the one place an error
becomes a message on stderr and an exit code.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence

from urdido import __version__

#: Each command, the module whose `main(argv)` runs it, and what it does.
COMMANDS = {
    "build": ("urdido.build", "build a video, a chapter, a cut or its plan"),
    "check": ("urdido.declaration", "check a video.toml without building"),
    "prepare": ("urdido.prepare", "plan and buy the narration's takes"),
    "words": ("urdido.narration_words", "transcribe the takes' word times"),
    "thumbnail": ("urdido.thumbnail", "draw the thumbnail and check it with its title"),
    "shorts": ("urdido.shorts", "cut YouTube Shorts from a built video"),
    "record": ("urdido.record", "record a scene video from its declared steps"),
    "terminal": ("urdido.terminal", "run a terminal scene's commands for real"),
    "claims": ("urdido.claims", "inspect, report and review the narration's claims"),
    "library": ("urdido.library", "import and review footage candidates"),
    "storyboard": ("urdido.storyboard", "edit a storyboard's beats"),
    "instance": ("urdido.instances", "start and stop a product instance"),
    "export": ("urdido.export.resolve", "hand the timeline to DaVinci Resolve"),
    "retention": ("urdido.retention", "read where a published video's viewers leave"),
    "publish": (
        "urdido.publish.__main__",
        "write the transcript where it is published",
    ),
}


def parser() -> argparse.ArgumentParser:
    """The command tree: `--version`, and one entry per command for `--help`."""
    built = argparse.ArgumentParser(
        prog="urdido",
        description="Build a narrated video from a declaration.",
        epilog="urdido <command> --help says what a command takes.",
    )
    built.add_argument("--version", action="version", version=f"urdido {__version__}")
    commands = built.add_subparsers(
        dest="command", metavar="<command>", title="commands"
    )
    for name, (_, said) in COMMANDS.items():
        command = commands.add_parser(name, help=said, add_help=False)
        command.add_argument("rest", nargs=argparse.REMAINDER)
    return built


def main(argv: Sequence[str] | None = None) -> int | str | None:
    """Run the command line; the return is what `sys.exit` takes."""
    from urdido.errors import UrdidoError
    from urdido.extras import MissingExtra

    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in COMMANDS:
        module = importlib.import_module(COMMANDS[args[0]][0])
        try:
            return module.main(args[1:])
        except (UrdidoError, MissingExtra) as error:
            print(f"urdido {args[0]}: {error}", file=sys.stderr)
            return 1
    tree = parser()
    tree.parse_args(args)
    return tree.format_help()
