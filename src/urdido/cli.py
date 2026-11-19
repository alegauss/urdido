"""The `urdido` command line."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from urdido import __version__


def parser() -> argparse.ArgumentParser:
    """The command line's parser, which commands register on as they arrive."""
    built = argparse.ArgumentParser(
        prog="urdido",
        description="Build a narrated video from a declaration.",
    )
    built.add_argument("--version", action="version", version=f"urdido {__version__}")
    return built


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return its exit status."""
    parser().parse_args(argv)
    return 0
