"""urdido: build a narrated video from a declaration.

Recording stays JavaScript (the narration reader, the driver and pointer, the terminal
replay, under `js/`); the assembly reads what a recording leaves (`chapters.json` and a
WebM, or `cenas.json` and one clip per take) and builds the video from it.

Nothing is imported here, so `import urdido` costs nothing until a command runs.
"""

__version__ = "0.1.0.dev0"
