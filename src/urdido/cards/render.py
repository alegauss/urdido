"""The cards' pictures, drawn from their pages with Playwright (VM6), as story-video.mjs draws them:
each card whole, its words alone over nothing (for the parallax to lay over the moving hills), the
backdrop, and each range of hills cut to its own box."""

from __future__ import annotations

import os
from typing import Mapping

from videomaker.cards.html import Frame


def render(pages: Mapping[str, str], frame: Frame, out_dir: str, channel: str | None = None) -> list[str]:
    """Write `<layer>.png` for every page in `pages` (and `card-<n>-text.png` for each card)
    to `out_dir`; returns the files in the order written."""
    from playwright.sync_api import sync_playwright

    os.makedirs(out_dir, exist_ok=True)
    written: list[str] = []
    channel = channel if channel is not None else os.environ.get("E2E_CHANNEL", "msedge")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel or None)
        try:
            page = browser.new_page(viewport={"width": frame.width, "height": frame.height})
            for name, content in pages.items():
                file = os.path.join(out_dir, f"{name}.png")
                page.set_content(content)
                page.evaluate("() => document.fonts.ready")
                if name.startswith("card-hills-"):
                    page.locator(".ridge").screenshot(path=file, omit_background=True)
                    written.append(file)
                    continue
                page.screenshot(path=file)
                written.append(file)
                if name != "card-backdrop":
                    page.evaluate("() => document.body.classList.add('layer-text')")
                    text = os.path.join(out_dir, f"{name}-text.png")
                    page.screenshot(path=text, omit_background=True)
                    written.append(text)
        finally:
            browser.close()
    return written
