"""A thumbnail's pictures are crops of the video's own sources, declared by box (VM51)."""
import pytest

from urdido.thumbnail import crop_filter
from urdido.thumbnail import fit_title


def test_a_box_of_fractions_becomes_an_ffmpeg_crop():
    assert crop_filter([0.25, 0.0, 0.75, 0.5]) == "crop=iw*0.5000:ih*0.5000:iw*0.2500:ih*0.0000"


def test_a_box_outside_the_frame_is_refused():
    with pytest.raises(ValueError, match="between 0 and 1"):
        crop_filter([0.5, 0.0, 0.4, 1.0])


def test_translated_title_fits_both_lines_away_from_subject_vm54():
    import os

    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as driver:
        browser = driver.chromium.launch(channel=os.environ.get("E2E_CHANNEL", "msedge"))
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.set_content('<style>h1{position:absolute;right:44px;top:34px;font: bold 104px/.98 Arial;white-space:nowrap}'
                             'em{display:block;font-style:normal}</style><h1>1 COMMENT<em>39% OF THE WEB</em></h1>')
            report = fit_title(page, (520, 0, 1236, 280), max_size=104)
            assert 64 <= report["font_size"] < 104
            assert len(report["lines"]) == 2
            assert all(line["x"] >= 520 and line["x"] + line["width"] <= 1236 for line in report["lines"])
            page.locator("em").evaluate("el => el.textContent = 'W'.repeat(100)")
            with pytest.raises(ValueError, match="subject-free column"):
                fit_title(page, (520, 0, 1236, 280), max_size=104)
        finally:
            browser.close()
