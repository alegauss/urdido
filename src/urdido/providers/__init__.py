"""The services urdido calls, behind small seams (UR25).

The rest of the code calls these and never runs a service itself: narration voices,
stock footage, reference frames, web capture and media measures all come through here.
Today one provider answers all of them (polyweave, in `urdido.providers.polyweave`); a
second provider for one seam changes this module, not its callers.
"""

from __future__ import annotations

from urdido.providers import polyweave as _provider

ProviderRefused = _provider.ProviderRefused


def available() -> bool:
    return _provider.available()


def unavailable() -> str:
    """Why the provider cannot run here, with the install that fixes it."""
    from urdido.extras import MissingExtra

    return str(MissingExtra(_provider.EXTRA, _provider.EXTRA))


def safe_area(root, subtitles: str, fonts: str | None = None) -> dict:
    """Which burned-in lines reach a platform's controls (the youtube-shorts bounds)."""
    return _provider.operation(
        "video.safe_area", root, subtitles=subtitles, fonts=fonts
    )


def accept(root, spec: str, subject: str) -> dict:
    """A file held to a spec of measured bounds: each predicate's value and verdict."""
    return _provider.operation("accept.check", root, spec=spec, subject=subject)


def operation(name: str, root, **parameters) -> dict:
    """One named operation of the provider, answered as data."""
    return _provider.operation(name, root, **parameters)


def voice_lines(
    root, script, locale: str, service: str, *, keys=None, spend=False
) -> dict:
    """Plan or buy narration takes (`spend`), as the script file lists them."""
    return _provider.operation(
        "voice.lines",
        root,
        script=script,
        locale=locale,
        service=service,
        spend=str(bool(spend)).lower(),
        keys=keys,
    )


def capture_web(root, source) -> dict:
    """Capture a declared web visit into the recording it names."""
    return _provider.operation("capture.web", root, source=source)


def config(root) -> dict:
    """The provider's project configuration (its services and prices)."""
    return _provider.config(root)


def config_file(root):
    return _provider.config_file(root)


def work_dir(root, *parts: str):
    """A folder for urdido's own state under the provider's work folder."""
    return _provider.work_dir(root, *parts)
