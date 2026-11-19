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

### §UR20 Agent guidance and a friction skill

A `CLAUDE.md` for this repository: the gates, the governed docs, one task per commit
through `run-commit.cmd -m`, and the rules video-maker kept (nothing on screen is
staged; a product's brand, words and URLs live in the declaration, never in a module;
media is never versioned).

For consumers, an `urdido` skill on how to declare and build a video, and an
`urdido-friction` skill, shaped like `polyweave-friction`, that files a line here
(prefix UR) when the framework gets in the way. It replaces marketing's
`video-maker-friction`, which files into marketing's own Block B.

**Done when** a session in marketing that meets a missing setting files it here through
the skill, with `(from: marketing)`.

### §UR35 A first video and the declaration reference

Split the video-maker README into what a newcomer needs:
- a quickstart that builds a short video from a declaration in `examples/`, with
  synthetic media (ffmpeg lavfi colour and tone, an OFL font), so it runs with nothing
  bought or recorded;
- `docs/specs/declaration.md`, generated from the declaration schema (Block B), one section per table
  and side file;
- one page per source kind (scenes, illustrated, and chaptered if it stays) and per
  check (claims, pauses, repetition, text, safe area);
- the external tools each extra needs.

Ticket ids and personal names leave the prose.

**Done when** the quickstart builds its example in a clean checkout and the reference
lists every key the schema accepts.

## Block B — The engine extracted (videomaker without marketing)

### §UR22 Roots and output declared, not assumed

`build.py:49-57` fixes the roots `video`, `recordings`, `plugin`, `root` and `shio`,
defaults `<plugin>` to `../../../turing/latest/wordpress` and `<shio>` to
`../../../shio/latest`, and names them again at `:89`, `:208`, `:360`, `:371` and
`:405`. `thumbnail.py:91` writes to `video/parts/thumbnail` ignoring `STORY_VIDEO_DIR`.

A declaration names its roots in a `[roots]` table, each a path relative to the
declaration or an environment variable it reads; the code knows no root by name and has
no default outside the project. The output folder and the work folder are declared, with
`video/` and `video/parts/` as defaults. `STORY_VIDEO_DIR`, `STORY_RECORDINGS`,
`TURING_WORDPRESS` and `SHIO_REPO` keep working for one release with a deprecation
notice.

**Done when** no module contains a root name or a sibling path, and the marketing
declarations build with `[roots]`.

### §UR23 A schema for the declaration

Every module reads the declaration as `decl["x"]["y"]`; only `[video] frame`,
`text_checks`, `brand_mark` and instance names are checked. Model the declaration as
typed dataclasses per table (`video`, `source`, `narration`, `cards`, `music`, `audio`,
`opening`, `cuts`, `captions`, `highlights`, `claims`, `description`, `thumbnail`,
`instances`, ...) and the side files it names, with defaults in one place, unknown keys
refused with a did-you-mean, and paths resolved through the roots.

`urdido check <video.toml>` validates without building, and the schema exports a JSON
Schema that editors and the reference docs read.

**Done when** every marketing declaration passes `urdido check`, and a misspelled key is
refused with its file, table and the nearest valid name.

### §UR24 Errors raised, commands declared

`SystemExit` is raised deep in `build.py`, `preflight.py` and the assemblers;
`RecordingRefused` stands in for every other error. `__main__.py` routes on
`sys.argv[1]` and its usage names only `build` and `thumbnail`, while `publish`,
`export` and `narration_words` are separate `-m` entry points.

A small exception hierarchy (`UrdidoError` with refusal, missing-tool and declaration
kinds, each with a remedy) is raised by the library and turned into exit codes and
messages only in `urdido.cli`. One argparse tree holds every command: `build`, `check`,
`prepare`, `thumbnail`, `claims`, `library`, `storyboard`, `instance`, `export`,
`publish`, `words`. A public API (`urdido.build(...)`, `urdido.load(...)`) is declared
in `__all__`; private names stop crossing modules.

**Done when** `urdido --help` lists every command and a refused build raised from Python
is an exception, not an exit.

### §UR25 One polyweave adapter behind provider seams

