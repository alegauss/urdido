# Improvements

## Block A — Package foundation (urdido installable from PyPI)

### §UR19 Releases through trusted publishing

Copy polyweave's `publish.yml` and `tools/release.py`. A `v*` tag builds the sdist and
wheel, runs `twine check --strict`, refuses a tag that differs from `__version__`,
publishes to TestPyPI and then PyPI through trusted publishing (no token, environments
`testpypi` and `pypi`), and opens a GitHub release with notes from the changelog.
`tools/release.py patch|minor|major` bumps, commits and tags on a clean `main`.

The wheel must carry the package data the build needs at run time: `export/finish.lua`,
card templates, and the JavaScript helpers if they ship inside it (Block B decides).

**Done when** `0.1.0` installs from PyPI into a fresh virtualenv and `urdido build
--help` answers.

## Block B — The engine extracted (videomaker without marketing)

### §UR30 The JavaScript side packaged

`prepare.py:30-38` runs `node` on `narration/takes.mjs` and `opening.mjs` found at
`Path(__file__).parents[1]`, which a wheel does not have. `takes.mjs` duplicates
`narration.py`; `buy.mjs` buys through polyweave; `story-moves.mjs`,
`terminal-replay.mjs` and `recording/seconds.mjs` are recording helpers using only Node
built-ins.

Port the opening gate to Python so the build needs no node. Publish the recording and
narration helpers as one npm package (`urdido-record`, or a scope), versioned with the
Python one, so consumers import it by name. The narration currency rules then exist
once, in Python, with the JS reading the result.

**Done when** `urdido prepare` runs without node, and marketing's scripts can import the
helpers from the npm package.

### §UR34 Where polyweave ends and urdido begins

polyweave PW712 (preflight and repetition), PW713 (interval preview), PW714 (media
catalogue), PW715 (build progress) and PW716 (claims) were filed from marketing; each
names a videomaker module as the temporary adapter, and each assumes polyweave owns an
authored cut, beats and narration anchors. That is urdido.

Agree the boundary: polyweave keeps the media primitives (stock, capture, voice and word
times, HTML to still, measuring a finished file, frames and contact sheets, provenance,
budgets); urdido keeps the declaration, timeline, cuts, cards, mix, checks over a cut,
review and publishing. Then move or narrow those PW lines, leaving polyweave the
primitive each one needs, and file urdido's remaining side here.

**Done when** no open PW line plans composition, and each urdido check names the
polyweave primitive it uses.

### §UR43 The lint baseline the import left

Where it happened: UR21 merged marketing's `video-maker/` history into `src/urdido/` and
`tests/`. That code was written without ruff, and on arrival `ruff check` reported about
2,100 findings (1,916 of them E501 at 88 columns, then I001, B023, F811, B905, UP035,
F401) and `ruff format --check` wanted to rewrite 87 files.

What was done: reformatting would have buried every module's history under one commit,
which is what the history import exists to keep. So `pyproject.toml` carries a generated
baseline: `[tool.ruff.lint.per-file-ignores]` lists each imported file with exactly the
codes it broke, and `[tool.ruff.format] exclude` lists the 87 unformatted files. New
files are held to the full rules.

What to do: pay the list down module by module, preferably with the change that next
touches the module, so blame moves with real work. Safe fixes (`ruff check --fix` for
I001, F401, UP035, UP037, UP017) can go in one pass. B023 (a closure over a loop
variable) and B905 (`zip` without `strict`) are possible bugs and need reading, not
suppressing. A file leaves both lists once it is clean, and nothing is ever added.

**Done when** both lists in `pyproject.toml` are gone and `ruff check` and `ruff format
--check` pass on the whole tree.

### Â§UR47 The side files and values checked

UR23 gave video.toml a key schema (`urdido.declaration.SCHEMA`). UR56 typed its values
(NUMBER, TEXT, FLAG, LIST), and the steps since check every side file the declaration
names against its own shape with the same did-you-mean refusal: the narration script,
the storyboard, the cards, the highlights, the claims and the translation tables
(`side_files`, `check_side_files`, run by `urdido check` and by `Project` before any
work).

