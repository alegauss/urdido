"""The scenes pipeline: scene clips or illustrated beats, each fitted to its line, with
its mix (UR33)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from urdido import cache, media
from urdido import captions as cap
from urdido.audio import mix
from urdido.cards import html
from urdido.errors import DeclarationError, Refused
from urdido.narration import Takes
from urdido.pipelines.finishing import Finishing
from urdido.timeline import pieces as pieces_of
from urdido.timeline import plan as plan_of


class Scenes(Finishing):
    """The scenes pipeline."""

    def scenes(self) -> int:
        from urdido.assemble.scenes import ScenesVideo
        from urdido.sources.scenes import scene_clips

        video_decl = self.decl["video"]
        folder = video_decl["folders"][self.language]
        illustrated = self.decl["source"]["kind"] == "illustrated"
        if illustrated:
            from urdido import progress
            from urdido.preflight import illustrated as preflight

            progress.plan("validation", 1)
            with progress.unit("validation", f"{self.name}.{self.language}"):
                script, cards, document = preflight(self)
            from urdido.repetition import publish

            publish(
                self.repetition_report,
                self.parts / f"{self.name}.{self.language}.repetition.json",
            )
            from urdido.pauses import publish as publish_pauses

            publish_pauses(
                self.pause_report,
                self.parts / f"{self.name}.{self.language}.pauses.json",
            )
            if "_claims_report" in document:
                from urdido.claims import publish as publish_claims

                publish_claims(
                    document["_claims_report"],
                    self.out / f"{self.name}.{self.language}.claims.html",
                )
        else:
            script = self.load(self.decl["narration"]["script"])
            cards = self.load(self.decl["cards"]["declaration"])
        theme = html.Theme.load(cards["theme"], self.roots)
        takes = Takes(
            script,
            self.path(self.decl["narration"]["takes"]),
            self.decl["narration"].get("tempo", 1.0),
        )
        encoder = os.environ.get("STORY_ENCODER") or (
            "x264" if self.args.cards or self.args.plan else media.detect_encoder()
        )
        if illustrated:
            if self.args.cut != "full" or self.args.vertical or self.args.project:
                raise Refused(
                    "illustrated videos support full cuts, cards, plans and motion "
                    "previews"
                )
            if self.args.cards and (
                self.args.plan or getattr(self.args, "preview", None)
            ):
                raise Refused("use --cards separately from --plan or --preview")
            from urdido.sources.illustrated import scenes as illustrations

            if getattr(self.args, "preview", None):
                from urdido.preview import render

                return render(self, document, script, cards, theme, takes, encoder)
            source_scenes = illustrations(
                document,
                takes,
                theme,
                self.language,
                str(self.here),
                str(self.parts),
                render=not self.args.plan,
                encoder=encoder,
                cards_only=self.args.cards,
                frame=self.frame(),
            )
            if self.args.cards:
                print(
                    "illustrated layers checked: "
                    f"{self.parts / 'illustrated/text-checks.json'}"
                )
                return 0
        else:
            listing = self.path(
                self.decl["source"]["listing"].replace("{folder}", folder)
            )
            source_scenes = scene_clips(listing)
        video = ScenesVideo(
            name=self.name,
            language=self.language,
            frame=self.frame(),
            scenes=source_scenes,
            takes=takes,
            script=script,
            theme=theme,
            words=cards["words"][self.language],
            parts=str(self.parts),
            encoder=encoder,
            intro=self.intro(),
            anchors=self.decl.get("anchors") or {},
        )
        cut = self.args.cut
        if cut.startswith("short:"):
            from urdido.cuts.selection import selection

            shorts = self.load(self.decl["shorts"]["declaration"])
            key = cut.split(":", 1)[1].lower()
            short = selection(
                video,
                key,
                shorts["cuts"][key]["chapters"],
                self.path(shorts["music"]),
                str(self.out),
                limit=shorts.get("limit", 60),
                track_language=video_decl["languages"][self.language],
            )
            self.checked_output(short.file)
            print(
                f"{short.file}: {short.length:.1f} s"
                + (
                    f", {short.over:.1f} s over its {short.limit:g} s"
                    if short.over
                    else ""
                )
            )
            return 0
        timeline = video.compose(render=not self.args.plan)
        self.write_plan(self.name, plan_of(timeline))
        highlights = []
        if self.decl.get("highlights"):
            from urdido.keywords import aliases as declared_aliases
            from urdido.keywords import cues as highlight_cues
            from urdido.safety import highlights as safe_highlights

            highlight_decl = self.load(self.decl["highlights"]["declaration"])
            highlights = highlight_cues(
                plan_of(timeline)["spoken"].get(self.language, []),
                highlight_decl["lines"],
                aliases=declared_aliases(script, self.language),
            )
            safe_highlights(
                highlight_decl["style"],
                highlights,
                self.parts / "highlights.safe-area.json",
            )
        if illustrated:
            from urdido.labels import check as check_labels
            from urdido.sources.illustrated import description

            description(
                document,
                script,
                plan_of(timeline),
                self.language,
                self.out,
                self.name,
                self.decl.get("description"),
            )
            edit = self.load(str(self.parts / "illustrated" / "edit.json"))
            check_labels(document, edit, highlights, video.opening)
        elif self.decl.get("description"):
            from urdido.publish.description import scenes as scenes_description
            from urdido.publish.description import write as write_description

            text, provenance = scenes_description(
                script, plan_of(timeline), self.language, self.decl["description"]
            )
            write_description(
                self.out, f"{self.name}.{self.language}", text, provenance
            )
        if self.args.plan:
            if illustrated:
                from urdido.review import sheet

                print(
                    sheet(
                        document,
                        edit,
                        plan_of(timeline)["spoken"].get(self.language, []),
                        highlights,
                        self.here,
                        self.parts,
                        self.out,
                        opening=video.opening,
                    )
                )
            return 0
        pieces = pieces_of(timeline)
        from urdido import progress

        progress.plan("join", 1)
        joined = video.media.concat(pieces, f"{self.name}-joined.mp4")
        total = media.seconds(joined)
        placed = plan_of(timeline)["spoken"].get(self.language, [])
        if (self.decl.get("captions") or {}).get("burn") and not self.decl.get(
            "highlights"
        ):
            raise DeclarationError(
                "urdido build: [captions] burn draws in the highlights' pass; "
                "declare [highlights] "
                "(its lines may be empty) for its fonts"
            )
        if self.decl.get("highlights"):
            from urdido.keywords import aliases as declared_aliases
            from urdido.keywords import overlay

            joined = overlay(
                joined,
                placed,
                self.load(self.decl["highlights"]["declaration"]),
                self.parts,
                self.path(self.decl["highlights"]["fonts"]),
                encoder,
                aliases=declared_aliases(script, self.language),
                frame=self.frame(),
                burn=(self.decl.get("captions") or {}).get("burn"),
            )
        if self.decl.get("mark"):
            from urdido import mark

            joined = mark.overlay(
                joined,
                mark.declared(self.decl["mark"], self.path),
                self.parts,
                encoder,
                self.frame().height,
            )
        cues = cap.narration_cues(placed)
        for ext, text in (("srt", cap.srt(cues)), ("vtt", cap.vtt(cues))):
            (self.out / f"{self.name}.{self.language}.{ext}").write_text(
                text, encoding="utf-8", newline=""
            )
        extra = self.translated_captions(placed)
        voice = self.scene_voice(video, placed, total)
        file = str(self.out / f"{self.name}.{self.language}.mp4")
        lang = video_decl["languages"][self.language]
        mux_args = [
            "-i",
            joined,
            "-i",
            str(self.out / f"{self.name}.{self.language}.srt"),
            "-i",
            voice,
            *[a for _, srt in extra for a in ("-i", srt)],
            "-map",
            "0:v",
            "-map",
            "2:a",
            "-map",
            "1",
            *[a for i in range(len(extra)) for a in ("-map", str(3 + i))],
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-c:s",
            "mov_text",
            "-metadata:s:v:0",
            "language=und",
            "-metadata:s:a:0",
            f"language={lang}",
            "-metadata:s:s:0",
            f"language={lang}",
            *[
                a
                for i, (track, _) in enumerate(extra)
                for a in (f"-metadata:s:s:{i + 1}", f"language={track}")
            ],
            file,
        ]
        mux_inputs = [mux_args[i + 1] for i, arg in enumerate(mux_args) if arg == "-i"]
        cache.run(
            "final mux",
            [file],
            mux_args,
            lambda: media.ffmpeg(mux_args),
            inputs=[__file__, media.__file__, *mux_inputs],
            tools=["ffmpeg"],
        )
        clips, at = [], 0.0
        for row in plan_of(timeline)["pieces"]:
            if "track" not in row:
                clips.append(
                    {"file": row["file"], "start": at, "end": at + row["length"]}
                )
                at += row["length"]
        print(self.checked_output(file, illustrated=illustrated, clips=clips))
        if not illustrated:
            from urdido.review import scene_sheet

            thumbnail = (self.decl.get("thumbnail") or {}).get(
                "out", "video/thumbnail.{language}.jpg"
            )
            print(
                scene_sheet(
                    Path(file),
                    placed,
                    script,
                    self.language,
                    self.out,
                    self.here / thumbnail.format(language=self.language),
                )
            )
        return 0

    def beat_sounds(self, opening: float) -> list:
        """The illustrated beats that play their clip's own sound, where they sit on
        the timeline (VM78): the edit records each one's clip and the second its
        picture starts from."""
        edit = self.parts / "illustrated" / "edit.json"
        if not edit.exists():
            return []
        beats = json.loads(edit.read_text(encoding="utf-8"))["beats"]
        return [
            mix.Sound(
                b["sound"]["file"],
                float(b["sound"]["source_at"]),
                opening + b["at"],
                b["seconds"],
                float(b["sound"].get("gain_db", 0.0)),
            )
            for b in beats
            if b.get("sound")
        ]

    def scene_voice(self, video, placed, total):
        """Use the full production mix even when VM57 reviews only a short interval."""
        voice = str(self.parts / f"voice.{self.language}.m4a")
        music = self.decl["music"]
        bed = self.path(music["bed"])
        sounds = (
            [mix.Sound(video.intro.file, video.intro.start, 0.0, video.opening)]
            if video.intro
            else []
        )
        sounds += self.beat_sounds(getattr(video, "opening", 0) or 0)
        # A narrated explainer may want its bed quieter than the default (VM38):
        # `reference` is the bed's LUFS before the duck, `between` / `under` its gain
        # beside and under the voice.
        duck = mix.Duck(
            **{k: music[k] for k in ("between", "under", "ramp") if k in music}
        )
        mix.voice_track(
            [mix.Take(p["file"], p["at"], p["length"]) for p in placed],
            total,
            voice,
            str(self.parts),
            sounds=sounds,
            bed=mix.Bed(bed, video.opening, music.get("reference", -18.0))
            if os.path.exists(bed)
            else None,
            loudness=mix.Loudness(**self.decl.get("audio", {})),
            duck=duck,
            name=f"mix.{self.language}",
        )
        return voice
