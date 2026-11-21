# Roadmap (active backlog)

## Block A — Package foundation (urdido installable from PyPI)

- ⏳ **UR20** (deps: UR16 ✅, UR17 ✅, UR35) **An agent working in this repo or driving urdido has no CLAUDE.md, skill or friction path** — Consumers still have no urdido skill on declaring and building a video, which waits for the code and its manual. → §UR20
- 📋 **UR35** (deps: UR16 ✅, UR23 ✅) **Nobody outside this machine can learn what a declaration accepts or how to build a first video** — A package on PyPI is read by people who never saw marketing, and today the only manual is a 600-line README full of VM ids. → §UR35

## Block B — The engine extracted (videomaker without marketing)

- 📋 **UR30** (deps: UR21 ✅) **The Python build shells out to node for the opening gate, and the JavaScript helpers have no install path** — A pip install brings no .mjs files, and eight project scripts and Turing's e2e specs import them by relative path. → §UR30
- 📋 **UR31** (deps: UR21 ✅) **Ten test files read japode, shio and turing folders, so the suite cannot run outside marketing** — CI here has none of those folders, and a test that skips everywhere but one machine proves nothing. → §UR31
- 📋 **UR32** (deps: UR21 ✅, UR22 ✅) **Every stage cache is keyed on absolute module and input paths, so moving the code invalidates every cache** — Each marketing video would rebuild from scratch on install, and caches would never be shared between two checkouts. → §UR32
- 📋 **UR33** (deps: UR22 ✅, UR28 ✅, UR23 ✅) **build.py holds both pipelines, the mux, the mix and every root in one 600-line class** — Each new source kind or check lands in that class, and nobody can test one pipeline without loading the others. → §UR33
- 📋 **UR34** (deps: —) **Polyweave's open tasks PW712 to PW716 describe video composition that urdido now owns** — Two roadmaps planning the same preflight, preview, progress and claims will build them twice or wait on each other. → §UR34
- 📋 **UR43** (deps: UR21 ✅) **The imported modules pass ruff only through a per-file baseline of ignored rules and unformatted files** — Each ignored B023 or B905 may hide a real bug, and new code in those files is checked against nothing. → §UR43
- 📋 **UR46** (deps: UR22 ✅, UR37) **Four environment variables still fill undeclared roots, the last root names left in a module** — They were kept for one release so marketing's builds keep working; left longer, the shim becomes a second way to declare a root. → §UR46
- 📋 **UR47** (deps: UR23 ✅) **Values in video.toml are untyped and the side files it names are not checked, so a typo inside them is still a KeyError** — urdido check refuses a misspelled table key, but storyboard.json or script.json still fail deep inside the build. → §UR47
- 📋 **UR49** (deps: UR24 ✅) **Building a video from Python means filling an argparse Namespace and importing build internals** — The package exports only its errors, so an embedding program reaches into Build and the modules' underscored names. → §UR49

## Block C — Adoption in marketing (video-maker replaced by urdido)

- 📋 **UR36** (deps: UR21 ✅) **Marketing installs the framework from its own folder with pip -e, with no version pinned** — Replacing the folder needs an install that does not point into it, and a pin says which urdido a video was built with. → §UR36
- 📋 **UR37** (deps: UR36, UR24 ✅) **Marketing's npm scripts, READMEs, bin scripts and brand code call python -m videomaker or import videomaker** — A flag-day rename across about twenty files would break whichever video is mid-build, so the switch needs a bridge. → §UR37
- 📋 **UR38** (deps: UR30, UR36) **Project scripts and Turing's e2e specs import narration and recording helpers by a relative path into video-maker/** — Turing's story specs reach takes.mjs through marketing, so removing the folder breaks a recording in another repository. → §UR38
- 📋 **UR39** (deps: UR36, UR31) **The golden check proves one marketing video but lives inside the framework, reading the Turing repository** — It belongs to the WordPress demo, and in urdido it would be a test that only runs on one machine. → §UR39
- 📋 **UR40** (deps: UR20 ⏳) **Marketing's video-maker gate hook, friction skill and CLAUDE.md rules point at a folder and a Block B that will be gone** — The rule that every friction becomes a framework task stops working the day the folder leaves, unless it points here. → §UR40
- 📋 **UR41** (deps: UR37, UR38, UR39) **Nothing proves that each published video comes out the same when built by urdido instead of video-maker** — A changed cut found after re-upload costs a published video, and the owner should not be the check. → §UR41
- 📋 **UR42** (deps: UR41, UR40) **video-maker/ still sits in marketing after every video is built by urdido** — Two copies of the framework drift on the first fix applied to only one of them. → §UR42

## Block D — Inherited from video-maker (marketing Block B)

- 📋 **UR3** (deps: marketing: VM28) **Published videos have no end screen or cards pointing to the next video on the subject** — A viewer who finishes the Docker video is not offered the Scion one, and the end screen should point at the continuation, not the newest upload. → §UR3
- 🛠 **UR4** (deps: UR2 ✅, UR33) **The Japode explainer videos are built by scripts copied into each video, outside video-maker** — video-maker only knows the recorded product demo, so the first video of another kind went around it, and its two copies already differ. → §UR4
- 📋 **UR5** (deps: UR21 ✅, UR33) **A second cut of a video, to test a new opening, means copying the whole video folder and its declaration** — Retention tests need several openings of the same episode, and each copy duplicates 722 MB and drifts from the published cut on every later fix. → §UR5
- 📋 **UR44** (deps: polyweave: PW720) **A retake moves the old take's files aside by hand because voice.lines cannot buy a current take again** — Moving files behind polyweave's back is a workaround that a crash mid-run can leave half done. → §UR44
- 📋 **UR45** (deps: UR14 ✅) **The flash scan's threshold was set on synthetic frames, never on the Shio flash or a published cut** — At 32x18 a same-brightness flash may slip under the threshold, and a published cut may be refused for a blink that is fine. → §UR45
- 📋 **UR48** (deps: UR2 ✅) **[shorts] is read by two cutters with different keys, so nothing says which cutter a key belongs to** — The scenes selection and urdido shorts share one table name, and a declaration can mix their keys unnoticed. → §UR48

## Done when — UR19

- **0.1.0 installs from PyPI and urdido build --help answers** In a fresh virtualenv,
  pip install urdido==0.1.0 succeeds and urdido build --help prints its usage, which
  needs the trusted publishers registered and the build command in the wheel.

## Done when — UR20

- **An urdido skill teaches a consumer to declare and build a video** A session in
  marketing, given only the skill, writes a video.toml that urdido build accepts, with
  the commands and tables taken from the manual UR35 writes rather than from
  video-maker's README.

## Non-goals
