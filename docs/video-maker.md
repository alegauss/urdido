# video-maker

The framework every product video in this repository is built with: the Viglet Turing
WordPress demo (`../turing/wordpress`), the Viglet Shio promo (`../shio/promo`) and the ones
after them. A video declares what it is (its narration, its scenes, its theme, its cuts); the
framework records, voices and assembles it.

A video is a declaration (`turing/wordpress/video.toml`, `developer.toml`,
`shio/promo/video.toml`) built by one command:

    python -m pip install -e "video-maker[test,cards]"     # once
    python -m videomaker build turing/wordpress/video.toml --language pt-BR [--project]
    python -m videomaker build turing/wordpress/video.toml --language pt-BR --cut chapter:2 [--vertical]
    python -m videomaker build shio/promo/video.toml --language pt-BR [--cut short:c1]

It grew out of the WordPress demo's 2,900-line assembly script, one module at a time, each step
keeping that video's output the same, until the script was removed (VM17). Recording stays
JavaScript; the assembly is the `videomaker` package. The plan was Block B of
`../docs/ROADMAP.md`.

## What is here today

| Module | What it does | Used by |
|---|---|---|
| `narration/takes.mjs` | A narration's script, its lines, where each take lives, what the voice says (`pronounce`), the captions' text, and whether a take is current | both videos' `bin/narration-takes.mjs` |
| `narration/buy.mjs` | Buys the takes through polyweave's `voice.lines`: plans, spends inside the budget, skips current takes | both videos' `bin/story-narration.mjs` |
| `story-moves.mjs` | A visible pointer a headless recording would leave out, a quick hand-like move to what is clicked, a slow eased scroll | `shio/promo/bin/story-scenes.mjs` |
| `recording/seconds.mjs` | A media file's length, for the recording side (the narration reader, the scene listings) | `narration/takes.mjs`, `shio/promo/bin/cenas.mjs` |
| `terminal-replay.mjs` | A Claude Code session replayed as a terminal scene from its own `stream-json` record: every line is real, nothing is staged. A video declares each chapter's lines as selectors (`chooseLines`: tools, kinds, patterns, first or last). `initLine` opens a chapter on the session's own start, showing the one declared plugin and nothing else of the machine | `shio/promo/bin/story-terminal.mjs`, from `shio/promo/demo/agent/terminal.json` |
| `videomaker/build.py` | `python -m videomaker build <video.toml>`: reads the declaration and builds the full cut, the teaser, a chapter clip or its vertical cut, a scene-by-scene video or its shorts, the Resolve project, the stills and the transcript; `--plan` stops at the timeline, `--cards` draws the cards alone | `npm run story:video` in both videos |
| `videomaker/media.py` | ffmpeg run quietly or in a bounded pool, the encoder (NVENC or x264, a keyframe each half second), a file's length, a mix's loudness, and per video context the cuts, held frames and joins; `tests/test_media.py` holds it to the arguments the JS built (`tests/oracles/`) | every module below |
| `videomaker/captions.py` | Narration captions (SRT, VTT), a silent cut's chapter-title captions and the YouTube chapter list, in any language the video declares. Titles come from the script's `chapters[n].title` and `introTitle`, and otherwise from the recording's step titles | `videomaker/build.py` |
| `videomaker/cards/` | The card pages (`html.py`: the opening, chapter and closing cards, the backdrop and the two ranges of hills, and the parallax that slides them) in a declared theme, drawn by Playwright for Python (`render.py`). The module holds the layout only. The theme and words are each video's `demo/cards.json`, Tarnfell for the WordPress demo and Quilhara for Viglet Shio | `videomaker/build.py` |
| `videomaker/sources/` | The chapter model the timeline consumes (`Chapter`: number, title, clip, marks, pacing) and `chaptered_recording`, which reads a `chapters.json` as Turing's specs write it and refuses it as the JS does: no recording, another language, a test run, a missing chapter, a story newer than the recording. A focus mark without a box is a release | `videomaker/build.py` |
| `videomaker/motion/pushin.py`, `videomaker/edit/stretch.py` | The push-in that follows the action and the time maps that cut a chapter's marked waits, as pure functions of the frame and the marks, equal to the JS they replaced for every chapter of the fixtures (`tests/oracles/motion.json`, frozen from the JS before it was removed) | `videomaker/build.py` |
| `videomaker/timeline.py` | The timeline as an OpenTimelineIO `Timeline`. Lanes V1 (recording, held frames), V2 (cards) and V3 (shots) are video tracks; each language's takes, the sounds and the bed are audio tracks; chapters are markers, and the encoded file, stills, chapter and dissolves ride in clip metadata. A `Builder` places pieces one after another, `plan()` derives VM1's plan JSON, and `.otio` files round-trip | `videomaker/assemble` |
| `videomaker/narration.py` | Reads a narration's takes as `narration/takes.mjs` does: each line's take, whether it is current (its provenance records the same spoken text, voice and model), and its length | `videomaker/assemble` |
| `videomaker/assemble/clip.py` | One chapter as a clip of its own, composed on the timeline from the chapter model, the cards, the takes and the bed, with real encodes. `tests/test_assemble_clip.py` builds chapter 2 and its vertical cut as the golden runner does and gets the golden plans | `videomaker/build.py` |
| `videomaker/assemble/video.py` | A full video on the timeline: the opening animation and its sound, title cards with shots cut at the narrator's pauses, each chapter's card and clip with its waits cut and its result held, the closing, the dissolves, and the push-ins and time maps as clip effects. Its work folder is the caller's, so two builds can each have their own. `tests/test_assemble_video.py` builds the English and Portuguese story and the developer walkthrough into their golden plans; it encodes for minutes, so it runs with `VIDEO_MAKER_FULL=1` | `videomaker/build.py` |
| `videomaker/cuts/render.py` | Renders a composed video's cuts through one path: the full cut with its dissolves (only the blended half second encoded again), the 30 s teaser when the video declares one, a chapter clip, and its vertical cut with the captions burned in. Each narrated language is mixed over the bed, and the captions are muxed beside the voice. `tests/test_cuts.py` renders the six variants into the golden `outputs.txt`, captions and chapter lists (`VIDEO_MAKER_FULL=1`) | `videomaker/build.py` |
| `videomaker/sources/scenes.py`, `videomaker/edit/pacing.py`, `videomaker/assemble/scenes.py` | A video filmed scene by scene: `cenas.json` read into scenes (each clip measured from the file; `filmed: false` kept as such), `fit_to_line` (a short clip holds its last frame, a long one plays faster as a whole, nothing cut), and the composition with every line over its own scene as an OTIO clip with a time warp, or over a card held in the video's theme while the scene is unfilmed | the Viglet Shio promo (VM20) |
| `videomaker/cuts/selection.py` | A short 9:16 cut made of chosen chapters of the 16:9 scenes: the long cut's scenes fitted to their lines, cropped to their centre (no focus box yet, VM16), cards drawn upright, captions burned in above the bottom fifth, and the voice over the short's own bed. Over its limit, it tightens the breaths and reports what is left over | the Viglet Shio shorts (`shio/promo/demo/shorts.json`, VM20) |
| `videomaker/export/` | The DaVinci Resolve project: the `.otio` timeline handed over (it is the video's source of truth; Resolve receives a copy), beside a `media/` folder that holds every file it points at, the recording transcoded to H.264, the bed as one looped clip on A2, the captions and `finish.lua`. `python -m videomaker.export` makes it from a build's plan, as `--project` does. Resolve does not read the push-in and time-map effects or the bed's ducking; that is a limit of the copy, and an edit there starts from the cut as rendered | `videomaker/build.py --project` |
| `videomaker/publish/` | Publishes outside the video only where its `publish.json` says: the narration's transcript (a TypeScript module and a block between markers in a docs page, per language) and the chapter stills (for the declared story and language). `python -m videomaker.publish transcript` is what `npm run transcript` runs. The WordPress build also keeps the store pages it shows in `video/screens/<language>/` and reuses them until `--refresh-screens`, so it gives the same video whether or not the store is up | `turing/wordpress/bin/transcript.mjs`, `videomaker/build.py` |
| `videomaker/audio/mix.py` | One language's narration over the music bed: the duck, the bed's trim to a reference level, sounds that come with the picture, and an iterated limiter to the loudness target. Every level is an argument, and the defaults are the WordPress demo's | `videomaker/build.py` |

## The Python assembly

`python -m videomaker storyboard inspect <storyboard.json>` prints the current
SHA-256 and beat IDs (VM46). On a legacy storyboard, run `storyboard assign-ids`
with `--expected-sha256 <hash>` once. IDs stay with their beats through later
insertions and moves. Add `--dry-run` to preview any edit without writing.

`storyboard edit <storyboard.json> --expected-sha256 <hash> --operations <edits.json>`
accepts an array of operations:

```json
[
  {"op": "set", "beat": "existing-id", "values": {"asset": "new-media", "seconds": 3}},
  {"op": "insert", "take": "intro", "after": "existing-id", "value": {"id": "new-id", "title": "New beat", "source": "source-key"}},
  {"op": "move", "beat": "new-id", "take": "intro"},
  {"op": "media", "key": "new-media", "values": {"author": "Source author"}},
  {"op": "credits", "value": "Updated credits"}
]
```

`remove` takes a `beat` ID. An omitted `after` inserts or moves to the start of
the take. Writes preserve UTF-8, key order, line endings and unrelated values,
refuse stale input and use an exclusive edit marker plus an atomic replacement.
The command prints a diff and the resulting hash. A build prints the SHA-256
of each declaration it reads and saves them in `parts/<name>.<language>.inputs.json`;
a declaration changed during that build prevents success.

Illustrated storyboards accept `brand_mark` on a beat, media asset or document,
in that order of precedence (VM45). Choose `top-left` (the default),
`top-right`, `bottom-left`, `bottom-right`, or `none`. The position applies
to both overlay layers, so a timed caption leaving the frame cannot restore
a hidden mark. The WordPress storyboard hides the mark on recorded web pages
to leave their own headings readable.

`python -m videomaker instance plan <video.toml> <name>` shows a declared
product fixture without running Docker (VM44). `[instances.<name>]` names
`compose`, `url`, optional `ready`, `ready_status` and `timeout`, and `setup`
as lists of Compose arguments. `up` starts it and runs setup once; `reset`
removes that fixture's volumes and starts a new generation; `down` removes it.
Compose files must use project-owned containers, networks and volumes.

For a visit with `[web] instance = "<name>"`, run
`instance capture <video.toml> <name> --visit <visit.web.toml>`.
The visit must use that instance's origin, and its running container IDs must
match the successful setup record. The command delegates recording to
polyweave's `capture.web` and writes an `.instance.json` sidecar with the
fixture generation, actual image IDs and the recording's hash. Reset is
explicit; capture never resets an instance implicitly. Modern WordPress is
declared in `japode/wordpress/instances/wordpress.compose.yaml`.
The historical fixture is `wordpress071` in the same video declaration;
its source archive hash, PHP compatibility shim and native-installer setup are
versioned beside its Compose file. The Viglet Shio promo declares `shio` and
uses the fixture in its existing JavaScript recording script. `fresh` creates
a fixture or explicitly resets its existing generation; `status` verifies a
ready fixture for continued filming. Optional `startup_logs_service` keeps the
actual Compose startup answer and application log for the recorded terminal.

Illustrated plans and builds refuse a spoken highlight while a beat's caption
is visible (VM43), including duplicate labels. `overlay_seconds` ends that
visibility on full-frame footage and pictures. A highlight crossing a cut
warns so its end time can be reviewed. Highlight entries can declare
`"person": "Michel Valdrighi"` or `"event": "WordCamp Brasil"`; alternatively,
the storyboard's `entities` maps a displayed label to `"person"` or `"event"`.
Missing matching `people` or `events` tags on the beat or asset produces a
warning. These declarations support review; they do not establish identity.

Illustrated beats after the first can declare `"from_word": "Gutenberg"`
(VM42). The current take's hash-checked transcript places that boundary at the
word's start plus the 0.4-second voice lead, rounded to a production frame.
For a repeated phrase, use `"from_word": {"text": "Mike", "occurrence": 2}`
(one based), or replace `occurrence` with `"context": "Mike Little"`.
Missing or ambiguous matches are refused before rendering. Existing duration
and weight rules fill each interval between anchors; contradictory durations,
reversed anchors and beats shorter than one second are refused. `at` remains
the trim into the source file. A retake recomputes the timeline from its new
word times; the first beat always begins at the take's origin.

For illustrated videos, `build --plan` also writes `video/review/index.html`
and `review.json` (VM41). Each beat has a source-midpoint still or its production
card, the overlapping hash-checked narration words, production captions,
highlights, source range and declared `people`, `events` and `topics` tags.
Missing or stale word times are refused before drawing the sheet. Source stills
show the original media; the production overlays are listed beside them.
Check identity and context against the sources; motion review remains VM57.

To keep a reviewed cut, set `revision = "v3"` in `[video]` or pass
`--revision v3` to `build` (VM40). The complete build writes into
`video/revisions/<name>.<language>.<cut>/v3/`: video, subtitles, description
and credits when generated, measured QA, first frame, and working parts.
An existing revision is refused, including an interrupted one; use a new
identifier for the next attempt. Language and cut have separate packages.

Only after every output and optional project succeeds does the build atomically
replace `<name>.<language>.<cut>.current.json` in `video/`. Its `videos` paths
are relative to `video/`; `review` points at the package's generated documentation
table, linking its videos, subtitles, QA, first frames and credits.
Unfinished packages retain `INCOMPLETE`; failures leave the previous pointer
and package usable. `--plan` and `--cards` do not reserve revisions. Declarations
without a revision keep their existing output paths.

Every encoded cut gets a measured `<cut>.qa.json` and a decoded
`<cut>.first.png` before the build announces success (VM39). The report records
the MP4's SHA-256, size, duration and streams, loudness and true peak per audio
stream, UTF-8 checks of its captions and script, and the first 120 decoded
frames' presentation intervals and identical-frame runs. Illustrated full cuts
also include shot, asset, source-file, static-time and highlight counts from
their build inputs. Other cuts leave those editorial counts null.

Before accepting a build, QA holds every audio stream in the encoded MP4 to
`[audio] peak` (VM47), using the mix's default ceiling when it is omitted.
AAC overshoot therefore fails the build even when the pre-encode limiter passed.
The error identifies the stream and measured dBTP; increase `[audio] margin`
and rebuild. A failed peak check removes stale QA and first-frame sidecars and
cannot advance a revision's current pointer. Direct `qa.report` callers can
pass `peak_ceiling` to request the same check.

The first-frame image carries its own hash and the MP4's hash in the report.
A failed measurement removes stale QA files; a video that changes during
measurement is refused. The opening sample measures cadence and repeated
frames. Camera shakiness and whether a shot fits its sentence still need review.

Before buying voice takes, `narration/buy.mjs` checks the selected language's
intro for preambles such as "Hoje eu quero te contar" or "Today we will" (VM29).
This runs for dry plans too, before writing the purchase request.

For a timing estimate, add `opening` to the narration's `script.json`:

```json
"opening": {
  "words_per_minute": { "pt-BR": 150 },
  "proof": { "pt-BR": { "take": "intro", "before_word": 10 } }
}
```

The editor names the take and zero-based word before which the first proof
appears on screen. The guard counts spoken words up to that point, excluding
delivery tags and applying pronunciation substitutions. It refuses an estimate
over 20 seconds or an invalid anchor. Supply the narrator's pace and proof for
each purchased language. Scripts without `opening` receive the preamble check
only. This estimate does not verify the footage or measure viewer retention;
review the rendered opening against the declared shot and later Studio curves.

An illustrated history can also declare `source.kind = "illustrated"` and a
`source.declaration` JSON, as `japode/wordpress/video.toml` does (VM35). It names
every narration take in order, with weighted editorial beats, their factual
sources and any licensed local media. Videos and portraits fill the frame by
default, with transparent lower thirds; `presentation = "panel"` keeps a source
beside the text. Dates and diagrams use the declared channel theme. Missing or
stale takes, absent footage, incomplete credits and clips shorter than a beat
are refused. The existing scene timeline supplies voice placement, mix and
optional subtitles; the description derives chapter times and media credits.
This path does not migrate Docker and Scion's existing footage pipelines (VM34).

VM36 adds explicit beat lengths (`seconds`), a declared `max_static_seconds`
limit that also covers photos and filmed static pages, and `edit.json` with the
measured shot schedule. Word-timed highlights are declared in `[highlights]`;
`python -m videomaker.narration_words <video-root>` keeps hash-checked transcripts
for them. Missing spoken anchors are refused rather than given guessed times.
Footage may opt into motion interpolation through its `smooth` media field.

`video-maker/` is also a Python project (`pyproject.toml`, Python 3.12+, OpenTimelineIO). Run
`python -m pip install -e "video-maker[test,cards]"` once, then `pytest video-maker` from the
repository root. The tests read VM1's goldens as data, so each port is proved against them
before the assembler that uses it exists. What the JS assembly computed before it was removed
(the ffmpeg arguments, the push-in and the time maps) is frozen in `tests/oracles/`, so the ports
stay held to it.

## The golden check

`node video-maker/test/golden/run.mjs` rebuilds the WordPress demo's variants (the English and
pt-BR story, the pt-BR one with its Resolve project, the developer walkthrough, chapter 2 and its
vertical cut) and diffs them against `test/golden/expected/`. It builds each variant with `python -m
videomaker build` from the WordPress declarations; a difference means a change moved the video.

