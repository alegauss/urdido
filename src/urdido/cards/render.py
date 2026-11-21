"""The cards' pictures, drawn from their pages with Playwright (VM6), as story-video.mjs draws them:
each card whole, its words alone over nothing (for the parallax to lay over the moving hills), the
backdrop, and each range of hills cut to its own box."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path

from urdido.cards.html import Frame

EDGE = "Microsoft/Edge/Application/msedge.exe"
#: The declaration's `[cards] channel`, set around a build (see `urdido.build.main`).
DECLARED: ContextVar[str | None] = ContextVar("cards_channel", default=None)


def browser_channel(asked: str | None = None) -> str | None:
    """The browser cards are drawn with (UR29): the caller's, else the declaration's
    `[cards] channel`, else `E2E_CHANNEL`, else none, which is Playwright's own Chromium
    on every system."""
    return asked or DECLARED.get() or os.environ.get("E2E_CHANNEL") or None


def render(pages: Mapping[str, str], frame: Frame, out_dir: str, channel: str | None = None) -> list[str]:
    """Write `<layer>.png` for every page in `pages` (and `card-<n>-text.png` for each card)
    to `out_dir`; returns the files in the order written. `channel` names a browser other
    than Playwright's bundled Chromium (`msedge`, `chrome`); none is the default."""
    from playwright.sync_api import sync_playwright

    from urdido import cache, progress, safety, textcheck

    os.makedirs(out_dir, exist_ok=True)
    written: list[str] = []
    findings = []
    text_findings = []
    safe_report = Path(out_dir) / "caption-safe-area.json"
    text_report = Path(out_dir) / "text-checks.json"
    safe_report.unlink(missing_ok=True)
    text_report.unlink(missing_ok=True)
    progress.plan("raster", len(pages))
    channel = browser_channel(channel)
    with sync_playwright() as p:
        executable = Path(p.chromium.executable_path)
        if not channel and not executable.is_file():
            from urdido.errors import MissingTool

            raise MissingTool("Playwright's Chromium is not installed, and cards are drawn with it",
                              remedy='python -m playwright install chromium, or declare [cards] channel = "msedge"')
        if channel == "msedge":
            executable = next((Path(os.environ.get(root, "")) / EDGE
                               for root in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA")
                               if (Path(os.environ.get(root, "")) / EDGE).is_file()), None)
        elif channel:
            # Other named channels have different binaries. Refuse caching when we cannot
            # fingerprint that browser, while retaining the renderer's existing channel support.
            executable = None
        browser = None
        page = None
        try:
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
                text_found = textcheck.measure(page, frame, name, layer)
                if text_found:
                    preview = Path(out_dir) / "text-check" / f"{name}.{layer}.png"
                    preview.parent.mkdir(exist_ok=True)
                    page.screenshot(path=str(preview), omit_background=layer == "text")
                    text_findings.extend({**row, "preview": str(preview), "preview_sha256": cache.file_hash(preview)} for row in text_found)
                    if textcheck.CURRENT.get().action == "error":
                        textcheck.publish(text_findings, text_report)

            for name, content in pages.items():
                file = os.path.join(out_dir, f"{name}.png")
                outputs = [file]
                if not name.startswith("card-hills-") and name != "card-backdrop":
                    outputs.append(os.path.join(out_dir, f"{name}-text.png"))

                def raster(content=content, name=name, file=file, outputs=outputs):
                    nonlocal browser, page
                    if browser is None:
                        browser = p.chromium.launch(channel=channel or None)
                        page = browser.new_page(viewport={"width": frame.width, "height": frame.height})
                    before = len(findings)
                    before_text = len(text_findings)
                    page.set_content(content)
                    page.evaluate("() => document.fonts.ready")
                    check_layer(name, "full")
                    if name.startswith("card-hills-"):
                        page.locator(".ridge").screenshot(path=file, omit_background=True)
                    else:
                        page.screenshot(path=file)
                        if len(outputs) > 1:
                            page.evaluate("() => document.body.classList.add('layer-text')")
                            page.evaluate("() => document.fonts.ready")
                            check_layer(name, "text")
                            page.screenshot(path=outputs[1], omit_background=True)
                    return {"safe": findings[before:], "text": text_findings[before_text:]}

                # All production pages embed their fonts/assets in content. External URLs
                # are deliberately uncached because their bytes are not declared here.
                urls = re.findall(r'(?:(?:src|href)\s*=\s*["\']|url\(\s*["\']?)([^)"\'\s]+)', content, re.I)
                embedded = all(url.startswith(("data:", "#")) for url in urls) \
                    and not any(tag in content.lower() for tag in ("<script", "@import"))
                if cache.CURRENT.get() and executable and embedded:
                    before = len(findings)
                    before_text = len(text_findings)
                    found = cache.run("raster", outputs,
                                      [content, frame.width, frame.height, channel, version("playwright"),
                                       asdict(safety.CURRENT.get()), asdict(textcheck.CURRENT.get())], raster,
                                      inputs=[__file__, safety.__file__, textcheck.__file__, executable])
                    if len(findings) == before:
                        findings.extend(found["safe"])
                    if len(text_findings) == before_text:
                        for row in found["text"]:
                            if not Path(row["preview"]).is_file() or cache.file_hash(row["preview"]) != row["preview_sha256"]:
                                preview = outputs[-1] if row["layer"] == "text" else outputs[0]
                                row = {**row, "preview": preview, "preview_sha256": cache.file_hash(preview)}
                            text_findings.append(row)
                else:
                    progress.run("raster", Path(file).name, raster)
                written.extend(outputs)
        finally:
            if browser:
                browser.close()
    safety.publish(findings, safe_report)
    textcheck.publish(text_findings, text_report)
    return written
