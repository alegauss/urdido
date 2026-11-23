"""`urdido build <video.toml>`: a product video built from its declaration (VM17).

    urdido build demo/video.toml --language pt-BR [--project]
    urdido build demo/video.toml --language pt-BR --cut chapter:2 [--vertical]
    urdido build demo/developer.toml --language en
    urdido build promo/video.toml --language pt-BR [--cut short:c1]
    ... --plan     stop once the timeline is decided, nothing encoded past it
    ... --cards    draw the cards alone, as previews, and stop

The declaration names the video's sources (one chaptered recording, or scene clips), its
narration, its cards' theme and words, its music, its cuts and where it publishes. Paths in it are
relative to its folder or start at a root it declares (UR22):

    [roots]
    plugin = "../../product/plugin"   # relative to the declaration
    shio = "$SHIO_REPO"                            # or an environment variable

    [output]
    folder = "video"                               # the default; `parts` defaults to "parts" in it

`<root>` is the declaration's folder, `<video>` the output folder and `<recordings>` the
folder's recordings/ unless declared; no other root exists unless declared. STORY_VIDEO_DIR,
STORY_RECORDINGS, TURING_WORDPRESS and SHIO_REPO still fill an undeclared root for one release,
with a notice.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from urdido import cache
from urdido.errors import Refused
from urdido.pipelines.chaptered import Chaptered
from urdido.pipelines.explainer import Explainer
from urdido.pipelines.scenes import Scenes
from urdido.project import LEGACY_ROOTS, NEWLINE, TAB, Project, roots_of  # noqa: F401


class Build(Scenes, Chaptered, Explainer):
    """The pipelines, on the loaded declaration (`urdido.project`)."""
















def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="urdido build", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("declaration", help="the video's .toml")
    p.add_argument("--language", required=True, help="the video's language, as its narration names it")
    p.add_argument("--cut", default="full", help="full, chapter:<n> or short:<c>")
    p.add_argument("--vertical", action="store_true", help="the 9:16 cut of a chapter, from its own recording")
    p.add_argument("--project", action="store_true", help="also the DaVinci Resolve project")
    p.add_argument("--cards", action="store_true", help="draw the cards alone, as previews, and stop")
    p.add_argument("--plan", action="store_true", help="stop once the timeline is decided")
    p.add_argument("--refresh-screens", action="store_true", help="take the store's pages again")
    p.add_argument("--revision", help="keep an immutable package under this revision (overrides video.revision)")
    p.add_argument("--preview", help="illustrated motion review: take:NAME, beat:ID, cue:TAKE:PHRASE or time:START:END")
    p.add_argument("--context-before", type=float, default=0, help="seconds before the preview selection")
    p.add_argument("--context-after", type=float, default=0, help="seconds after the preview selection")
    p.add_argument("--preview-occurrence", type=int, help="1-based spoken-cue occurrence when the phrase repeats")
    p.add_argument("--root", dest="roots", action="append", metavar="NAME=PATH",
                   help="replace a root for this run (video, recordings, a declared one); repeatable")
    p.add_argument("--progress", choices=["human", "json", "off"], default="human",
                   help="live stage events: human on stderr or JSONL on stdout; also saved beside the build parts")
    a = p.parse_args(argv)
    return run(Build(Path(a.declaration), a), a)


#: What `make` passes for an option it is not given: the command line's defaults.
OPTIONS = {
    "cut": "full", "vertical": False, "project": False, "cards": False, "plan": False,
    "refresh_screens": False, "revision": None, "preview": None, "context_before": 0.0,
    "context_after": 0.0, "preview_occurrence": None, "progress": "human", "roots": None,
}


def make(declaration: str | Path, language: str, **options) -> int:
    """Build a video from its declaration, as `urdido build` does (UR49).

    The options are the command line's, by keyword (`cut="chapter:2"`, `plan=True`,
    `progress="off"`); an unknown one is refused by name. Returns 0 when the build
    passed its checks, and raises `urdido.UrdidoError` when it is refused."""
    unknown = sorted(set(options) - set(OPTIONS))
    if unknown:
        raise TypeError(f"urdido.make: no option {', '.join(unknown)}; it takes {', '.join(OPTIONS)}")
    args = argparse.Namespace(declaration=str(declaration), language=language, **{**OPTIONS, **options})
    return run(Build(Path(declaration), args), args)


def run(build: Build, a: argparse.Namespace) -> int:
    """The build `main` and `make` share, on a loaded declaration."""
    kind = build.decl["source"]["kind"]
    if a.preview and kind != "illustrated":
        raise Refused("--preview requires an illustrated source")
    from urdido import progress, textcheck
    from urdido.cards.render import DECLARED
    from urdido.safety import configured

    DECLARED.set((build.decl.get("cards") or {}).get("channel"))
    with progress.configured(build.parts / f"progress.{build.language}.jsonl", mode=a.progress), \
            cache.configured(build.parts / f"cache.{build.language}.json", enabled=kind == "illustrated" and not a.plan,
                             roots=build.roots), \
            textcheck.configured(build.decl.get("text_checks", {}), build.language, enabled=kind == "illustrated"), \
            configured(build.decl.get("captions", {}).get("safe_area", {})):
        with progress.unit("assembly", f"{build.name}.{build.language}:{a.cut}"):
            from urdido.pipelines import pipeline

            result = pipeline(build, kind)()
        if result == 0:
            with progress.unit("declarations", "input hashes"):
                build.write_inputs()
        if result == 0 and build.revision:
            with progress.unit("package", "revision"):
                print(build.revision.complete(build.checked))
    return result