`prepare.py:43-54` (`voice.lines`), `library.py:225-239` (`stock.fetch`,
`reference.register`, `reference.frames`, `provenance.credits`) and `instances.py:253`
(`capture.web`, with the PW710 workaround) each run `python -m polyweave ... --json`;
`prepare.py:136` reads `polyweave.toml` for Scribe prices.

One `urdido.providers.polyweave` module owns the subprocess contract and the refusal
parsing, behind small protocols the rest of the code calls: voice, stock, reference
frames, web capture. It stays a subprocess: polyweave's stable contract is its CLI, not
its modules. Without polyweave installed, an operation that needs it refuses with `pip
install urdido[polyweave]`.

**Done when** no module outside the adapter mentions polyweave, and the library, prepare
and instance tests pass against a fake provider.

### §UR26 A transcriber seam

`narration_words.py:15-47` posts to Scribe with `requests` and `ELEVENLABS_API_KEY`,
defaults to `pt-BR`/`por`, and `prepare.py` prices it from `polyweave.toml`. Put a
`Transcriber` protocol in front of it, with the Scribe client as one implementation in
the `narration` extra and polyweave's `sound.speech` as another once PW703 lands. The
language comes from the declaration, never a default. The hash-bound word records stay
the contract every caller reads.

UR13 (takes heard back) and UR7 (re-roll) build on the same seam.

**Done when** the anchor, highlight and prepare tests run against a fake transcriber,
and the language default is gone.

### §UR27 Publishing texts by locale and by target

`publish/description.py:39-157` holds "Capítulos", "Fontes e demonstrações", "Apoio",
"Capturas próprias", licence prefixes in Portuguese and a default ElevenLabs credit;
`sources/illustrated.py:387` writes "0:00 Introdução". The 5,000-unit limit, youtu.be
shortening and the Shorts safe area are YouTube's; `cuts/render.py:45-47` defaults the
languages to `en` and `pt-BR`.

A strings table per language, chosen by the build's language and overridable in the
declaration, and a publishing target (YouTube first) that owns the limits, link
shortening and safe areas. `scion()` in `description.py:152` is dead and goes.

**Done when** an English build writes an English description, and no Portuguese literal
remains outside the pt-BR table.

### §UR28 One video's needs out of the core

`build.py:299-343` visits `/?post_type=product` with WooCommerce selectors to take store
screenshots for the opening; `build.py:357-360` copies stills into the Turing site;
`publish/__init__.py:46-75` writes a TypeScript module and a marked block into Turing's
docs. The chaptered pipeline (`sources/recording`, `assemble/clip`, `assemble/video`,
the teaser and vertical cuts) reads `chapters.json` as Turing's e2e specs write it and
keeps JS-parity rounding.

Decide per piece: the chaptered source stays as a generic kind if its contract can be
stated without Turing; the store screenshots become declared web captures; the
transcript and stills publishing become a declared output, or a hook marketing owns.
Nothing in the package writes into another repository unless the declaration says where.

**Done when** no module names WooCommerce, Turing or a path outside the declared roots,
and the WordPress demo still builds.

### §UR29 Browser and layout without machine assumptions

`cards/render.py:35-41` and `build.py:316` default the Playwright channel to `msedge`
and look for `msedge.exe` under `PROGRAMFILES` and `LOCALAPPDATA`; elsewhere the
executable is `None` and caching is refused. `thumbnail.py:85` runs `exec_module` on the
declaration's `layout = "../brand/brand.py"`.

Default to Playwright's bundled Chromium, identified by its own version for the cache,
with the channel an opt-in in the declaration. Thumbnail layouts register through an
entry point group (`urdido.thumbnail_layouts`) or a declared module name, with a
documented function signature; japode's `brand.py` becomes one.

**Done when** the card and thumbnail tests pass on Linux CI, and the Japode thumbnail
still renders through the declared layout.

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

### §UR31 Tests on synthetic fixtures

