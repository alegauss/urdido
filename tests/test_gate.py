"""The gate names every skipped test with its reason."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gate", ROOT / "tools" / "gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

REPORT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite>
  <testcase classname="tests.test_a" name="test_ok"/>
  <testcase classname="tests.test_a" name="test_bad"><failure message="x"/></testcase>
  <testcase classname="tests.test_b" name="test_long">
    <skipped message="full encode: set URDIDO_FULL=1 to run it"/>
  </testcase>
  <testcase classname="tests.test_b" name="test_ffmpeg">
    <skipped message="ffmpeg is not on PATH"/>
  </testcase>
</testsuite></testsuites>
"""


def test_counts_and_names_each_skip(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(REPORT, encoding="utf-8")
    found = gate.counts(report)
    assert (found["passed"], found["failed"], found["skipped"]) == (1, 1, 2)
    assert {"test": "tests.test_b::test_ffmpeg", "reason": "ffmpeg is not on PATH"} in (
        found["skips"]
    )


def test_summary_groups_skips_by_reason(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(REPORT, encoding="utf-8")
    lines = gate.summary(gate.counts(report), 1)
    assert lines[0] == "gate: exit 1, 1 passed, 1 failed, 2 skipped"
    assert "skipped 1: ffmpeg is not on PATH" in lines
    assert "  tests.test_b::test_long" in lines


def test_missing_report_counts_nothing(tmp_path):
    found = gate.counts(tmp_path / "absent.xml")
    assert found == {"passed": 0, "failed": 0, "skipped": 0, "skips": []}
