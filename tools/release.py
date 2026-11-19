"""Release the next version to PyPI in one command.

    python tools/release.py patch        0.1.0 -> 0.1.1
    python tools/release.py minor        0.1.0 -> 0.2.0
    python tools/release.py major        0.1.0 -> 1.0.0
    python tools/release.py 0.1.0        exactly that (0.1.0.dev0 -> 0.1.0 included)
    python tools/release.py patch --dry-run

The version lives in `src/urdido/__init__.py` alone. This writes it, commits it, tags
the commit `v<version>` and pushes the branch and the tag together; the tag starts
.github/workflows/publish.yml, which publishes to TestPyPI, then PyPI, then makes the
GitHub release. PyPI takes a number once, so everything is checked first: on main, a
clean tree, nothing on origin that main lacks, and a tag that exists nowhere yet.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "urdido" / "__init__.py"

VERSION = re.compile(
    r'^__version__ = "(\d+)\.(\d+)\.(\d+)(?:\.dev(\d+))?"$', re.MULTILINE
)
PARTS = ("major", "minor", "patch")


class Refused(Exception):
    """A release that must not go ahead, with the reason."""


def current(text: str | None = None) -> str:
    """The package's version as written, `.devN` included."""
    found = VERSION.search(PACKAGE.read_text("utf-8") if text is None else text)
    if not found:
        raise Refused(f'{PACKAGE} holds no __version__ = "X.Y.Z"')
    major, minor, patch, dev = found.groups()
    base = f"{major}.{minor}.{patch}"
    return base if dev is None else f"{base}.dev{dev}"


def bumped(version: str, asked: str) -> str:
    """The version after `asked`: a part to raise, or an exact X.Y.Z above `version`.

    A development version `X.Y.Z.devN` sits below `X.Y.Z`, so releasing `X.Y.Z` from it
    is a step up, and `patch` from it releases `X.Y.Z` itself.
    """
    base, _, dev = version.partition(".dev")
    now = tuple(int(n) for n in base.split("."))
    if asked in PARTS:
        if dev and asked == "patch":
            return base
        at = PARTS.index(asked)
        return ".".join(str(n) for n in (*now[:at], now[at] + 1, *([0] * (2 - at))))
    if not re.fullmatch(r"\d+\.\d+\.\d+", asked):
        raise Refused(f"{asked!r} is not patch, minor, major or a version X.Y.Z")
    wanted = tuple(int(n) for n in asked.split("."))
    if wanted < now or (wanted == now and not dev):
        raise Refused(f"{asked} is not above {version}, and PyPI takes a number once")
    return asked


def rewritten(text: str, version: str) -> str:
    """`text` with its `__version__` set to `version`, every other byte as it was."""
    return VERSION.sub(f'__version__ = "{version}"', text, count=1)


def git(*args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise Refused(f"git {' '.join(args)}: {(done.stderr or done.stdout).strip()}")
    return done.stdout.strip()


def checked(tag: str) -> None:
    """Refuse a release from anywhere but a clean main in step with origin."""
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        raise Refused(f"on {branch}, and a release is made from main")
    if git("status", "--porcelain"):
        raise Refused("the tree has changes; commit or set them aside first")
    git("fetch", "--quiet", "--tags", "origin")
    # Ahead is fine, since the push takes main with the tag; behind or apart is not.
    try:
        git("merge-base", "--is-ancestor", "origin/main", "HEAD")
    except Refused:
        raise Refused("origin/main has commits main does not; pull first") from None
    if git("tag", "--list", tag):
        raise Refused(f"the tag {tag} already exists")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("bump", help="patch, minor, major, or an exact X.Y.Z")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="say what would happen, writing and pushing nothing",
    )
    args = parser.parse_args(argv)
    try:
        was = current()
        version = bumped(was, args.bump)
        tag = f"v{version}"
        checked(tag)
        if args.dry_run:
            print(f"release: would take {was} to {version}, commit, tag {tag} and push")
            return 0
        text = PACKAGE.read_text("utf-8")
        PACKAGE.write_text(rewritten(text, version), encoding="utf-8", newline="\n")
        git("add", "--", str(PACKAGE.relative_to(ROOT)))
        git("commit", "--quiet", "-m", f"chore(release): urdido {version}")
        git("tag", "-a", tag, "-m", f"urdido {version}")
        git("push", "--atomic", "origin", "main", tag)
    except Refused as refused:
        print(f"release: {refused}", file=sys.stderr)
        return 1
    print(
        f"release: {was} -> {version}, tag {tag} pushed; publish.yml takes it to "
        "TestPyPI and then PyPI (gh run watch to follow it)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
