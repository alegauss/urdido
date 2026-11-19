"""The test gate: run pytest, keep its log, and name every test that skipped.

    python tools/gate.py [pytest arguments]

A green suite says nothing about the tests that skipped for lack of ffmpeg, a browser
or the full-encode switch, so the gate reads pytest's JUnit report and says them:

- the whole output goes to `.urdido/gate/pytest.log`;
- `.urdido/gate/stamp.json` records the commit, the exit code, passed, failed and
  skipped, and each skipped test with its reason;
- the last lines name each skip reason with its count, and the tests behind it.

The exit code is pytest's own.
"""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / ".urdido" / "gate"


def counts(report: Path) -> dict:
    """Passed, failed and skipped off the JUnit report, with each skip's reason."""
    found: dict = {"passed": 0, "failed": 0, "skipped": 0, "skips": []}
    if not report.is_file():
        return found
    for case in ET.parse(report).getroot().iter("testcase"):
        name = f"{case.get('classname', '')}::{case.get('name', '')}"
        skip = case.find("skipped")
        if skip is not None:
            found["skipped"] += 1
            reason = (skip.get("message") or skip.text or "no reason given").strip()
            found["skips"].append({"test": name, "reason": reason})
        elif case.find("failure") is not None or case.find("error") is not None:
            found["failed"] += 1
        else:
            found["passed"] += 1
    return found


def commit() -> str:
    ran = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return ran.stdout.strip()


def summary(found: dict, code: int) -> list[str]:
    """The lines the gate ends with: the counts, then each skip reason and its tests."""
    lines = [
        f"gate: exit {code}, {found['passed']} passed, {found['failed']} failed, "
        f"{found['skipped']} skipped"
    ]
    by_reason: dict[str, list[str]] = defaultdict(list)
    for skip in found["skips"]:
        by_reason[skip["reason"]].append(skip["test"])
    for reason, tests in sorted(by_reason.items()):
        lines.append(f"skipped {len(tests)}: {reason}")
        lines.extend(f"  {test}" for test in tests)
    return lines


def main(argv: list[str]) -> int:
    HERE.mkdir(parents=True, exist_ok=True)
    report = HERE / "junit.xml"
    report.unlink(missing_ok=True)
    log = HERE / "pytest.log"
    with log.open("w", encoding="utf-8") as out:
        code = subprocess.run(
            [sys.executable, "-m", "pytest", f"--junitxml={report}", "-rs", *argv],
            cwd=ROOT,
            stdout=out,
            stderr=subprocess.STDOUT,
            check=False,
        ).returncode
    found = counts(report)
    stamp = {"commit": commit(), "exit": code, **found}
    (HERE / "stamp.json").write_text(json.dumps(stamp, indent=2), encoding="utf-8")
    print("\n".join(summary(found, code)))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
