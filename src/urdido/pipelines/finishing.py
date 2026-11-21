"""The stages every pipeline finishes with: verification, translated captions, the
opening animation and the drawn cards (UR33)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from urdido import captions as cap
from urdido.cards import html
from urdido.declaration import setting
from urdido.errors import Refused
from urdido.project import Project


class Finishing(Project):
    """The stages every pipeline finishes with."""

    def checked_output(self, file: str, *, illustrated: bool = False, clips=()) -> str:
        """VM39: no finished export is announced until its measured sidecar exists."""
        from urdido.qa import report

        edit = (
            self.load(str(self.parts / "illustrated" / "edit.json"))
            if illustrated
            else None
        )
        highlights = (
            self.load(self.decl["highlights"]["declaration"])
            if illustrated and self.decl.get("highlights")
            else None
        )
        assets = None
        if illustrated:
            from urdido.library import resolve

            assets = resolve(
                self.load(self.decl["source"]["declaration"]), self.here, self.load
            ).get("media", {})
        texts = [Path(self.path(self.decl["narration"]["script"]))]
        texts.extend(
            p
            for suffix in (".srt", ".vtt")
            if (p := Path(file).with_suffix(suffix)).exists()
        )
        from urdido import progress

        progress.run(
            "verification",
            Path(file).name,
            lambda: report(
                file,
                edit=edit,
                highlights=highlights,
                assets=assets,
                text_files=texts,
                peak_ceiling=setting(self.decl, "audio", "peak"),
                clips=clips,
                flash_action=setting(self.decl, "qa", "flashes"),
                flash_threshold=setting(self.decl, "qa", "flash_threshold"),
                flash_refuse=setting(self.decl, "qa", "flash_refuse"),
            ),
        )
        self.checked.append(file)
        return file

    def translated_tracks(self, placed):
        """Pure production cue timing, shared by publishing and VM57 motion previews."""
        tracks = []
        for language, spec in (
            self.decl.get("captions", {}).get("translations", {}).items()
        ):
            from urdido.keywords import word_record

            table = self.load(spec["file"])
            cues = []
            for take in placed:
                audio = self.path(take["file"])
                stem = Path(audio).stem
                if stem not in table:
                    raise Refused(
                        f"captions.{language}: no translation for the take {stem}"
                    )
                try:
                    cues += cap.translated_cues(
                        take, word_record(Path(audio)), table[stem]
                    )
                except ValueError as e:
                    raise Refused(f"captions.{language}, {stem}: {e}") from e
            tracks.append((language, spec.get("track", language), cues))
        return tracks

    def translated_captions(self, placed) -> list[tuple[str, str]]:
        """The `[captions.translations.<language>]` the video declares (VM53):
        captions in a language it is not narrated in, timed sentence by sentence to
        the spoken takes. Writes `<name>.<language>.srt` and `.vtt`; returns the
        ISO 639-2 track code and the srt path, per language."""
        out = []
        for language, track, cues in self.translated_tracks(placed):
            for ext, text in (("srt", cap.srt(cues)), ("vtt", cap.vtt(cues))):
                (self.out / f"{self.name}.{language}.{ext}").write_text(
                    text, encoding="utf-8", newline=""
                )
            out.append((track, str(self.out / f"{self.name}.{language}.srt")))
        return out

    def intro(self):
        """The opening animation the declaration names, when it is on disk (media
        is not versioned)."""
        from urdido.assemble.video import Intro

        opening = self.decl.get("opening", {})
        if not opening.get("intro") or not os.path.exists(self.path(opening["intro"])):
            return None
        meta = (
            self.load(opening["intro_meta"])
            if opening.get("intro_meta")
            and os.path.exists(self.path(opening["intro_meta"]))
            else {}
        )
        return Intro(self.path(opening["intro"]), meta.get("from", 0))

    def draw_cards(self, pages: Mapping[str, str], frame: html.Frame) -> None:
        """Each card's page and its pictures, beside the parts (`preview-` ones
        with --cards)."""
        from urdido.cards.render import render

        prefix = "preview-" if self.args.cards else ""
        named = {f"{prefix}{n}": p for n, p in pages.items()}
        for name, page in named.items():
            (self.parts / f"{name}.html").write_text(page, encoding="utf-8", newline="")
        render(named, frame, str(self.parts))
