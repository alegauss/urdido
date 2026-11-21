"""The chaptered pipeline: one recording cut into chapters, its cards, its opening
screens, its stills and its Resolve project (UR33)."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

from urdido import captions as cap
from urdido import media
from urdido.audio import mix
from urdido.cards import html
from urdido.errors import DeclarationError, Refused
from urdido.jsnum import fixed
from urdido.narration import Takes
from urdido.pipelines.finishing import Finishing
from urdido.sources import RecordingRefused, chaptered_recording
from urdido.timeline import from_plan
from urdido.timeline import plan as plan_of


class Chaptered(Finishing):
    """The chaptered pipeline."""

    def chaptered(self) -> int:
        src = self.decl["source"]
        cut = self.args.cut
        clip = int(cut.split(":")[1]) if cut.startswith("chapter:") else None
        vertical = self.args.vertical
        if vertical and clip is None:
            raise Refused(
                "urdido build: --vertical cuts one chapter: add --cut chapter:<n>"
            )
        folder = self.path(src["vertical_folder"] if vertical else src["folder"])
        command = src.get(
            "vertical_record_command" if vertical else "record_command", "the recording"
        )
        webm = os.path.join(folder, src["recording"])
        try:
            recording = chaptered_recording(
                webm,
                os.path.join(folder, "chapters.json"),
                language=self.language,
                chapters=src["chapters"],
                record_command=command,
                sources=[self.path(p) for p in src.get("newer_than", [])],
            )
        except RecordingRefused as refused:
            raise Refused(f"urdido build: {refused}") from refused
        frame = html.Frame(1080, 1920) if vertical else html.Frame(1920, 1080)
        script = self.load(self.decl["narration"]["script"])
        takes = Takes(
            script,
            self.path(self.decl["narration"]["takes"]),
            self.decl["narration"].get("tempo", 1.0),
        )
        cards = self.load(self.decl["cards"]["declaration"])
        theme = html.Theme.load(cards["theme"], self.roots)
        words = cards["words"][self.decl["cards"]["words"]]
        words = words.get(self.language, words.get("en"))
        chapters = [cap.Chapter(str(c.n), c.title) for c in recording.chapters]
        pages = html.pages(
            theme, frame, words, chapters, script, self.language, clip_chapter=clip
        )
        self.draw_cards(pages, frame)
        if self.args.cards:
            return 0
        bed_file = (
            self.path(self.decl["music"]["bed"]) if "music" in self.decl else None
        )
        bed = mix.Bed(bed_file) if bed_file and os.path.exists(bed_file) else None
        common = dict(
            name=self.name,
            language=self.language,
            voices=[self.language],
            frame=frame,
            vertical=vertical,
            webm=webm,
            chapters=recording.chapters,
            takes=takes,
            theme=theme,
            card_count=sum(
                1 for n in pages if n.startswith("card-") and n[5:].isdigit()
            ),
            parts=str(self.parts),
            bed=bed,
            encoder=os.environ.get("STORY_ENCODER") or media.detect_encoder(),
        )
        from urdido.cuts.render import Renderer

        titles = self.decl["video"]["title_languages"]
        tracks = {**titles, **self.decl["video"]["languages"]}
        if clip is not None:
            from urdido.assemble.clip import ClipVideo

            video = ClipVideo(**common)
            builder, _ = video.build(clip)
            self.write_plan(
                builder.timeline.metadata["videomaker"]["video"][
                    : -len(f".{self.language}")
                ],
                plan_of(builder.timeline),
            )
            if self.args.plan:
                return 0
            renderer = Renderer(
                video,
                str(self.out),
                script,
                title_languages=list(titles),
                track_languages=tracks,
                portable=self.portable,
            )
            print(self.checked_output(renderer.clip(builder)))
            return 0

        from urdido.assemble.video import FullVideo, Intro

        opening = self.decl.get("opening", {})
        intro = None
        if opening.get("intro") and os.path.exists(self.path(opening["intro"])):
            meta = self.load(opening["intro_meta"]) if opening.get("intro_meta") else {}
            intro = Intro(self.path(opening["intro"]), meta.get("from", 0))
        footage = (
            sorted(str(p) for p in Path(self.path(opening["footage"])).glob("*.mp4"))
            if opening.get("footage") and os.path.isdir(self.path(opening["footage"]))
            else []
        )
        photos = [
            str(p)
            for d in opening.get("photos", [])
            if os.path.isdir(self.path(d))
            for p in sorted(Path(self.path(d)).glob("*.webp"))
        ]
        screens = self.screens(opening) if opening.get("store") else []
        broll = []
        for n in range(max(len(footage), len(photos), len(screens), 0)):
            for source in (
                footage[n] if n < len(footage) else None,
                photos[n] if n < len(photos) else None,
                screens[n] if n < 3 and n < len(screens) else None,
            ):
                if source:
                    broll.append(source)
        video = FullVideo(**common, intro=intro, broll=broll, footage=footage)
        builder = video.compose()
        plan_file = self.write_plan(self.name, plan_of(builder.timeline))
        if self.args.plan:
            print(f"{plan_file}: the timeline, nothing encoded past it")
            return 0
        renderer = Renderer(
            video,
            str(self.out),
            script,
            title_languages=list(titles),
            track_languages=tracks,
            write_plan=self.write_plan,
            portable=self.portable,
        )
        made = renderer.full(
            builder, teaser=self.decl.get("cuts", {}).get("teaser", False)
        )
        for file in made:
            self.checked_output(file)
        self.stills(video)
        if self.args.project:
            made.append(self.project(plan_file, webm))
        for file in made:
            print(file)
        return 0

    def screens(self, opening: Mapping) -> list[str]:
        """The site pages the opening shows, kept in video/screens/<language>/ and
        reused until
        --refresh-screens; taken only when none are kept and the site answers.

        Which pages, in order, is the declaration's (UR28): `[opening] screens` is a
        list of
        `{ path = "/", scroll = 900 }` (a page of the site, scrolled) or
        `{ follow = "<css selector>" }` (the first link the selector finds on the
        page before)."""
        kept = self.out / "screens" / self.language
        if not self.args.refresh_screens and kept.is_dir():
            files = sorted(str(p) for p in kept.glob("screen-*.png"))
            if files:
                return files
        store = os.environ.get("STORE_URL") or opening["store"].get(self.language)
        if not store or self.args.cut != "full":
            return []
        steps = opening.get("screens")
        if not steps:
            raise DeclarationError(
                "urdido build: [opening] store has no screens to take; declare "
                '[opening] screens = [{ path = "/" }, { follow = "a.product" }, ...]'
            )
        if not all(
            isinstance(s, dict) and (("path" in s) != ("follow" in s)) for s in steps
        ):
            raise DeclarationError(
                "urdido build: each [opening] screens entry is a path (with an "
                "optional "
                "scroll) or a follow selector"
            )
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return []
        files: list[str] = []
        with sync_playwright() as p:
            from urdido.cards.render import browser_channel

            browser = p.chromium.launch(channel=browser_channel())
            page = browser.new_page(viewport={"width": 1920, "height": 1080})

            def shot(path: str, scroll: int = 0) -> None:
                try:
                    page.goto(
                        store.rstrip("/") + path if path.startswith("/") else path,
                        wait_until="networkidle",
                    )
                    page.evaluate("y => window.scrollTo(0, y)", scroll)
                    page.wait_for_timeout(400)
                    kept.mkdir(parents=True, exist_ok=True)
                    file = str(kept / f"screen-{len(files)}.png")
                    page.screenshot(path=file)
                    files.append(file)
                except Exception:  # a page the store does not have, or no store at all
                    pass

            for step in steps:
                if "path" in step:
                    shot(step["path"], step.get("scroll", 0))
                    continue
                try:
                    link = page.locator(step["follow"]).first.get_attribute(
                        "href", timeout=3000
                    )
                except Exception:  # nothing on the page before matches
                    link = None
                if link:
                    shot(link, step.get("scroll", 0))
            browser.close()
        return files

    def stills(self, video) -> None:
        """One still per chapter, its result on screen, published where
        publish.json says."""
        from urdido.publish import publish_stills

        folder = self.out / "stills"
        folder.mkdir(exist_ok=True)
        written = []
        for i, chapter in enumerate(video.chapters):
            file = str(folder / f"chapter-{i + 1}.webp")
            media.ffmpeg(
                [
                    "-ss",
                    fixed(video.best(chapter), 2),
                    "-i",
                    str(self.parts / f"chapter-{i + 1}.mp4"),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=1280:-1",
                    "-c:v",
                    "libwebp",
                    "-quality",
                    "80",
                    file,
                ]
            )
            written.append(file)
        if "publish" in self.decl:
            declared = self.load(self.decl["publish"]["declaration"]).get("stills")
            publish_stills(declared, written, self.name, self.language, self.roots)

    def project(self, plan_file: Path, webm: str) -> str:
        """The Resolve project: the timeline handed over, read from the build's own
        plan (VM14)."""
        from urdido.export.resolve import export_project

        resolve = (
            self.load(self.decl["resolve"]["declaration"])
            if "resolve" in self.decl
            else {}
        )
        name = f"{self.name}.{self.language}"
        return export_project(
            from_plan(json.loads(plan_file.read_text(encoding="utf-8"))),
            str(self.out / f"{name}.project"),
            name,
            recording=self.portable(webm),
            captions=str(self.out / f"{self.name}.{self.language}.srt"),
            resolve=resolve,
            roots=dict(self.roots),
            encoder=os.environ.get("STORY_ENCODER") or media.detect_encoder(),
        )
