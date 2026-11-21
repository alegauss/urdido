"""urdido: build a narrated video from a declaration.

Recording stays JavaScript (the narration reader, the driver and pointer, the terminal
replay, under `js/`); the assembly reads what a recording leaves (`chapters.json` and a
WebM, or `cenas.json` and one clip per take) and builds the video from it.

The declared API (UR49) is three calls, each importing what it needs only when called,
so `import urdido` costs one module of four error classes:

    import urdido

    problems = urdido.check("promo/video.toml")      # [] when it passes
    project = urdido.load("promo/video.toml", "en")  # the declaration, roots, folders
    urdido.make("promo/video.toml", "en", plan=True) # build; options by keyword

The library raises `UrdidoError` (and its kinds) and never exits (UR24).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from urdido.errors import DeclarationError, MissingTool, Refused, UrdidoError

if TYPE_CHECKING:
    from urdido.project import Project

__version__ = "0.1.0.dev0"

__all__ = [
    "DeclarationError",
    "MissingTool",
    "Refused",
    "UrdidoError",
    "__version__",
    "check",
    "load",
    "make",
]


def check(declaration: str | Path) -> list[str]:
    """Every problem in a video.toml and the side files it names; empty if it passes."""
    from urdido.declaration import check_file

    return check_file(declaration)


def load(declaration: str | Path, language: str | None = None) -> Project:
    """A declaration loaded for one language (its first unless named): the checked
    tables (`.decl`), the roots its paths start at (`.roots`), its output and parts
    folders, and `.load(path)` for a side file. Creates the parts folder."""
    import argparse
    import tomllib

    from urdido.project import Project

    path = Path(declaration)
    if language is None:
        document = tomllib.loads(path.read_text(encoding="utf-8-sig"))
        spoken = list((document.get("video") or {}).get("languages") or {})
        if not spoken:
            raise DeclarationError(f"{path} [video]: needs languages")
        language = spoken[0]
    args = argparse.Namespace(language=language, cut="full", vertical=False, plan=True)
    return Project(path, args)


def make(declaration: str | Path, language: str, **options) -> int:
    """Build a video as `urdido build` does, its options by keyword (`cut`, `plan`,
    `vertical`, `revision`, `progress`, ...). Returns 0 when the build passed."""
    from urdido.build import make as build

    return build(declaration, language, **options)
