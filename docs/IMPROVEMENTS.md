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

### §UR46 The legacy root variables removed

UR22 made every root a declaration's own: `[roots]` names each one, `[output] folder` is
`<video>`, and `build.roots_of` knows no sibling path. For one release, `LEGACY_ROOTS`
in `build.py` still lets STORY_VIDEO_DIR, STORY_RECORDINGS, TURING_WORDPRESS and
SHIO_REPO fill an undeclared root, printing a notice each time. That table is the last
place a root name lives in a module, and the tests still set STORY_VIDEO_DIR to move a
build's output into a temporary folder.

After the first release that carries `[roots]`, and once marketing's declarations
declare their roots (UR37), delete `LEGACY_ROOTS` and its loop, and change the tests
that set STORY_VIDEO_DIR to declare `[output] folder` in their fixture instead.

Done when no module names a root and no test sets one of the four variables.

### §UR47 The side files and values checked

UR23 gave video.toml a key schema (`urdido.declaration.SCHEMA`): every table and key the
code reads, unknown keys refused with the nearest name, required keys and each source
kind's needs checked by `urdido check` and before every build. The values are not typed
(a `tempo` of "fast" passes), the defaults still live at each `.get(key, default)` in
the modules, and the side files a declaration names are not checked at all: the
narration script, the cards declaration, the storyboard, the highlights, the claims and
the translation tables still fail as a KeyError when a key is misspelled inside them.

What to build: give each table and each side file a dataclass with its types and its
defaults, load the declaration once into them (the loader UR33 splits out of `Build`),
and let `urdido check` follow every path the declaration names, through its roots, and
check that file against its own model with the same did-you-mean refusal. The JSON
Schema export then comes from the dataclasses rather than from the key table.

Done when a misspelled key inside storyboard.json or script.json is refused by `urdido
check` with its file and the nearest name, and no module reads a default that the model
does not hold.

### §UR49 A declared Python API

UR24 made the library raise `urdido.UrdidoError` (with `Refused`, `DeclarationError` and
`MissingTool`) instead of exiting, and put every command under one `urdido --help`. The
package's `__all__` names only those errors. A program that wants to build a video still
imports `urdido.build.Build`, fills an `argparse.Namespace` by hand and calls its
methods, and the modules reach into each other's underscored names (`timeline._rounded`,
`build._portable_all`).

