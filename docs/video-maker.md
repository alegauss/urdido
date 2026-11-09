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
| `story-moves.mjs` | A visible pointer a headless recording would leave out, a quick hand-like move to what is clicked, a slow eased scroll | `shio/promo/bin/story-scenes.mjs` |
| `terminal-replay.mjs` | A Claude Code session replayed as a terminal scene from its own `stream-json` record: every line is real, nothing is staged | `shio/promo/bin/story-terminal.mjs` |

## The golden check

`node video-maker/test/golden/run.mjs` rebuilds the WordPress demo's variants (the English and
pt-BR story, the pt-BR one with its Resolve project, the developer walkthrough, chapter 2 and its
vertical cut) and diffs them against `test/golden/expected/`. Every step that moves code out of
`story-video.mjs` runs it before and after; a difference means the step changed the video.

- What it compares: each build's timeline (`story-video.mjs` writes `parts/<name>.plan.json`;
  `--plan` stops there), its captions and chapter list, the FCPXML and `finish.lua`, and the
  finished files' lengths and streams.
- The recordings are `test/golden/fixtures/*.json`, frozen timelines played over a synthetic
  WebM, so a re-record never moves the goldens. The cards never see a live store, and the
  English build's stills go to a scratch copy of the plugin, so the run is the same with or
  without the demo stack and leaves the Turing repository as it was.
- The narration takes, music, intro and b-roll are this machine's, since media is not versioned.
  When a take is bought, `--update` writes the goldens anew; `--only <name,...>` builds a few.

## Where it is going

`narration/`, `captions.mjs`, `audio/mix.mjs`, `cards/`, `timeline.mjs`,
`sources/` (a chaptered recording, scene clips, a terminal replay), `cuts/`, `motion/`, `edit/`,
`export/fcpxml.mjs`, `publish/`, `recording/` and `cli.mjs`, with each video described by a
`video.config.mjs`. The order and the reason for each step are in the roadmap.

## Rules every module keeps

- Nothing on screen is staged: a scene is the product working, and an agent's session is its
  real record.
- A product's brand, words, URLs and languages live in the video's config, never in a module.
- Media is not versioned (see the repository's `.gitignore`); the scripts and the small sources
  that make it are.
