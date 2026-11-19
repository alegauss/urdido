"""Suite-wide switches.

A test marked `full` encodes minutes of video. It runs only where `URDIDO_FULL=1`
(the nightly CI job, or a desk that asks for it), and skips by name everywhere else.
"""

import os

import pytest

FULL = os.environ.get("URDIDO_FULL") == "1"


def pytest_collection_modifyitems(config, items):
    if FULL:
        return
    skip = pytest.mark.skip(reason="full encode: set URDIDO_FULL=1 to run it")
    for item in items:
        if "full" in item.keywords:
            item.add_marker(skip)