`test_assemble_clip`, `test_cache`, `test_captions`, `test_cards`, `test_description`,
`test_mix`, `test_preflight`, `test_preview`, `test_publish`, `test_scenes` and
`tests/js/terminal.mjs` read `japode/brand/fonts`, `japode/wordpress/cards.json`,
`turing/wordpress/demo/narration`, `shio/promo/` or `D:\Git\viglet\turing`.

Replace them with fixtures under `tests/fixtures/`: media generated by ffmpeg lavfi at
test time, an OFL font, small declarations and storyboards written for the tests.
Markers say what each test needs (`ffmpeg`, `browser`, `node`, `full`), and the gate
reports skips by marker. The JS-parity oracles (`tests/oracles/`) come along as data.

**Done when** the whole suite runs in CI with no path outside this repository.

### §UR32 Cache keys that survive an install

`cache.py:51-58` keys each stage on the absolute path of `cache.py` and of every input.
Installing urdido instead of the in-repo package changes every key, and the tracked
`*.cache.json` under `japode/*/video/parts/` all miss.

Key the code by the package version plus a hash of the modules a stage runs, and inputs
by content hash with paths relative to the declared roots. Keep a one-time reader for
the old format that reports what it can no longer verify.

**Done when** a build cached in one checkout hits its cache from another checkout of the
same version, and an upgrade misses only the stages whose code changed.

### §UR33 One pipeline per source kind

`Build` in `build.py` resolves roots, loads hash-pinned JSON, runs the chaptered
(`:188`) and scenes (`:377`) pipelines, scrapes the store, writes stills, the Resolve
project, the final mux and the mix, and imports about thirty modules; `prepare.py:22`
imports it back. Split it into a declaration loader, one pipeline per source kind behind
a common interface, and shared finishing stages (mix, mux, QA, revisions, description).

The illustrated path, today the most checked, sets the shape the others follow. Sources
become pluggable through an entry point group, so a project can add one without forking.

**Done when** each pipeline has its own module and tests, and `build.py` is the
orchestration alone.

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

**Done when** `node turing/wordpress/test/golden/run.mjs` passes against the installed
urdido with the expected files unchanged.

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

### §UR1 Titles and thumbnails checked as a pair (was marketing VM30)

The Scion thumbnail says "O Git não aguentou" and "30 mil merges por dia"; its title is
"30 mil merges por dia: o Git não aguentou e a Anthropic...", which the Studio list
itself shows cut. The two say the same thing twice and the end of the title is never
read.

Rules from youtube-agent-skill's title linter and the thumbnail guides of claude-youtube
and youtube-agent-pro, read on 2026-11-12:

- a title keeps its point inside 60 characters (desktop search) and ideally 40 (the phone feed); 100 is only YouTube's hard limit;
- a number, a name or a date in it; at most two words in capitals; no empty superlatives;
- the thumbnail shares no meaningful word with the title: it adds what the title leaves out (a picture of the stakes, a number the title does not say);
- three words on the thumbnail at most, legible at about 168 x 94 px, one face or one object, two or three colours;
- the first five seconds of the video continue the thumbnail's promise;
- a Short's title stays under 60 characters, with 3 to 5 hashtags in the description.

The check runs where the thumbnail and the description are made, and refuses a pair that
breaks the first three rules. The Google Ads limits already written in japode/brand
stay.

Done when the Scion and Docker titles and thumbnails pass the check, or are rewritten
until they do.

### §UR2 Shorts cut by the framework (was marketing VM31)