What is left: the defaults still live at each `.get(key, default)` in the modules, so
the reference and the JSON Schema cannot say what an absent key means. Give each table a
dataclass holding its types and its defaults, load the declaration into them once in
`Project`, and let `reference()` and `json_schema()` read the dataclasses rather than
the key table.

Done when no module reads a default that the model does not hold, and
docs/specs/declaration.md names each key's default.

## Block C — Adoption in marketing (video-maker replaced by urdido)

### §UR41 Every video rebuilt and compared

Rebuild every declared video with urdido and compare with the last video-maker build:
turing/wordpress (story and developer, both languages), shio/promo (long cut and
shorts), japode/wordpress, japode/primeiro-bug. Compare plans, captions, descriptions,
credits and QA (duration, streams, loudness); the frames come from the review sheets.
Expect one full rebuild per video unless the cache keys survive the install.

Differences are either explained by a deliberate change in the extraction or fixed.
japode/docker and japode/scion stay on their copied scripts until UR4.

**Done when** each video's comparison is recorded with no unexplained difference.

### §UR42 The in-repo framework removed

Delete `video-maker/` from marketing, with its `.gitignore` lines (`*.egg-info/`,
`video-maker/spikes/out/`), the untracked `.polyweave/*.py` scratch scripts that import
it, and the remaining mentions in marketing's README and in visibility's `CLAUDE.md`.
Marketing's remaining Block B (channel analytics, VM28 and VM32) stays there under a new
title.

**Done when** marketing has no `video-maker/` folder, every video builds from the pinned
urdido, and `roadkeep lint` passes in both repositories.

## Block D — Inherited from video-maker (marketing Block B)

### §UR3 End screens and cards (was marketing VM33)

Neither the Docker nor the Scion video has an end screen or a card, so a viewer who
reaches the end of one is offered nothing from the channel, and YouTube's own suggestion
takes them elsewhere.

Rules from youtube-agent-pro's yt-endscreen and claude-youtube, read on 2026-11-12:

- the end screen covers the last 5 to 20 s, so the video's closing card leaves that space free of text;
- it points at the video that continues the subject (Docker to Scion, a Viglet demo to the next step), never just the newest upload;
- at most one video element and one subscribe element;
- 0 to 2 cards, placed just before a known drop on the retention curve, never on a peak;
- the narration's last line sets it up ("the next one is about...") instead of a bare like-and-subscribe.

The build writes, beside the description, which video the end screen points at and the
second each card goes in, so the Alexandre sets them in Studio in one pass.

### §UR4 The explainer video on video-maker (was marketing VM34)

video-maker was grown from the recorded product demo (Viglet Turing for WordPress,
Viglet Shio), and the first video of another kind went around it. The Japode Docker and
Scion videos each carry their own build.py, narration.mjs, check-takes.py, capture and
film scripts, thumbnail.py and short.py, and the two copies already differ (the Scion
one has the brand and the new Shorts rules, the Docker one does not).

What an explainer needs from the framework, all of it already working in japode/scion:

- shots from Creative Commons footage, each a source, a start second, a duration, a speed and a box that keeps an author's own text out, panned slowly;
- a web page filmed with a highlighter drawn over the quoted sentence, and a terminal session captured for real and filmed;
- callouts timed to the words said, with a one-line definition for a new term;
- a channel theme (japode/brand: fonts, colours, logo, thumbnail layout) as the cards theme is for the product videos;
- the description with chapters and the CC BY credits of the clips actually used;
- the Shorts, through `urdido shorts` (UR2), each video declaring `[shorts]`.

Done when the Docker and Scion videos are each a video.toml built by `python -m
videomaker build`, their copied bin/ scripts are removed, and the published cuts are
reproduced (the golden-check rule of Block B). This is also the condition for giving
video-maker a repository of its own: two owners, Viglet and Japode, using it.

### §UR5 A video cannot be built as a variant of another (was marketing VM68)

Where it happened: the published WordPress episode (`japode/wordpress`) lost most of its
audience between 8 s and 19 s (YouTube Studio, 2026-11-16: 94% to 58% at 8 s, under 30%
at 19 s). The owner asked for a second cut with a new opening to re-upload and compare
retention.