What to build: a small declared API in `urdido/__init__.py`, loaded lazily so `import
urdido` stays cheap: `urdido.check(path)` returning the problems, `urdido.load(path)`
returning the parsed declaration with its roots, and a build entry (`urdido.make(path,
language, cut=...)`; not `urdido.build`, which is the submodule's name) that takes
keyword options rather than a Namespace. Each module's public names go in its own
`__all__`; an underscored name used from another module is renamed or moved.

Done when the README's Python example builds a plan without argparse, and no module
imports another's underscored name.

## Block C — Adoption in marketing (video-maker replaced by urdido)

### §UR36 Marketing on an installed urdido

Marketing gets a `requirements.txt` (or a small `pyproject.toml`) that pins urdido:
editable from `D:\Git\alegauss\urdido` while the extraction is in flight, then the PyPI
version once UR19 releases. The skill and README install lines (`pip install -e
"video-maker[test,cards,narration]"`) change with it, and `PYTHON` in the bin scripts
keeps naming the interpreter that has it.

**Done when** a fresh virtualenv in marketing gets urdido from the pin and `urdido
--version` answers there.

### §UR37 Every call switched to urdido

The callers: `package.json` in turing/wordpress and shio/promo (`story:video`,
`story:developer`); `turing/wordpress/bin/transcript.mjs` (which imports the package by
running from `video-maker/`); `shio/promo/bin/story-scenes.mjs:92` (`instance`); the
japode READMEs and `PUBLICACAO.md`; `japode/brand/brand.py:186`
(`videomaker.thumbnail.fit_title`); `japode/scion/bin/build.py:347`
(`videomaker.publish.description`).

urdido ships a `videomaker` shim for one minor release: the module name and `python -m
videomaker` forward to urdido with a deprecation notice. Marketing switches project by
project; the shim goes in the next release.

**Done when** grep finds no `videomaker` in marketing outside the changelog, and every
video still builds.

### §UR38 JavaScript imports from the package

Eight scripts import `../../../video-maker/...`: `narration-takes.mjs` and
`story-narration.mjs` in turing/wordpress, shio/promo and both japode explainers;
shio/promo's `cenas.mjs`, `pace.mjs`, `story-scenes.mjs` and `story-terminal.mjs`.
Turing's `wordpress/tests/e2e/marketing.mjs:16-35` imports marketing's
`turing/wordpress/bin/narration-takes.mjs`, which imports `takes.mjs`.

Switch each import to the npm package from the JavaScript-packaging task, installed by a
`package.json` at the root of marketing. `narrationFor` stays exported from
`turing/wordpress/bin/ narration-takes.mjs`, so Turing's specs need no change.

**Done when** no marketing script imports a path under `video-maker/`, and Turing's
story recording still finds its narration.

### §UR39 The golden check moves to the video it proves

`video-maker/test/golden/run.mjs` rebuilds the WordPress demo's variants from
`turing/wordpress` and `../turing/latest/wordpress`, snapshots the Turing repository's
`git status`, and diffs against `test/golden/expected/`, using media that is not
versioned.

Move it to `turing/wordpress/test/golden/` in marketing, running the installed urdido.
urdido keeps the frozen oracles and its own synthetic end-to-end test.

The tests in urdido that still read marketing check one of its videos, not the
framework, and move with it (UR31 left them guarded by `needs_marketing`): the golden
comparisons in `test_captions`, `test_cards`, `test_assemble_clip`,
`test_assemble_video`, `test_cuts`, `test_goldens`, `test_mix` and `test_timeline`; the
Viglet Shio promo's terminal chapters (`test_terminal`), scenes (`test_scenes`) and card
(`test_cards`); and the WordPress description (`test_description`). Once they live in
marketing, `tests/marketing.py` goes.

**Done when** `node turing/wordpress/test/golden/run.mjs` passes against the installed
urdido with the expected files unchanged, and urdido's suite runs in CI with no path
outside this repository.

### §UR40 Marketing's agent rules point at urdido

`.claude/hooks/video-maker-gate.py` exempts `video-maker/` and any ffmpeg command
mentioning videomaker, and tells the agent to add a module and a Block B task;
`.claude/settings.json:37-46` wires it; `.claude/skills/video-maker-friction` files into
Block B; `roadkeep-gui-roadmap-docs` has the install line, the pytest and node gates and
the `feat(video-maker)` scope; `CLAUDE.md:8-28,43,56` describes the framework.

Reword the hook for `urdido` (the exemption and the guidance), replace the friction
skill with urdido's (UR20), update the gates to marketing's own tests, and rewrite the
CLAUDE.md rules: every video is built by urdido, and framework friction becomes a UR
task.

**Done when** a new script in a video folder still asks first, and the guidance names
urdido and its roadmap.

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

### §UR45 The flash scan calibrated on real cuts

UR14 put a flash scan in the final verification (`qa.flashes`): every frame is decoded
grey at 32x18, and a change of at least 6 (mean absolute difference, 0 to 255) that
lasts one or two frames and comes back within a third of the jump is refused. The
threshold and the size were set on synthetic frames, not on a real cut.

Two things are unknown. The second Shio promo flash (2026-11-17, 40.667 s) was a
different picture of the same brightness, ffmpeg YDIF 7.6 at full size; averaged down to
32x18 its difference may fall under 6, and then the scan lets it through. And no
published video has been scanned yet: an animated card, a blinking cursor or a quick
zoom might read as a flash, which would refuse a cut that is fine.

What to do: run `qa.flashes` over the Shio promo's chapter-2 clip as it was before the
fix and over each published Japode and Viglet cut, and set the size and threshold from
what separates them; keep both in `[qa]` if one value does not fit every channel. Record
the numbers next to the test that encodes the dashboard case.

Done when the Shio promo's old chapter 2 is refused and every published cut passes.

### §UR48 One table, one Shorts cutter

Two things read `[shorts]` in a video.toml. A scenes build's `--cut short:<c>` reads
`[shorts] declaration`, a JSON file of chapter selections cut by `cuts/selection.py`
(VM12). `urdido shorts` (UR2) reads `[shorts]` with `plan`, `picture`, `mix`, `look`,
`[[shorts.cut]]` and the rest, for a video built outside the scenes pipeline. The key
schema (UR23) accepts the union of both, so a declaration can mix them and nothing says
which cutter a key belongs to; the Viglet Shio promo already uses the first and a Japode
video moving onto urdido would use the second.

What to build: decide whether the selection cutter's Shorts follow the UR2 rules (loop,
punch-ins, word captions, loudness) and become one cutter, or keep two and give the
newer one its own table name (`[shorts.feed]`, say) with the schema refusing a key of
one inside the other. Either way, one table means one thing.

Done when each key under `[shorts]` belongs to exactly one cutter and the schema says
which.

### §UR53 Page and terminal films declared

UR4 and its steps (UR51, UR52) moved the Japode explainer's plan, render and description
into urdido (`urdido.pipelines.explainer`). Two of its sources are still made by scripts
copied into each video: `bin/film-page.py` films a web page scrolling to a quoted
sentence with a highlighter drawn over it (the Anthropic post in the Scion video), and
`bin/capture-terminal.py` with `bin/film-terminal.py` record a real shell session and
film it as a terminal scene (Scion's Git session, Docker's container commands). The
explainer reads what they leave, `footage/page/<scene>.webm` and
`footage/terminal/<scene>.webm`, as `page:<scene>` and `terminal:<scene>` shots.

What to build: a page film declared by URL, the sentence to highlight and the scroll,
filmed through the provider's web capture (`capture.web`) with the highlight drawn over
the found text, never typed into the page; and a terminal scene declared as the commands
to run in a throwaway folder, recorded for real and filmed with
`js/terminal-replay.mjs`'s window (the same rule as the agent replay: nothing on screen
written by hand). Both become `[[record.step]]`s a video declares, so `urdido record`
makes them in order.

Done when the Scion video's page and terminal shots are made by urdido from its
declaration, and its bin/film-page.py, capture-terminal.py and film-terminal.py go.
