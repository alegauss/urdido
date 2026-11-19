"""VM29: run the narration purchase guard in its JavaScript runtime."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("node"), reason="node is not on PATH")
def test_opening_purchase_guard_vm29():
    subprocess.run(["node", "--test", str(Path(__file__).parent / "js" / "opening.test.mjs")],
                   check=True, capture_output=True, text=True, encoding="utf-8")
