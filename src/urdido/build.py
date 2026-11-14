"""`python -m videomaker build <video.toml>`: a product video built from its declaration (VM17).

    python -m videomaker build turing/wordpress/video.toml --language pt-BR [--project]
    python -m videomaker build turing/wordpress/video.toml --language pt-BR --cut chapter:2 [--vertical]
    python -m videomaker build turing/wordpress/developer.toml --language en
    python -m videomaker build shio/promo/video.toml --language pt-BR [--cut short:c1]
    ... --plan     stop once the timeline is decided, nothing encoded past it
    ... --cards    draw the cards alone, as previews, and stop

The declaration names the video's sources (one chaptered recording, or scene clips), its
narration, its cards' theme and words, its music, its cuts and where it publishes. Paths in it are
relative to its folder or start at a root: <plugin> (TURING_WORDPRESS), <recordings>
(STORY_RECORDINGS), <shio> (SHIO_REPO). The build writes into the folder's video/ (STORY_VIDEO_DIR).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Mapping

from videomaker import captions as cap
from videomaker import media
from videomaker.audio import mix
from videomaker.cards import html
from videomaker.jsnum import fixed
from videomaker.narration import Takes
from videomaker.sources import RecordingRefused, chaptered_recording
from videomaker.timeline import from_plan, pieces as pieces_of, plan as plan_of

TAB, NEWLINE = chr(9), chr(10)


class Build:
    def __init__(self, toml: Path, args: argparse.Namespace):
        self.here = toml.parent.resolve()
        with open(toml, "rb") as f:
            self.decl = tomllib.load(f)
        self.args = args
        env = os.environ.get
        self.roots = {
            "video": str(Path(env("STORY_VIDEO_DIR")).resolve()) if env("STORY_VIDEO_DIR") else str(self.here / "video"),
            "recordings": str(Path(env("STORY_RECORDINGS")).resolve()) if env("STORY_RECORDINGS") else str(self.here / "recordings"),
            "plugin": str(Path(env("TURING_WORDPRESS")).resolve()) if env("TURING_WORDPRESS")
            else str((self.here / ".." / ".." / ".." / "turing" / "latest" / "wordpress").resolve()),
            "root": str(self.here),
            "shio": str(Path(env("SHIO_REPO")).resolve()) if env("SHIO_REPO")
            else str((self.here / ".." / ".." / ".." / "shio" / "latest").resolve()),
        }
        self.out = Path(self.roots["video"])
        self.language = args.language
        video = self.decl["video"]
        self.name = video["name"]
        if self.language not in video["languages"]:
            raise SystemExit(f"videomaker build: {self.name} speaks {', '.join(video['languages'])}, not {self.language}")
        self.revision = None
        self.checked: list[str] = []
        revision = getattr(args, "revision", None) or video.get("revision")
        if revision and not (getattr(args, "plan", False) or getattr(args, "cards", False)):
            from videomaker.revisions import Revision

            cut = args.cut + ("-vertical" if args.vertical else "")
            self.revision = Revision(self.out, self.name, self.language, cut, revision)
            self.out = self.revision.folder
        self.parts = self.out / "parts"
        self.parts.mkdir(parents=True, exist_ok=True)

    # -- paths -----------------------------------------------------------------------------------

    def path(self, declared: str) -> str:
        for name, root in self.roots.items():
            if declared.startswith(f"<{name}>"):
                return os.path.normpath(declared.replace(f"<{name}>", root))
        return os.path.normpath(str(self.here / declared))

    def portable(self, text: str) -> str:
        """Paths named by the folder they are under, as story-video.mjs's plan writes them."""
        folders = sorted(((self.roots[k], f"<{k}>") for k in ("video", "recordings", "plugin", "root")),
                         key=lambda p: -len(p[0]))
        for folder, name in folders:
            text = text.replace(folder, name).replace(folder.replace("\\", "/"), name)
        return text.replace("\\", "/")

    def _portable_all(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.portable(value)
        if isinstance(value, dict):
            return {k: self._portable_all(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._portable_all(v) for v in value]
        return value

    def write_plan(self, name: str, data: Mapping) -> Path:
        from videomaker.timeline import _rounded

        file = self.parts / f"{name}.{self.language}.plan.json"
        text = json.dumps(_rounded(self._portable_all(dict(data))), ensure_ascii=False, indent=TAB) + NEWLINE
        file.write_text(text, encoding="utf-8", newline="")
        return file

    def checked_output(self, file: str, *, illustrated: bool = False) -> str:
        """VM39: no finished export is announced until its measured sidecar exists."""
        from videomaker.qa import report

        edit = self.load(str(self.parts / "illustrated" / "edit.json")) if illustrated else None
        highlights = self.load(self.decl["highlights"]["declaration"]) \
            if illustrated and self.decl.get("highlights") else None
        assets = self.load(self.decl["source"]["declaration"]).get("media", {}) if illustrated else None
        texts = [Path(self.path(self.decl["narration"]["script"]))]
        texts.extend(p for suffix in (".srt", ".vtt") if (p := Path(file).with_suffix(suffix)).exists())
        report(file, edit=edit, highlights=highlights, assets=assets, text_files=texts)
        self.checked.append(file)
        return file

    def translated_captions(self, placed) -> list[tuple[str, str]]:
        """The `[captions.translations.<language>]` the video declares (VM53): captions in a
        language it is not narrated in, timed sentence by sentence to the spoken takes. Writes
        `<name>.<language>.srt` and `.vtt`; returns (ISO 639-2 track code, srt path) per language."""
        out = []
        for language, spec in self.decl.get("captions", {}).get("translations", {}).items():
            table = self.load(spec["file"])
            cues = []
            for take in placed:
                audio = self.path(take["file"])
                stem = os.path.splitext(os.path.basename(audio))[0]
                if stem not in table:
                    raise SystemExit(f"captions.{language}: no translation for the take {stem}")
                with open(os.path.splitext(audio)[0] + ".words.json", encoding="utf-8") as f:
                    words = json.load(f)["words"]
                try:
                    cues += cap.translated_cues(take, words, table[stem])
                except ValueError as e:
                    raise SystemExit(f"captions.{language}, {stem}: {e}")
            for ext, text in (("srt", cap.srt(cues)), ("vtt", cap.vtt(cues))):
                (self.out / f"{self.name}.{language}.{ext}").write_text(text, encoding="utf-8", newline="")
            out.append((spec.get("track", language), str(self.out / f"{self.name}.{language}.srt")))
        return out

    def load(self, declared: str):
        with open(self.path(declared), encoding="utf-8") as f:
            return json.load(f)

    # -- the chaptered recording ----------------------------------------------------------------

    def chaptered(self) -> int:
        src = self.decl["source"]
        cut = self.args.cut
        clip = int(cut.split(":")[1]) if cut.startswith("chapter:") else None
        vertical = self.args.vertical
        if vertical and clip is None:
            raise SystemExit("videomaker build: --vertical cuts one chapter: add --cut chapter:<n>")
        folder = self.path(src["vertical_folder"] if vertical else src["folder"])
        command = src.get("vertical_record_command" if vertical else "record_command", "the recording")
        webm = os.path.join(folder, src["recording"])
        try:
            recording = chaptered_recording(
                webm, os.path.join(folder, "chapters.json"), language=self.language, chapters=src["chapters"],
                record_command=command, sources=[self.path(p) for p in src.get("newer_than", [])])
        except RecordingRefused as refused:
            raise SystemExit(f"videomaker build: {refused}")
        frame = html.Frame(1080, 1920) if vertical else html.Frame(1920, 1080)
        script = self.load(self.decl["narration"]["script"])
        takes = Takes(script, self.path(self.decl["narration"]["takes"]))
        cards = self.load(self.decl["cards"]["declaration"])
        theme = html.Theme.load(cards["theme"], {"turing": self.roots["plugin"], "shio": self.roots["shio"]})
        words = cards["words"][self.decl["cards"]["words"]]
        words = words.get(self.language, words.get("en"))
        chapters = [cap.Chapter(str(c.n), c.title) for c in recording.chapters]
        pages = html.pages(theme, frame, words, chapters, script, self.language, clip_chapter=clip)
        self.draw_cards(pages, frame)
        if self.args.cards:
            return 0
        bed_file = self.path(self.decl["music"]["bed"]) if "music" in self.decl else None
        bed = mix.Bed(bed_file) if bed_file and os.path.exists(bed_file) else None
        common = dict(
            name=self.name, language=self.language, voices=[self.language], frame=frame, vertical=vertical,
            webm=webm, chapters=recording.chapters, takes=takes, theme=theme,
            card_count=sum(1 for n in pages if n.startswith("card-") and n[5:].isdigit()),
            parts=str(self.parts), bed=bed, encoder=os.environ.get("STORY_ENCODER") or media.detect_encoder(),
        )
        from videomaker.cuts.render import Renderer

        titles = self.decl["video"]["title_languages"]
        tracks = {**titles, **self.decl["video"]["languages"]}
        if clip is not None:
            from videomaker.assemble.clip import ClipVideo

            video = ClipVideo(**common)
            builder, _ = video.build(clip)
            self.write_plan(builder.timeline.metadata["videomaker"]["video"][: -len(f".{self.language}")],
                            plan_of(builder.timeline))
            if self.args.plan:
                return 0
            renderer = Renderer(video, str(self.out), script, title_languages=list(titles),
                                track_languages=tracks, portable=self.portable)
            print(self.checked_output(renderer.clip(builder)))
            return 0

        from videomaker.assemble.video import FullVideo, Intro

        opening = self.decl.get("opening", {})
        intro = None
        if opening.get("intro") and os.path.exists(self.path(opening["intro"])):
            meta = self.load(opening["intro_meta"]) if opening.get("intro_meta") else {}
            intro = Intro(self.path(opening["intro"]), meta.get("from", 0))
        footage = sorted(str(p) for p in Path(self.path(opening["footage"])).glob("*.mp4")) \
            if opening.get("footage") and os.path.isdir(self.path(opening["footage"])) else []
        photos = [str(p) for d in opening.get("photos", []) if os.path.isdir(self.path(d))
                  for p in sorted(Path(self.path(d)).glob("*.webp"))]
        screens = self.screens(opening) if opening.get("store") else []
        broll = []
        for n in range(max(len(footage), len(photos), len(screens), 0)):
            for source in (footage[n] if n < len(footage) else None, photos[n] if n < len(photos) else None,
                           screens[n] if n < 3 and n < len(screens) else None):
                if source:
                    broll.append(source)
        video = FullVideo(**common, intro=intro, broll=broll, footage=footage)
        builder = video.compose()
        plan_file = self.write_plan(self.name, plan_of(builder.timeline))
        if self.args.plan:
            print(f"{plan_file}: the timeline, nothing encoded past it")
            return 0
        renderer = Renderer(video, str(self.out), script, title_languages=list(titles),
                            track_languages=tracks, write_plan=self.write_plan, portable=self.portable)
        made = renderer.full(builder, teaser=self.decl.get("cuts", {}).get("teaser", False))
        for file in made:
            self.checked_output(file)
        self.stills(video)
        if self.args.project:
            made.append(self.project(plan_file, webm))
        for file in made:
            print(file)
        return 0

    def intro(self):
        """The opening animation the declaration names, when it is on disk (media is not versioned)."""
        from videomaker.assemble.video import Intro

        opening = self.decl.get("opening", {})
        if not opening.get("intro") or not os.path.exists(self.path(opening["intro"])):
            return None
        meta = self.load(opening["intro_meta"]) if opening.get("intro_meta") and os.path.exists(
            self.path(opening["intro_meta"])) else {}
        return Intro(self.path(opening["intro"]), meta.get("from", 0))

    def draw_cards(self, pages: Mapping[str, str], frame: html.Frame) -> None:
        """Each card's page and its pictures, beside the parts (`preview-` ones with --cards)."""
        from videomaker.cards.render import render

        prefix = "preview-" if self.args.cards else ""
        named = {f"{prefix}{n}": p for n, p in pages.items()}
        for name, page in named.items():
            (self.parts / f"{name}.html").write_text(page, encoding="utf-8", newline="")
        render(named, frame, str(self.parts))

    def screens(self, opening: Mapping) -> list[str]:
        """The store pages the opening shows, kept in video/screens/<language>/ and reused until
        --refresh-screens; taken only when none are kept and the store answers."""
        kept = self.out / "screens" / self.language
        if not self.args.refresh_screens and kept.is_dir():
            files = sorted(str(p) for p in kept.glob("screen-*.png"))
            if files:
                return files
        store = os.environ.get("STORE_URL") or opening["store"].get(self.language)
        if not store or self.args.cut != "full":
            return []
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return []
        files: list[str] = []
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=os.environ.get("E2E_CHANNEL", "msedge"))
            page = browser.new_page(viewport={"width": 1920, "height": 1080})

            def shot(path: str, scroll: int = 0) -> None:
                try:
                    page.goto(store.rstrip("/") + path if path.startswith("/") else path, wait_until="networkidle")
                    page.evaluate("y => window.scrollTo(0, y)", scroll)
                    page.wait_for_timeout(400)
                    kept.mkdir(parents=True, exist_ok=True)
                    file = str(kept / f"screen-{len(files)}.png")
                    page.screenshot(path=file)
                    files.append(file)
                except Exception:  # a page the store does not have, or no store at all
                    pass

            shot("/")
            shot("/", 900)
            shot("/?post_type=product")
            try:
                product = page.locator('a.woocommerce-LoopProduct-link, .wc-block-components-product-name, '
                                       'a[href*="/product/"], a[href*="/produto/"]').first.get_attribute("href", timeout=3000)
            except Exception:
                product = None
            if product:
                shot(product)
            shot("/?pagename=journal")
            browser.close()
        return files

    def stills(self, video) -> None:
        """One still per chapter, its result on screen, published where publish.json says."""
        from videomaker.publish import publish_stills

        folder = self.out / "stills"
        folder.mkdir(exist_ok=True)
        written = []
        for i, chapter in enumerate(video.chapters):
            file = str(folder / f"chapter-{i + 1}.webp")
            media.ffmpeg(["-ss", fixed(video.best(chapter), 2), "-i", str(self.parts / f"chapter-{i + 1}.mp4"),
                          "-frames:v", "1", "-vf", "scale=1280:-1", "-c:v", "libwebp", "-quality", "80", file])
            written.append(file)
        if "publish" in self.decl:
            declared = self.load(self.decl["publish"]["declaration"]).get("stills")
            publish_stills(declared, written, self.name, self.language,
                           {"turing": str(Path(self.roots["plugin"]).parent)})

    def project(self, plan_file: Path, webm: str) -> str:
        """The Resolve project: the timeline handed over, read from the build's own plan (VM14)."""
        from videomaker.export.resolve import export_project

        resolve = self.load(self.decl["resolve"]["declaration"]) if "resolve" in self.decl else {}
        name = f"{self.name}.{self.language}"
        return export_project(
            from_plan(json.loads(plan_file.read_text(encoding="utf-8"))), str(self.out / f"{name}.project"), name,
            recording=self.portable(webm), captions=str(self.out / f"{self.name}.{self.language}.srt"),
            resolve=resolve, roots={k: self.roots[k] for k in ("video", "recordings", "plugin", "root")},
            encoder=os.environ.get("STORY_ENCODER") or media.detect_encoder(),
        )

    # -- scene by scene ---------------------------------------------------------------------------

    def scenes(self) -> int:
        from videomaker.assemble.scenes import ScenesVideo
        from videomaker.sources.scenes import scene_clips

        video_decl = self.decl["video"]
        folder = video_decl["folders"][self.language]
        script = self.load(self.decl["narration"]["script"])
        cards = self.load(self.decl["cards"]["declaration"])
        theme = html.Theme.load(cards["theme"], {"shio": self.roots["shio"], "root": str(self.here)})
        takes = Takes(script, self.path(self.decl["narration"]["takes"]))
        encoder = os.environ.get("STORY_ENCODER") or media.detect_encoder()
        illustrated = self.decl["source"]["kind"] == "illustrated"
        if illustrated:
            if self.args.cut != "full" or self.args.vertical or self.args.project or self.args.cards:
                raise SystemExit("illustrated videos currently support full cuts and --plan")
            from videomaker.sources.illustrated import scenes as illustrations

            document = self.load(self.decl["source"]["declaration"])
            source_scenes = illustrations(document, takes, theme, self.language, str(self.here),
                                         str(self.parts), render=not self.args.plan, encoder=encoder)
        else:
            listing = self.path(self.decl["source"]["listing"].replace("{folder}", folder))
            source_scenes = scene_clips(listing)
        video = ScenesVideo(
            name=self.name, language=self.language, frame=html.Frame(1920, 1080), scenes=source_scenes,
            takes=takes, script=script, theme=theme,
            words=cards["words"][self.language], parts=str(self.parts),
            encoder=encoder, intro=self.intro(),
        )
        cut = self.args.cut
        if cut.startswith("short:"):
            from videomaker.cuts.selection import selection

            shorts = self.load(self.decl["shorts"]["declaration"])
            key = cut.split(":", 1)[1].lower()
            short = selection(video, key, shorts["cuts"][key]["chapters"], self.path(shorts["music"]),
                              str(self.out), limit=shorts.get("limit", 60),
                              track_language=video_decl["languages"][self.language])
            self.checked_output(short.file)
            print(f"{short.file}: {short.length:.1f} s" + (f", {short.over:.1f} s over its {short.limit:g} s" if short.over else ""))
            return 0
        timeline = video.compose(render=not self.args.plan)
        self.write_plan(self.name, plan_of(timeline))
        if illustrated:
            from videomaker.sources.illustrated import description
            from videomaker.keywords import cues as highlight_cues
            from videomaker.labels import check as check_labels

            description(document, script, plan_of(timeline), self.language, self.out, self.name)
            highlights = highlight_cues(plan_of(timeline)["spoken"].get(self.language, []),
                                        self.load(self.decl["highlights"]["declaration"])["lines"]) \
                if self.decl.get("highlights") else []
            edit = self.load(str(self.parts / "illustrated" / "edit.json"))
            check_labels(document, edit, highlights, video.opening)
        if self.args.plan:
            if illustrated:
                from videomaker.review import sheet

                print(sheet(document, edit,
                            plan_of(timeline)["spoken"].get(self.language, []), highlights,
                            self.here, self.parts, self.out, opening=video.opening))
            return 0
        pieces = pieces_of(timeline)
        joined = video.media.concat(pieces, f"{self.name}-joined.mp4")
        total = media.seconds(joined)
        placed = plan_of(timeline)["spoken"].get(self.language, [])
        if self.decl.get("highlights"):
            from videomaker.keywords import overlay

            joined = overlay(joined, placed, self.load(self.decl["highlights"]["declaration"]),
                             self.parts, self.path(self.decl["highlights"]["fonts"]), encoder)
        cues = cap.narration_cues(placed)
        for ext, text in (("srt", cap.srt(cues)), ("vtt", cap.vtt(cues))):
            (self.out / f"{self.name}.{self.language}.{ext}").write_text(text, encoding="utf-8", newline="")
        extra = self.translated_captions(placed)
        voice = str(self.parts / f"voice.{self.language}.m4a")
        music = self.decl["music"]
        bed = self.path(music["bed"])
        sounds = [mix.Sound(video.intro.file, video.intro.start, 0.0, video.opening)] if video.intro else []
        # A narrated explainer may want its bed quieter than the default (VM38): `reference` is the
        # bed's LUFS before the duck, `between` / `under` its gain beside and under the voice.
        duck = mix.Duck(**{k: music[k] for k in ("between", "under", "ramp") if k in music})
        mix.voice_track([mix.Take(p["file"], p["at"], p["length"]) for p in placed], total, voice, str(self.parts),
                        sounds=sounds,
                        bed=mix.Bed(bed, video.opening, music.get("reference", -18.0)) if os.path.exists(bed) else None,
                        loudness=mix.Loudness(**self.decl.get("audio", {})), duck=duck,
                        name=f"mix.{self.language}")
        file = str(self.out / f"{self.name}.{self.language}.mp4")
        lang = video_decl["languages"][self.language]
        media.ffmpeg(["-i", joined, "-i", str(self.out / f"{self.name}.{self.language}.srt"), "-i", voice,
                      *[a for _, srt in extra for a in ("-i", srt)],
                      "-map", "0:v", "-map", "2:a", "-map", "1",
                      *[a for i in range(len(extra)) for a in ("-map", str(3 + i))],
                      "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                      "-c:s", "mov_text", "-metadata:s:v:0", "language=und", "-metadata:s:a:0", f"language={lang}",
                      "-metadata:s:s:0", f"language={lang}",
                      *[a for i, (track, _) in enumerate(extra) for a in (f"-metadata:s:s:{i + 1}", f"language={track}")],
                      file])
        print(self.checked_output(file, illustrated=illustrated))
        return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m videomaker build", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("declaration", help="the video's .toml")
    p.add_argument("--language", required=True, help="the video's language, as its narration names it")
    p.add_argument("--cut", default="full", help="full, chapter:<n> or short:<c>")
    p.add_argument("--vertical", action="store_true", help="the 9:16 cut of a chapter, from its own recording")
    p.add_argument("--project", action="store_true", help="also the DaVinci Resolve project")
    p.add_argument("--cards", action="store_true", help="draw the cards alone, as previews, and stop")
    p.add_argument("--plan", action="store_true", help="stop once the timeline is decided")
    p.add_argument("--refresh-screens", action="store_true", help="take the store's pages again")
    p.add_argument("--revision", help="keep an immutable package under this revision (overrides video.revision)")
    a = p.parse_args(argv)
    build = Build(Path(a.declaration), a)
    kind = build.decl["source"]["kind"]
    result = build.chaptered() if kind == "chaptered" else build.scenes()
    if result == 0 and build.revision:
        print(build.revision.complete(build.checked))
    return result
