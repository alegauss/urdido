"""A recorded session is judged against its chapters before it is filmed (UR11)."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which("node"), reason="node is not on PATH")
def test_a_session_missing_a_required_beat_is_refused_ur11():
    test = Path(__file__).parent / "js" / "session.test.mjs"
    run = subprocess.run(
        ["node", "--test", str(test)], capture_output=True, text=True, encoding="utf-8"
    )
    assert run.returncode == 0, run.stdout + run.stderr
