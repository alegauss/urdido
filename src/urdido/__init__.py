"""urdido: build a narrated video from a declaration.

Recording stays JavaScript (the narration reader, the driver and pointer, the terminal
replay, under `js/`); the assembly reads what a recording leaves (`chapters.json` and a
WebM, or `cenas.json` and one clip per take) and builds the video from it.

Only the errors are imported here (a module of four classes), so `import urdido` costs
nothing until a command runs. The library raises them and never exits (UR24).
"""

from urdido.errors import DeclarationError, MissingTool, Refused, UrdidoError

__version__ = "0.1.0.dev0"

__all__ = ["DeclarationError", "MissingTool", "Refused", "UrdidoError", "__version__"]
