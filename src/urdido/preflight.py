"""VM56 / PW712: read-only validation of an illustrated cut before any render."""
from __future__ import annotations

import math
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from urdido import captions, keywords, media
from urdido.cards.html import Frame, Theme, resolve
from urdido.narration import Takes
from urdido.sources.illustrated import anchored_frames, paced, page, scene_frames, validate
from urdido.sources.model import RecordingRefused


class PreflightRefused(RecordingRefused):
    def __init__(self, findings):
        self.findings = findings
        super().__init__("preflight failed:\n" + "\n".join(
            f"{f['file']} [{f['field']}] take={f['take'] or '-'} beat={f['beat'] or '-'}: {f['message']}"
            for f in findings))


def illustrated(build):
    """Return loaded declarations, or all independent findings. Never writes or purchases."""
    findings = []
    errors = (RecordingRefused, OSError, ValueError, TypeError, KeyError, IndexError, subprocess.SubprocessError)

    def issue(file, field, message, take=None, beat=None):
        row = {"file": str(file), "field": field, "take": take, "beat": beat, "message": str(message)}
        if row not in findings:
            findings.append(row)

    def check(file, field, action, take=None, beat=None):
        try:
            return action()
        except errors as exc:
            issue(file, field, exc, take, beat)
            return None

    def load(declared, field):
        if not declared:
            issue(build.here / "video.toml", field, "missing declaration")
            return None
        return check(build.path(declared), field, lambda: build.load(declared))

    script = load(build.decl.get("narration", {}).get("script"), "narration.script")
    aliases = check(build.here, "narration.aliases", lambda: keywords.aliases(script, build.language)) if script else None
    cards = load(build.decl.get("cards", {}).get("declaration"), "cards.declaration")
    document = load(build.decl.get("source", {}).get("declaration"), "source.declaration")
    if document is not None:
        from urdido.library import check_rejected, check_range, resolve_asset

        for key, asset in document.get("media", {}).items():
            if "library" in asset:
                resolved = check(build.path(build.decl["source"]["declaration"]), f"media.{key}.library",
                                 lambda: resolve_asset(asset, build.here, build.load))
                if resolved is not None:
                    document["media"][key] = resolved
        for beats in document.get("scenes", {}).values():
            for beat in beats:
                binding = document.get("media", {}).get(beat.get("asset"), {}).get("library_binding")
                if binding:
                    beat.setdefault("at", binding["range"].get("start", 0))
    highlight_spec = build.decl.get("highlights", {})
    highlights = load(highlight_spec.get("declaration"), "highlights.declaration") if highlight_spec else None
    translations = [(lang, spec, load(spec.get("file"), f"captions.translations.{lang}.file"))
                    for lang, spec in build.decl.get("captions", {}).get("translations", {}).items()]
    theme = None
    if cards is not None:
        def font_files():
            spec = cards["theme"]["fonts"]
            folder = Path(resolve(spec["dir"], {"root": str(build.here), "shio": build.roots["shio"]}))
            return [folder / name for name in [*spec["display"]["files"].values(), spec["text"]["file"]]]
        fonts = check(build.path(build.decl["cards"]["declaration"]), "theme.fonts", font_files) or []
        for file in fonts:
            check(file, "theme.fonts", lambda file=file: file.read_bytes())
        if fonts and all(file.is_file() for file in fonts):
            theme = check(build.path(build.decl["cards"]["declaration"]), "theme",
                          lambda: Theme.load(cards["theme"], {"root": str(build.here), "shio": build.roots["shio"]}))
    if highlight_spec:
        folder = Path(build.path(highlight_spec.get("fonts", "")))
        if not folder.is_dir() or not any(p.suffix.lower() in {".ttf", ".otf", ".woff", ".woff2"}
                                         for p in folder.iterdir()):
            issue(folder, "highlights.fonts", "missing font directory or font files")
    if highlights is not None:
        def style():
            import re

            value = highlights["style"]
            if not value["font"] or not re.fullmatch(r"#[0-9a-fA-F]{6}", value["color"]):
                raise ValueError("highlight style needs a font name and #RRGGBB color")
            if not math.isfinite(float(value.get("margin", 85))):
                raise ValueError("highlight margin must be finite")
        check(build.path(highlight_spec["declaration"]), "style", style)
    takes = None
    if script is not None:
        takes = check(build.here, "narration", lambda: Takes(script, build.path(build.decl["narration"]["takes"]), build.decl["narration"].get("tempo", 1.0)))
    voices, words = {}, {}
    if takes:
        for name in takes.lines:
            file = Path(takes.take_file(build.language, name))
            found = check(file, "narration.provenance", lambda name=name: takes.takes(name, [build.language], current_language=build.language), name)
            if found is None:
                continue
            if len(found) != 1:
                issue(file, "narration.provenance", "missing or stale take; prepare the current narration explicitly", name)
                continue
            take = voices[name] = found[0]
            transcript = check(file.with_suffix(".words.json"), "words.sha256", lambda file=file: keywords.word_record(file), name)
            if transcript is not None:
                words[name] = transcript
                if transcript and transcript[-1]["end"] > take.length + 0.1:
                    issue(file.with_suffix(".words.json"), "words.end", "word times extend beyond the audio", name)
            for language, spec, table in translations:
                if table is None:
                    continue
                if name not in table:
                    issue(build.path(spec["file"]), language, "missing take translation", name)
                elif transcript is not None:
                    check(build.path(spec["file"]), language,
                          lambda table=table, name=name, take=take: captions.translated_cues(
                              {"at": 0, "length": take.length, "text": take.text}, transcript, table[name]), name)
            if highlights is not None:
                wanted = highlights.get("lines", {}).get(name, [])
                if transcript is not None:
                    cursor = 0
                    for i, item in enumerate(wanted):
                        duration = item.get("duration", 2.8)
                        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
                            issue(build.path(highlight_spec["declaration"]), f"lines.{name}.{i}.duration",
                                  "highlight duration must be finite and positive", name)
                        def match():
                            return keywords.matches(transcript, item.get("hear", item["show"]), cursor, aliases=aliases)
                        candidates = check(build.path(highlight_spec["declaration"]), f"lines.{name}.{i}.hear", match, name)
                        if candidates:
                            cursor = candidates[0][1]
                        elif candidates is not None:
                            issue(build.path(highlight_spec["declaration"]), f"lines.{name}.{i}.hear",
                                  f"keyword anchor {item.get('hear', item.get('show'))!r} not heard; review the transcript", name)
        if highlights is not None:
            for name in highlights.get("lines", {}):
                if name not in takes.lines:
                    issue(build.path(highlight_spec["declaration"]), f"lines.{name}", "unknown narration take", name)
    if document is not None:
        source_file = build.path(build.decl["source"]["declaration"])
        check(build.here / document.get("logo", ""), "logo", lambda: (build.here / document["logo"]).read_bytes())
        scenes = document.get("scenes", {})
        for key, source in document.get("sources", {}).items():
            if not all(source.get(field) for field in ("label", "url")):
                issue(source_file, f"sources.{key}", "source needs a label and URL")
        if takes and list(scenes) != list(takes.lines):
            issue(source_file, "scenes", "scenes must name every narration take in script order")
        durations = {}
        pictures = set()
        beat_errors = set()
        audit, placed, clock = [], [], 0
        intro = check(build.here, "opening", build.intro)
        opening = check(intro.file, "opening.duration", lambda: max(0, media.seconds(intro.file) - intro.start)) if intro else 0
        for name, beats in scenes.items():
            proxy = SimpleNamespace(lines={name: {}}, takes=lambda *args, **kwargs: [SimpleNamespace(length=1)])
            if not beats:
                issue(source_file, f"scenes.{name}", "no illustrated beats", name)
            for i, beat in enumerate(beats):
                key = beat.get("id", f"{name}-{i}")
                try:
                    validate({**document, "scenes": {name: [beat]}, "max_asset_uses": None, "asset_use_limits": {}}, proxy, build.language)
                except errors as exc:
                    beat_errors.add(str(exc))
                    issue(source_file, f"scenes.{name}.{i}", exc, name, key)
                if theme is not None:
                    check(source_file, f"scenes.{name}.{i}.page",
                          lambda: page(beat, document, theme, build.frame() if hasattr(build, "frame") else Frame(1920, 1080),
                                       "preflight", i + 1), name, key)
                if "from_word" in beat and name in words:
                    check(source_file, f"scenes.{name}.{i}.from_word",
                          lambda: keywords.anchor(Path(voices[name].file), beat["from_word"], aliases=aliases), name, key)
                asset = document.get("media", {}).get(beat.get("asset"))
                if asset is not None:
                    if not asset.get("file"):
                        issue(source_file, f"media.{beat['asset']}.file", "missing media path", name, key)
                        continue
                    file = build.here / asset["file"]
                    if not file.is_file():
                        issue(file, f"media.{beat['asset']}.file", "missing media asset", name, key)
                    if not all(asset.get(field) for field in ("license", "author", "url")):
                        issue(source_file, f"media.{beat['asset']}", "media needs license, author and source URL", name, key)
            if name not in voices:
                continue
            take = voices[name]
            lengths = check(source_file, f"scenes.{name}.timing",
                            lambda: anchored_frames(paced(beats, getattr(takes, "tempo", 1.0)),
                                                    scene_frames(document, name, take.length), take.file,
                                                    document.get("max_static_seconds"), aliases=aliases), name)
            if lengths:
                placed.append({"file": take.file, "at": (opening or 0) + clock / 30 + 0.4,
                               "length": take.length, "text": take.text})
                for i, (beat, frames) in enumerate(zip(beats, lengths)):
                    audit.append({"beat": f"{name}-{i}", "at": clock / 30, "seconds": frames / 30})
                    clock += frames
                    asset = document.get("media", {}).get(beat.get("asset"))
                    if not asset or not asset.get("file"):
                        continue
                    check(source_file, f"scenes.{name}.{i}.range", lambda: check_range(beat, asset, frames), name,
                          beat.get("id", f"{name}-{i}"))
                    check(source_file, f"media.{beat['asset']}.rejected", lambda: check_rejected(beat, asset, frames),
                          name, beat.get("id", f"{name}-{i}"))
                    file = build.here / asset["file"]
                    key = beat.get("id", f"{name}-{i}")
                    if file.is_file() and beat.get("layout") == "footage":
                        if file not in durations:
                            durations[file] = check(file, "duration", lambda: media.seconds(str(file)), name, key)
                        at = beat.get("at", 0)
                        if not isinstance(at, (int, float)) or not math.isfinite(at) or at < 0:
                            issue(source_file, f"scenes.{name}.{i}.at", "source start must be finite and nonnegative", name, key)
                        elif durations[file] is not None and at + frames / 30 > durations[file] + 0.02:
                            issue(source_file, f"scenes.{name}.{i}.at", "footage is shorter than the requested beat", name, key)
                    elif file.is_file() and beat.get("layout") == "picture" and file not in pictures:
                        def picture():
                            probe = json.loads(subprocess.run(
                                ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                 "-of", "json", str(file)], capture_output=True, check=True).stdout)
                            if not probe.get("streams") or not all(probe["streams"][0].get(k, 0) > 0 for k in ("width", "height")):
                                raise ValueError("picture has no readable video frame")
                        check(file, f"media.{beat['asset']}.file", picture, name, key)
                        pictures.add(file)
        if takes and len(voices) == len(takes.lines):
            proxy = SimpleNamespace(lines=takes.lines, takes=lambda name, *args, **kwargs: [voices[name]])
            try:
                validate(document, proxy, build.language)
            except errors as exc:
                if str(exc) not in beat_errors:
                    issue(source_file, "scenes", exc)
        if not findings and highlights is not None:
            from urdido.labels import check as labels
            import warnings

            timed = check(build.path(highlight_spec["declaration"]), "lines",
                          lambda: keywords.cues(placed, highlights["lines"], aliases=aliases))
            if timed is not None:
                # The production check still publishes review warnings. Preflight only
                # collects fatal conflicts, without emitting the same warning twice.
                with warnings.catch_warnings(record=True):
                    check(source_file, "labels", lambda: labels(document, {"beats": audit}, timed, opening or 0))
        if not findings:
            from urdido.repetition import inspect, enforce

            report = check(source_file, "repetition", lambda: inspect(document, {"beats": audit}, build.here, opening or 0))
            if report is not None:
                build.repetition_report = report
                check(source_file, "repetition", lambda: enforce(report))
        if not findings:
            from urdido.pauses import inspect as inspect_pauses, enforce as enforce_pauses

            report = check(source_file, "pauses", lambda: inspect_pauses(document, {"beats": audit}, build.here, opening or 0))
            if report is not None:
                build.pause_report = report
                check(source_file, "pauses", lambda: enforce_pauses(report))
    if document is not None and script is not None:
        if build.decl.get("claims") and takes:
            from urdido.claims import inspect as inspect_claims, enforce as enforce_claims

            claim_data = load(build.decl["claims"].get("declaration"), "claims.declaration")
            if claim_data is not None:
                claim_report = check(build.path(build.decl["claims"]["declaration"]), "claims",
                                     lambda: inspect_claims(claim_data, takes, build.language, document, build.here,
                                                            action=build.decl["claims"].get("action", "warn")))
                if claim_report is not None:
                    document["_claims_report"] = claim_report
                    check(build.path(build.decl["claims"]["declaration"]), "claims", lambda: enforce_claims(claim_report))
        from urdido import textcheck

        settings = textcheck.policy(build.decl.get("text_checks", {}), build.language)
        text_findings = check(build.here, "text_checks", lambda: textcheck.inputs(document, script, build.language, theme, settings))
        if text_findings is not None and settings.action != "off":
            for language, spec, table in translations:
                if isinstance(table, dict):
                    for name, sentences in table.items():
                        if isinstance(sentences, list):
                            for i, text in enumerate(sentences):
                                if isinstance(text, str):
                                    text_findings.extend({"field": f"captions.translations.{language}.{name}.{i}", "rule": "encoding",
                                                          "message": message, "file": build.path(spec["file"])}
                                                         for message in textcheck.corruption(text))
        if text_findings:
            if settings.action == "error":
                for row in text_findings:
                    file = row.get("file") or build.path(build.decl["narration"]["script"] if row["field"].startswith("narration.") else
                                      build.decl["cards"]["declaration"] if row["field"].startswith("cards.") else build.decl["source"]["declaration"])
                    issue(file, row["field"], row["message"])
            else:
                textcheck.enforce(text_findings, settings)
    if findings:
        raise PreflightRefused(findings)
    return script, cards, document
