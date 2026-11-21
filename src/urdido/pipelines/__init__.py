"""The pipelines a video is built by, one per source kind (UR33).

`[source] kind` picks one: `chaptered` (one recording cut into chapters), `scenes`
(scene clips) and `illustrated` (illustrated beats, through the scenes pipeline) are
urdido's own. A package adds a kind without forking by registering a function
`pipeline(build) -> int` under the entry point group `urdido.sources`; it receives the
`urdido.build.Build` (the loaded declaration, its roots, folders and finishing stages)
and returns the build's exit code.
"""

from __future__ import annotations

from importlib.metadata import entry_points

GROUP = "urdido.sources"

#: urdido's own kinds, and the method of `Build` that builds each.
BUILT_IN = {"chaptered": "chaptered", "scenes": "scenes", "illustrated": "scenes"}


def registered() -> dict:
    """The kinds installed packages add, by name."""
    return {ep.name: ep for ep in entry_points(group=GROUP)}


def kinds() -> set[str]:
    return set(BUILT_IN) | set(registered())


def pipeline(build, kind: str):
    """What builds `kind` for `build`: one of its methods, or a plugin's function."""
    if kind in BUILT_IN:
        return getattr(build, BUILT_IN[kind])
    plugins = registered()
    if kind in plugins:
        function = plugins[kind].load()
        return lambda: function(build)
    from urdido.errors import DeclarationError

    raise DeclarationError(
        f"urdido build: no pipeline builds a {kind!r} source; the "
        f"kinds are {', '.join(sorted(kinds()))}"
    )