What was done by hand: `robocopy japode\wordpress japode\wordpress2` copied 722 MB of
footage, takes, ledgers, instance records and the whole declaration, only to change
three takes (intro, chapter-1, chapter-1-result), two scene lists in `storyboard.json`,
two highlight lists, three caption translations and one claim. A throwaway script in the
scratchpad rewrote those JSON files. From now on the two folders drift apart: any
credit, claim or source fix in one must be repeated in the other, and nothing says which
is the published cut.

What video-maker should do: let a declaration build a variant of another video, for
example `[video] base = "../wordpress"` plus overrides for the takes, scenes and
highlights that differ. It should reuse the base's media, takes and ledgers without
copying them, write its output to its own folder, and record in the review which variant
was uploaded and against which retention report it is being compared (with VM32).

Sequenced after UR33: the overlay must resolve every relative path through the base, and
about 25 call sites read `build.here` directly; UR33's declaration loader is the one
place it belongs.

### §UR15 One recording driver (was marketing VM16)

`tests/e2e/story/shopper.story.mjs` and `developer/install.developer.mjs` in the Turing
repository copy the driver (`speak`, `tell`, `until`, `focus`, `release`, `skipping`,
`highlight`, `chapter`), the developer copy without `skip` or `tell`;
`video-maker/story-moves.mjs` copies the pointer and has drifted (`__storyCursor`, no
deadline pacing). Make `video-maker/recording/`: `moves.mjs` (pointer, reach, glide with
a deadline, scrollBy, layoutAt) and `storyClock`, which writes `chapters.json`
byte-compatible. The driver also records each clicked element's box as a `focus` mark,
in `cenas.json` for a scene: Viglet Shio's 9:16 shorts (VM12) crop its scenes at the
centre today and cut the console's left edge, and would follow the box instead.

The plugin's specs reach it through `tests/e2e/marketing.mjs`, whose contract is that
"only a recording needs it; the stories run as tests without it". Keep that contract:
the driver is loaded only when recording, and without the marketing repository the specs
fall back to plain steps with no pointer or pacing. This edits Turing's specs, so it
ships with a commit there too.

**Done when** the three recordings use the one driver, a re-recording produces the same
`chapters.json` shape, and Turing's stories pass as tests with
`VIGLET_MARKETING_WORDPRESS` pointing nowhere.

### §UR44 Retakes through voice.lines once it can

`urdido prepare --retake` (UR7, `src/urdido/prepare.py`, `retaken`) re-buys a take whose
text is unchanged by moving the take, its `.prov.json` and its `.words.json` into
`<language>/retakes/` before asking polyweave's `voice.lines` for a quote, then putting
them back when nothing was bought. That works only because voice.lines decides "current"
from the file on disk, and it has no parameter to buy a current key again.

polyweave PW720 asks voice.lines for a `retake` list of keys that it plans as not
current, keeps the replaced take, and records the reason in the take's provenance. When
it ships, pass the retaken keys through instead of moving files, keep `--retake` and
`--retake-reason` as they are, and keep writing `retakes.json` (or read the reason back
from the provenance if PW720 records it there).

**Done when** `retaken` moves no file and the UR7 tests pass against a voice fake that
honours the retake list.

### §UR53 Page and terminal films declared

The terminal half is in urdido: `[terminal.scenes.<name>] commands`, run for real by
`urdido terminal` (`urdido.terminal`) into `terminal/session.json`, and filmed by
`js/film-terminal.mjs` with the terminal replay's window into
`footage/terminal/<scene>.webm`, the `terminal:<scene>` shots the explainer reads.

Left: the page film. Marketing's `japode/scion/bin/film-page.py` opens the post, scrolls
eased to each quoted sentence and draws a highlighter over it, refusing a sentence the
page no longer prints. It belongs in a declared visit, and polyweave's `capture.web`
cannot find a text or draw over it yet (polyweave PW721, beside PW704's eased scroll).
Once it can, a video declares each quote as a visit (the URL, the sentence, the hold)
and a `[[record.step]]` runs `capture.web` for it into `footage/page/<scene>.webm`.

Then marketing drops Scion's and Docker's `bin/film-page.py`, `capture-terminal.py` and
`film-terminal.py` for declared `[terminal]` scenes and visits (a marketing task once
this ships).

Done when the Scion video's page and terminal shots are made from its declaration.