The Docker and Scion Shorts are cut by scripts copied into each video
(japode/*/bin/short.py); only the Scion copy carries what was learned on 2026-11-12.

What the Scion cutter does now, and every video's Shorts should:

- no frozen end card: a Short is replayed in a loop and replays count, so the last word runs straight back into the hook; the pointer to the full video replaces the hook for the last 2.6 s, over the moving picture;
- a visual change every 2 to 4 s: a shot longer than 3.6 s is punched in to 1.1 at its middle (never a terminal, whose lines the 4:3 cut already trims);
- the voice 1.1 times faster, pitch kept, and 0.35 s after the last word;
- captions burned in, word-timed, 20 characters a line, numbers in the brand's green, inside the safe area (clear of the right 140 px from y 900 to 1700 and of the bottom 420 px);
- the channel's look: night green with the glow, green rules around the picture;
- loudness near -14 LUFS, true peak under -1 dBTP;
- three Shorts per long video, posted a day or more apart, each self-contained, 20 to 55 s, opening on a number.

Sources: Melvynx/video-agent-skills, Ansub/long-to-shorts, youtube-agent-skill.
claude-youtube adds that a Short's related-video link converts under 1%: Shorts get the
channel found, they do not feed the long video.

Done when video-maker cuts the Shorts from any built video's plan and both Japode videos
use it.

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
- the Shorts, through VM31.

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

### §UR7 A take cannot be re-rolled with the same text (was marketing VM70)

Where it happened: `japode/wordpress2`, the chapter-1 take bought on 2026-11-16
(eleven_v3, Leo Antonio, pt-BR). The owner heard European Portuguese between 0:28 and
0:35 of the cut. The build, the Scribe transcription and the QA all passed. Scribe
reports only `por`, so nothing told Brazilian from European Portuguese.

What was done by hand: the narration buyer has no way to buy a take again when its text
has not changed (`video-maker/narration/buy.mjs` treats the take as current). To get a
new take, the text had to be rewritten. That worked here because more Brazilian phrasing
("fazia meses que ninguém atualizava") also helps the accent, but a take with good text
could not be re-rolled at all.

What video-maker should do:
- let a take be marked for re-purchase (`retake = ["chapter-1"]`, or a `--retake` option), with
  the reason kept in the ledger;
- record which takes the owner flagged for accent, so a voice or model that keeps drifting shows
  up across videos.

### §UR8 A thumbnail picture is not checked against the video (was marketing VM73)

Where it happened: `japode/wordpress2`, on 2026-11-16 (`python -m videomaker thumbnail
japode/wordpress2/video.toml --language pt-BR`). The owner asked for the WordPress logo
alone in place of Matt Mullenweg.

What happened: the only large logo in the video's sources is inside the 20th-anniversary
emblem (`wp20.webm`). Cropping the W alone would have stretched about 140 px to 660. So
the official mark was downloaded by hand from wordpress.org/about/logos into
`footage/wordpress-wmark-white.png`, with a hand-written `.prov.json` (trademark policy,
URL, hash). It does not appear in the cut. `thumbnail.py` says every picture is a frame
of the video's own sources, but it checks only that the file exists. The white mark on
transparent landed well on the layout's background by luck: nothing declares how a
graphic is placed (size, margin, background).

What video-maker should do:
- check that `thumbnail.picture` and `thumbnail.proof` are media the storyboard declares, or
  sources the cut shows, and refuse otherwise unless the declaration marks them as thumbnail-only
  with a reason;
- require their provenance (license, author, URL) like any storyboard media;
- let a graphic declare its placement instead of the photo-style `cover` crop.

### §UR9 Descriptions for scene videos (was marketing VM80)

`[description]` writes a ready description with measured chapter times, but only for the
illustrated source (`sources/illustrated.py`). The Viglet Shio promo is made of filmed
scenes, so on 2026-11-17 its chapter times were read by hand: the first caption of each
chapter's card line, matched by its first words in promo.pt-BR.srt. Two takes bought
later the same day moved five chapters by a second, and the draft had to be corrected
again.

The timeline already knows where each chapter starts; the scenes build should write the
same description file from it, with the chapter titles from the script and the notes
from `[description]`.

**Done when** the Viglet Shio promo's build writes its description with chapter times,
and the draft in alegauss/visibility takes them from it.

### §UR10 One command records a scene video (was marketing VM81)

Recording the Viglet Shio promo is six commands from its README, in an order that
matters: the first scenes on a fresh instance, the agent's session, the terminal
replays, the later scenes on the same instance with --reuse, the cold open, then the
instance down. On 2026-11-17 they were chained by hand with `&&` behind `| tail`, so
when the chapter-2 scene timed out on a new image the agent still ran, on an instance
with no Quilhara, and wrote a useless session over the good one. The previous recordings
had to be copied aside by hand first, because a re-recording overwrites them.

`videomaker record` should run the steps declared in video.toml (each a command and the
scenes it makes), stop at the first failure, keep the last complete recording until the
new one is complete, and say which step to resume from.

**Done when** the Viglet Shio promo is recorded with one command, and a failing scene
leaves the previous recording intact.

### §UR11 A session checked against its chapters (was marketing VM82)

The Viglet Shio promo's chapters 3 to 6 replay a real Claude Code session, and the
narration says what happens in it: the plugin's skill loads, the agent asks Viglet Shio
what is there, a call goes wrong and Viglet Shio says how to fix it, the agent checks
its work once before saying it is done. On 2026-11-17 three sessions were recorded and
read by hand with one-off Python: one had no skill and no verify, the next no skill and
no error, and the agent wrote one line in English in a Portuguese session. The fourth,
on the new image, did have Viglet Shio's teaching errors (inside shio_read's answer),
but the hand check missed them because the text was escaped in the JSON, and a correct
line was rewritten and bought twice before the cut showed them in red.

terminal.json's selectors already name what each chapter shows. A selector marked
required should refuse a session where it picks nothing, a count should refuse two
reports where one is wanted, and lines in the wrong language should be reported, so a
session is judged before anything is filmed after it.

**Done when** a session missing a required beat is refused with the chapter and the
selector that found nothing.

### §UR12 A review sheet for scene videos (was marketing VM83)

`videomaker build --plan` prints a review sheet for illustrated videos (`review.sheet`),
one frame per beat with its line. A video made of filmed scenes has none. On 2026-11-17
every check of the Viglet Shio promo was a frame grabbed by hand: the corner mark over
the console and over a light page, the purple closing card, the Marketplace search, the
agent's prompt and its final report, the thumbnail at 320x180 and 168x94. Each was an
ffmpeg call with a guessed second and a stacked image in the scratchpad.

The build knows where each chapter, card and line sits. It should write a contact sheet
for a scene video: a frame at the start, the middle and the end of each chapter with its
title and spoken line, the cold open, and the closing card, and the thumbnail at the two
feed sizes beside it.

**Done when** the Viglet Shio promo's build writes a sheet that shows each of those
without a hand-picked second.

### §UR13 Takes heard back (was marketing VM84)

`pronounce` in a script changes what is sent to the voice, but nothing listens to what
came back. On 2026-11-17 the Alexandre heard "agentes de Ía" at the start of the Viglet
Shio promo; "IA" went into the pt-BR pronounce map as "iá" and three takes were bought
again, and the only proof was the text sent (lines.json), not the sound. No
speech-to-text is installed on this machine.

After a take is bought, a transcription of it should be compared with the line: words
missing or added, and every word the pronounce map names, reported per take with its
second, so a take that says something else is refused before it is cut in. The
transcriber is a declared dependency of video-maker, not something each session
installs.

**Done when** the Viglet Shio promo's takes are transcribed on purchase and a take that
drops or garbles a mapped word is reported.

### §UR14 A flash refused before the owner sees it (was marketing VM86)

On 2026-11-17 the Alexandre saw the Viglet Shio promo flash at 0:40. One frame at 40.667
s averaged 234 in luma between frames of 26 to 43: the first frame of chapter-2.webm,
which Playwright films as the empty white page before the scene's first navigation
paints. Six of the sixteen scene clips start on that white frame; the others did not
show because the page after them is light too. The recording now cuts each clip at its
first paint, but nothing in the build would have refused the flash.

After that fix the Alexandre still saw 0:40 flash: one frame of the console's loading
dashboard, the same brightness as its neighbours (luma 39 against 43) but a different
picture (ffmpeg YDIF 7.6, then 7.9 back), which a brightness scan let through. The final
verification should compare each frame with its neighbours, by picture difference and
not only brightness, and refuse a change that lasts a frame or two and comes back (a
flash), naming the second and the clip it came from, so a blank frame from any source is
refused rather than published. polyweave's `measure.flashes` may already be the
measurement.

**Done when** the build refuses a cut with a one-frame white flash between dark frames,
and the Viglet Shio promo passes.

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
