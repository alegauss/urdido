# video-maker

The framework every product video in this repository is built with: the Viglet Turing
WordPress demo (`../turing/wordpress`), the Viglet Shio promo (`../shio/promo`) and the ones
after them. A video declares what it is (its narration, its scenes, its theme, its cuts); the
framework records, voices and assembles it.

It grows out of the WordPress demo's assembly (`turing/wordpress/bin/story-video.mjs`, about
2,900 lines in one script), one module at a time, and each step keeps that video's output the
same. The plan is Block B of `../docs/ROADMAP.md` (VM1 to VM18).

## What is here today

| Module | What it does | Used by |
|---|---|---|
| `media/ffmpeg.mjs` | ffmpeg run quietly or side by side in a bounded pool, the encoder (NVENC or x264, one keyframe each half second), a file's length, a mix's loudness, and per video context the cuts, held frames and joins | `turing/wordpress/bin/story-video.mjs` |
| `narration/takes.mjs` | A narration's script, its lines, where each take lives, what the voice says (`pronounce`), the captions' text, and whether a take is current | both videos' `bin/narration-takes.mjs` |
| `narration/buy.mjs` | Buys the takes through polyweave's `voice.lines`: plans, spends inside the budget, skips current takes | `shio/promo/bin/story-narration.mjs` (WordPress waits on polyweave PW691) |
| `story-moves.mjs` | A visible pointer a headless recording would leave out, a quick hand-like move to what is clicked, a slow eased scroll | `shio/promo/bin/story-scenes.mjs` |
| `terminal-replay.mjs` | A Claude Code session replayed as a terminal scene from its own `stream-json` record: every line is real, nothing is staged. A video declares each chapter's lines as selectors (`chooseLines`: tools, kinds, patterns, first or last). `initLine` opens a chapter on the session's own start, showing the one declared plugin and nothing else of the machine | `shio/promo/bin/story-terminal.mjs`, from `shio/promo/demo/agent/terminal.json` |
| `videomaker/media.py` | The Python port of `media/ffmpeg.mjs`, the first module of the Python assembly; `tests/test_media.py` checks that it builds the same ffmpeg arguments | nothing yet |
| `videomaker/captions.py` | Narration captions (SRT, VTT), a silent cut's chapter-title captions and the YouTube chapter list, in any language the video declares. Titles come from the script's `chapters[n].title` and `introTitle`, and otherwise from the recording's step titles | nothing yet (`story-video.mjs` reads the same script fields) |
| `videomaker/cards/` | The card pages (`html.py`: the opening, chapter and closing cards, the backdrop and the two ranges of hills, and the parallax that slides them) in a declared theme, drawn by Playwright for Python (`render.py`). The module holds the layout only. The theme and words are each video's `demo/cards.json`, Tarnfell for the WordPress demo and Quilhara for Viglet Shio | nothing yet (`story-video.mjs` reads the same `cards.json`) |
| `videomaker/sources/` | The chapter model the timeline consumes (`Chapter`: number, title, clip, marks, pacing) and `chaptered_recording`, which reads a `chapters.json` as Turing's specs write it and refuses it as the JS does: no recording, another language, a test run, a missing chapter, a story newer than the recording. A focus mark without a box is a release | nothing yet (VM7's timeline) |
| `motion/pushin.mjs`, `edit/stretch.mjs` | The push-in that follows the action (its windows, the curve, the zoompan filter, the moments and values an editor keys) and the time maps that cut a chapter's marked waits, as pure functions of the frame and the marks | `turing/wordpress/bin/story-video.mjs` |
| `videomaker/motion/pushin.py`, `videomaker/edit/stretch.py` | Their Python ports, equal to the JS for every chapter of the fixtures (`tests/js/motion.mjs` prints the JS results) | nothing yet (VM7's timeline) |
| `videomaker/timeline.py` | The timeline as an OpenTimelineIO `Timeline`. Lanes V1 (recording, held frames), V2 (cards) and V3 (shots) are video tracks; each language's takes, the sounds and the bed are audio tracks; chapters are markers, and the encoded file, stills, chapter and dissolves ride in clip metadata. A `Builder` places pieces one after another, `plan()` derives VM1's plan JSON, and `.otio` files round-trip | `videomaker/assemble` |
| `videomaker/narration.py` | Reads a narration's takes as `narration/takes.mjs` does: each line's take, whether it is current (its provenance records the same spoken text, voice and model), and its length | `videomaker/assemble` |
| `videomaker/assemble/clip.py` | One chapter as a clip of its own, composed on the timeline from the chapter model, the cards, the takes and the bed, with real encodes. `tests/test_assemble_clip.py` builds chapter 2 and its vertical cut as the golden runner does and gets the golden plans | nothing yet (VM9, VM17) |
| `videomaker/assemble/video.py` | A full video on the timeline: the opening animation and its sound, title cards with shots cut at the narrator's pauses, each chapter's card and clip with its waits cut and its result held, the closing, the dissolves, and the push-ins and time maps as clip effects. Its work folder is the caller's, so two builds can each have their own. `tests/test_assemble_video.py` builds the English and Portuguese story and the developer walkthrough into their golden plans; it encodes for minutes, so it runs with `VIDEO_MAKER_FULL=1` | nothing yet (VM17) |
| `videomaker/cuts/render.py` | Renders a composed video's cuts through one path: the full cut with its dissolves (only the blended half second encoded again), the 30 s teaser when the video declares one, a chapter clip, and its vertical cut with the captions burned in. Each narrated language is mixed over the bed, and the captions are muxed beside the voice. `tests/test_cuts.py` renders the six variants into the golden `outputs.txt`, captions and chapter lists (`VIDEO_MAKER_FULL=1`) | nothing yet (VM17) |
| `videomaker/sources/scenes.py`, `videomaker/edit/pacing.py`, `videomaker/assemble/scenes.py` | A video filmed scene by scene: `cenas.json` read into scenes (each clip measured from the file; `filmed: false` kept as such), `fit_to_line` (a short clip holds its last frame, a long one plays faster as a whole, nothing cut), and the composition with every line over its own scene as an OTIO clip with a time warp, or over a card held in the video's theme while the scene is unfilmed | the Viglet Shio promo (VM20) |
| `videomaker/cuts/selection.py` | A short 9:16 cut made of chosen chapters of the 16:9 scenes: the long cut's scenes fitted to their lines, cropped to their centre (no focus box yet, VM16), cards drawn upright, captions burned in above the bottom fifth, and the voice over the short's own bed. Over its limit, it tightens the breaths and reports what is left over | the Viglet Shio shorts (`shio/promo/demo/shorts.json`, VM20) |
| `videomaker/audio/mix.py` | One language's narration over the music bed: the duck, the bed's trim to a reference level, sounds that come with the picture, and an iterated limiter to the loudness target. Every level is an argument, and the defaults are the WordPress demo's | nothing yet |

## The Python assembly

`video-maker/` is also a Python project (`pyproject.toml`, Python 3.12+, OpenTimelineIO). Run
`python -m pip install -e "video-maker[test]"` once, then `pytest video-maker` from the
repository root. The tests read VM1's goldens as data, so each port is proved against them
before the assembler that uses it exists. `tests/js/ffmpeg-args.mjs` loads the JS module with
`child_process` swapped for a recorder, which lets a test compare the arguments of both
implementations without running ffmpeg.

## The golden check

`node video-maker/test/golden/run.mjs` rebuilds the WordPress demo's variants (the English and
pt-BR story, the pt-BR one with its Resolve project, the developer walkthrough, chapter 2 and its
vertical cut) and diffs them against `test/golden/expected/`. Every step that moves code out of
`story-video.mjs` runs it before and after; a difference means the step changed the video.

- What it compares: each build's timeline (`story-video.mjs` writes `parts/<name>.plan.json`;
  `--plan` stops there), the page each card layer is drawn from (`cards/*.html`, fonts named by
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
timeline as OpenTimelineIO, the cuts, the push-in and time maps, the Resolve export through
OTIO's `fcp_xml` adapter, publishing, and `python -m videomaker build <video.toml>`. Each port
is proved against the golden files before the assembler that uses it exists. Whether MLT
replaces the ffmpeg filtergraphs for the render is measured on one chapter first. The order
and the reason for each step are in the roadmap.

## Rules every module keeps

- Nothing on screen is staged: a scene is the product working, and an agent's session is its
  real record.
- A product's brand, words, URLs and languages live in the video's config, never in a module.
- Media is not versioned (see the repository's `.gitignore`); the scripts and the small sources
  that make it are.
