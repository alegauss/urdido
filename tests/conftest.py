"""Suite-wide switches.

A test marked `full` encodes minutes of video. It runs only where `URDIDO_FULL=1`
(the nightly CI job, or a desk that asks for it), and skips by name everywhere else.

Cards draw with Playwright's own Chromium (UR29), which CI installs. A desk without it
but with Microsoft Edge draws with Edge instead, unless E2E_CHANNEL already says.
"""

import os
from pathlib import Path

import pytest

FULL = os.environ.get("URDIDO_FULL") == "1"


def _browser_for_this_desk() -> None:
    if os.environ.get("E2E_CHANNEL"):
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return
    with sync_playwright() as p:
        if Path(p.chromium.executable_path).is_file():
            return
    edge = "Microsoft/Edge/Application/msedge.exe"
    roots = ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")
    if any((Path(os.environ.get(root, "")) / edge).is_file() for root in roots):
        os.environ["E2E_CHANNEL"] = "msedge"


_browser_for_this_desk()


def pytest_collection_modifyitems(config, items):
    if FULL:
        return
    skip = pytest.mark.skip(reason="full encode: set URDIDO_FULL=1 to run it")
    for item in items:
        if "full" in item.keywords:
            item.add_marker(skip)
