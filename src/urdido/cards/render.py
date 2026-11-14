"""The cards' pictures, drawn from their pages with Playwright (VM6), as story-video.mjs draws them:
each card whole, its words alone over nothing (for the parallax to lay over the moving hills), the
backdrop, and each range of hills cut to its own box."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from videomaker.cards.html import Frame


def render(pages: Mapping[str, str], frame: Frame, out_dir: str, channel: str | None = None) -> list[str]:
    """Write `<layer>.png` for every page in `pages` (and `card-<n>-text.png` for each card)
    to `out_dir`; returns the files in the order written."""
    from playwright.sync_api import sync_playwright
    from videomaker import safety

    os.makedirs(out_dir, exist_ok=True)
    written: list[str] = []
    findings = []
    safe_report = Path(out_dir) / "caption-safe-area.json"
    safe_report.unlink(missing_ok=True)
    channel = channel if channel is not None else os.environ.get("E2E_CHANNEL", "msedge")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel or None)
        try:
            page = browser.new_page(viewport={"width": frame.width, "height": frame.height})

            def check_layer(name, layer):
                found = safety.collisions(safety.page_boxes(page, name), frame.height)
                for item in found:
                    match = next((f for f in findings if f["page"] == name and all(
                        f[k] == item[k] for k in ("label", "text", "x", "y", "width", "height"))), None)
                    if match:
                        match["layers"].append(layer)
                    else:
                        findings.append({**item, "page": name, "layers": [layer]})
                if found and safety.CURRENT.get().action == "error":
                    safety.publish(findings, safe_report)

            for name, content in pages.items():
                file = os.path.join(out_dir, f"{name}.png")
                page.set_content(content)
                page.evaluate("() => document.fonts.ready")
                check_layer(name, "full")
                if name.startswith("card-hills-"):
                    page.locator(".ridge").screenshot(path=file, omit_background=True)
                    written.append(file)
                    continue
                page.screenshot(path=file)
                written.append(file)
                if name != "card-backdrop":
                    page.evaluate("() => document.body.classList.add('layer-text')")
                    page.evaluate("() => document.fonts.ready")
                    check_layer(name, "text")
                    text = os.path.join(out_dir, f"{name}-text.png")
                    page.screenshot(path=text, omit_background=True)
                    written.append(text)
        finally:
            browser.close()
    safety.publish(findings, safe_report)
    return written
