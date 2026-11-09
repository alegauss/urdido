"""Which golden plan a test reads: a variant's own, not its teaser's (`<base>-30s.*.plan.json`, VM25)."""

from pathlib import Path


def is_teaser(path: Path) -> bool:
    return "-30s." in path.name


def main_plan(folder: Path) -> Path:
    """A variant folder's own plan."""
    return next(p for p in sorted(folder.glob("*.plan.json")) if not is_teaser(p))


def main_plans(expected: Path) -> list[Path]:
    """Every variant's own plan."""
    return [p for p in sorted(expected.glob("*/*.plan.json")) if not is_teaser(p)]
