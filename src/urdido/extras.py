"""Optional extras, and the refusal that names the install a missing one needs."""

from __future__ import annotations

import importlib
from types import ModuleType

#: The distribution name a remedy tells the reader to install.
DISTRIBUTION = "urdido"

#: Each extra in pyproject.toml, mapped to the modules that show it is installed.
EXTRAS: dict[str, tuple[str, ...]] = {
    "cards": ("playwright", "fontTools"),
    "narration": ("requests",),
    "polyweave": ("polyweave",),
}


class MissingExtra(ImportError):
    """An optional extra is not installed; the message says how to install it."""

    def __init__(self, extra: str, module: str) -> None:
        self.extra = extra
        self.module = module
        self.remedy = f"pip install {DISTRIBUTION}[{extra}]"
        super().__init__(
            f"{module} is not installed; it comes with the {extra} extra: {self.remedy}"
        )


def require(extra: str, module: str | None = None) -> ModuleType:
    """Import one of `extra`'s modules, or refuse naming the install that fixes it.

    `module` defaults to the extra's first module. An extra not declared in `EXTRAS`
    is a programming error and raises KeyError.
    """
    modules = EXTRAS[extra]
    name = module or modules[0]
    if name not in modules:
        raise KeyError(f"{name} is not a module of the {extra} extra")
    try:
        return importlib.import_module(name)
    except ImportError as missing:
        raise MissingExtra(extra, name) from missing