- What it compares: each build's timeline (`parts/<name>.plan.json`; `--plan` stops there), the
  teaser's plan and each narrated language's mix graph, the page each card layer is drawn from (`cards/*.html`, fonts named by
  file), its captions and chapter list, the FCPXML and `finish.lua`, and the
  finished files' lengths and streams.
- The recordings are `test/golden/fixtures/*.json`, frozen timelines played over a synthetic
  WebM, so a re-record never moves the goldens. The cards never see a live store, and the
  English build's stills go to a scratch copy of the plugin, so the run is the same with or
  without the demo stack and leaves the Turing repository as it was.
- The narration takes, music, intro and b-roll are this machine's, since media is not versioned.
  When a take is bought, `--update` writes the goldens anew; `--only <name,...>` builds a few.

## Where it is going

Recording stays JavaScript and the assembly becomes Python (decided 2026-11-09). Recording
means the narration reader Turing's specs import, the recording driver and pointer
(`recording/`), and the terminal replay. The assembly becomes the `videomaker` package:
captions, the mix, themed cards, the sources (a chaptered recording, scene clips), the
timeline as OpenTimelineIO (the video's source of truth), the cuts, the push-in and time
maps, the Resolve project as that `.otio` handed over, publishing, and `python -m videomaker
build <video.toml>`. Each port is proved against the golden files before the assembler that
uses it exists. The order and the reason for each step are in the roadmap.

The render stays ffmpeg (VM24, 2026-11-09). `spikes/mlt_chapter.py` rendered chapter 2 of the
pt-BR story both ways from the same inputs. MLT (`melt` 7.41) gave the same picture and, once
normalised the same way, the same level (-14.1 LUFS, -2.0 dBTP). But one MLT pass took 55 s
against 28 s for the whole ffmpeg path, and reaching the target took three whole renders
(141 s), where ffmpeg re-encodes only the audio. It would replace about 170 lines with an XML
writer of about 100 for one chapter's shape, none of it in the hard part, which the OTIO timeline
already carries. Worth measuring again if a GPU render (MLT's movit) or an editor that reads
MLT XML becomes a need.

## Rules every module keeps

- Nothing on screen is staged: a scene is the product working, and an agent's session is its
  real record.
- A product's brand, words, URLs and languages live in the video's config, never in a module.
- Media is not versioned (see the repository's `.gitignore`); the scripts and the small sources
  that make it are.
