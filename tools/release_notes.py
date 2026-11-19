"""The notes of a GitHub release, beside the PyPI upload of the same tag.

    python tools/release_notes.py v0.2.0 > notes.md

publish.yml runs this once PyPI has the version. The notes are the shipped entries
docs/CHANGELOG.md gained since the tag before, one entry a line, under the install line.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = "docs/CHANGELOG.md"
#: How a shipped entry opens in the changelog roadkeep writes.
SHIPPED = "- ✅ "


def git(*args: str) -> str:
    done = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return done.stdout if done.returncode == 0 else ""


def previous(tag: str) -> str:
    """The version tag before `tag`, or "" where it is the first."""
    return git("describe", "--tags", "--abbrev=0", "--match", "v*", f"{tag}^").strip()


def entries(diff: str) -> list[str]:
    """The shipped entries a changelog diff adds, each as the changelog spells it."""
    return [line[1:] for line in diff.splitlines() if line.startswith("+" + SHIPPED)]


def notes(tag: str, before: str, added: list[str]) -> str:
    version = tag.removeprefix("v")
    lines = ["```", f"pip install urdido=={version}", "```", ""]
    if not before:
        lines.append(
            f"The first release. What it holds is in [{CHANGELOG}]"
            f"(https://github.com/alegauss/urdido/blob/{tag}/{CHANGELOG})."
        )
    elif added:
        lines += [f"## Since {before}", "", *added]
    else:
        lines.append(f"No entry shipped since {before}.")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 1 or not argv[0].startswith("v"):
        print("usage: release_notes.py v<version>", file=sys.stderr)
        return 2
    tag = argv[0]
    before = previous(tag)
    added = entries(git("diff", f"{before}..{tag}", "--", CHANGELOG)) if before else []
    sys.stdout.write(notes(tag, before, added))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
