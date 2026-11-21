"""VM48: player captions keep a declared band clear of labels and marks."""
import json
import os

import pytest

from urdido import safety
from urdido.cards.html import Frame
from urdido.cards.render import render
from urdido.sources.model import RecordingRefused


def test_band_scales_with_frame_and_can_be_overridden_vm48():
    box = [{"label": "title", "text": "Hello", "y": 850, "height": 50}]
    assert safety.collisions(box, 1080, safety.Policy(.2, "warn"))[0]["crossing"] == 36
    assert not safety.collisions(box, 1080, safety.Policy(.1, "error"))
    assert not safety.collisions(box, 1920, safety.Policy(.2, "warn"))
    assert not safety.collisions(box, 1080, safety.Policy(.2, "off"))


def test_ass_outline_is_included_and_error_mode_preserves_diagnostics_vm48(tmp_path):
    timed = [{"at": 1, "end": 2, "show": "Name"}]
    report = tmp_path / "highlights.json"
    with safety.configured({"action": "error"}):
        with pytest.raises(RecordingRefused, match="Name.*crosses"):
            safety.highlights({"margin": 216}, timed, report)
        data = json.loads(report.read_text())
        assert data["findings"][0]["crossing"] == 18
        safety.highlights({"margin": 260}, timed, report)
        assert not json.loads(report.read_text())["findings"]
    assert safety.CURRENT.get().action == "off"


def test_browser_reports_actual_bottom_brand_and_refuses_before_png_vm48(tmp_path):
    pytest.importorskip("playwright.sync_api")
    page = '<style>body{margin:0}header{position:absolute;bottom:10px;height:50px}</style><header>Viglet</header>'
    with safety.configured({"action": "error"}):
        with pytest.raises(RecordingRefused, match="Viglet"):
            render({"mark": page}, Frame(1920, 1080), str(tmp_path), channel=os.environ.get("E2E_CHANNEL"))
    assert not (tmp_path / "mark.png").exists()
    data = json.loads((tmp_path / "caption-safe-area.json").read_text())
    assert data["findings"][0]["label"] == "header"
    assert data["findings"][0]["page"] == "mark"


def test_warn_mode_writes_images_and_ignores_hidden_labels_vm48(tmp_path):
    pytest.importorskip("playwright.sync_api")
    page = ('<style>body{margin:0}h1{position:absolute;bottom:10px}header{display:none}</style>'
            '<header>Hidden</header><h1>Visible</h1>')
    with safety.configured({"action": "warn"}):
        with pytest.warns(UserWarning, match="1 overlap"):
            render({"card": page}, Frame(1920, 1080), str(tmp_path), channel=os.environ.get("E2E_CHANNEL"))
    assert (tmp_path / "card.png").is_file()
    findings = json.loads((tmp_path / "caption-safe-area.json").read_text())["findings"]
    assert len(findings) == 1 and findings[0]["text"] == "Visible"
    assert findings[0]["layers"] == ["full", "text"]


def test_text_overlay_is_checked_after_its_layout_changes_vm48(tmp_path):
    pytest.importorskip("playwright.sync_api")
    page = ('<style>body{margin:0}h1{position:absolute;top:10px;height:50px;margin:0}'
            '.layer-text h1{top:auto;bottom:10px}</style><h1>Overlay</h1>')
    with safety.configured({"action": "error"}):
        with pytest.raises(RecordingRefused, match="Overlay"):
            render({"card": page}, Frame(1920, 1080), str(tmp_path), channel=os.environ.get("E2E_CHANNEL"))
    assert (tmp_path / "card.png").is_file()
    assert not (tmp_path / "card-text.png").exists()
    findings = json.loads((tmp_path / "caption-safe-area.json").read_text())["findings"]
    assert findings[0]["layers"] == ["text"]


@pytest.mark.parametrize("spec", [{"bottom": -1}, {"bottom": 1}, {"bottom": float("nan")}, {"action": "guess"}])
def test_invalid_policy_is_refused_vm48(spec):
    with pytest.raises(ValueError):
        with safety.configured(spec):
            pass
