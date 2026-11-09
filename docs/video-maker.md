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
| `story-moves.mjs` | A visible pointer a headless recording would leave out, a quick hand-like move to what is clicked, a slow eased scroll | `shio/promo/bin/story-scenes.mjs` |
| `terminal-replay.mjs` | A Claude Code session replayed as a terminal scene from its own `stream-json` record: every line is real, nothing is staged | `shio/promo/bin/story-terminal.mjs` |

## Where it is going

`media/ffmpeg.mjs`, `narration/`, `captions.mjs`, `audio/mix.mjs`, `cards/`, `timeline.mjs`,
`sources/` (a chaptered recording, scene clips, a terminal replay), `cuts/`, `motion/`, `edit/`,
`export/fcpxml.mjs`, `publish/`, `recording/` and `cli.mjs`, with each video described by a
`video.config.mjs`. The order and the reason for each step are in the roadmap.

## Rules every module keeps

- Nothing on screen is staged: a scene is the product working, and an agent's session is its
  real record.
- A product's brand, words, URLs and languages live in the video's config, never in a module.
- Media is not versioned (see the repository's `.gitignore`); the scripts and the small sources
  that make it are.
