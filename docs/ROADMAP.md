# Roadmap (active backlog)

## Block A — Package foundation (urdido installable from PyPI)

## Block B — The engine extracted (videomaker without marketing)

- 📋 **UR46** (deps: UR22 ✅, UR37) **Four environment variables still fill undeclared roots, the last root names left in a module** — They were kept for one release so marketing's builds keep working; left longer, the shim becomes a second way to declare a root. → §UR46
- 📋 **UR47** (deps: UR23 ✅) **Values in video.toml are untyped and the side files it names are not checked, so a typo inside them is still a KeyError** — urdido check refuses a misspelled table key, but storyboard.json or script.json still fail deep inside the build. → §UR47
- 📋 **UR49** (deps: UR24 ✅) **Building a video from Python means filling an argparse Namespace and importing build internals** — The package exports only its errors, so an embedding program reaches into Build and the modules' underscored names. → §UR49

## Block C — Adoption in marketing (video-maker replaced by urdido)

- 📋 **UR37** (deps: UR36 ⏸, UR24 ✅) **Marketing's npm scripts, READMEs, bin scripts and brand code call python -m videomaker or import videomaker** — A flag-day rename across about twenty files would break whichever video is mid-build, so the switch needs a bridge. → §UR37
- 📋 **UR38** (deps: UR30 ✅, UR36 ⏸) **Project scripts and Turing's e2e specs import narration and recording helpers by a relative path into video-maker/** — Turing's story specs reach takes.mjs through marketing, so removing the folder breaks a recording in another repository. → §UR38
- 📋 **UR39** (deps: UR36 ⏸, UR31 ✅) **The golden check proves one marketing video but lives inside the framework, reading the Turing repository** — It belongs to the WordPress demo, and in urdido it would be a test that only runs on one machine. → §UR39
- 📋 **UR41** (deps: UR37, UR38, UR39) **Nothing proves that each published video comes out the same when built by urdido instead of video-maker** — A changed cut found after re-upload costs a published video, and the owner should not be the check. → §UR41
- 📋 **UR42** (deps: UR41, UR40 ⏸) **video-maker/ still sits in marketing after every video is built by urdido** — Two copies of the framework drift on the first fix applied to only one of them. → §UR42

## Block D — Inherited from video-maker (marketing Block B)

- 📋 **UR3** (deps: marketing: VM28) **Published videos have no end screen or cards pointing to the next video on the subject** — A viewer who finishes the Docker video is not offered the Scion one, and the end screen should point at the continuation, not the newest upload. → §UR3
- 🛠 **UR4** (deps: UR2 ✅, UR33 ✅, UR36 ⏸, UR53) **The Japode explainer videos are built by scripts copied into each video, outside video-maker** — The Japode videos declare their styles, closing, mark and credits, build with urdido, drop their bin scripts and reproduce their published cuts. → §UR4
- ⏳ **UR5** (deps: UR21 ✅, marketing: VM32) **A second cut of a video, to test a new opening, means copying the whole video folder and its declaration** — The review records which variant was uploaded and which retention report it is compared against, once marketing's VM32 review exists. → §UR5
- 📋 **UR44** (deps: polyweave: PW720) **A retake moves the old take's files aside by hand because voice.lines cannot buy a current take again** — Moving files behind polyweave's back is a workaround that a crash mid-run can leave half done. → §UR44
- 🛠 **UR45** (deps: UR14 ✅) **The flash scan's threshold was set on synthetic frames, never on the Shio flash or a published cut** — At 32x18 a same-brightness flash may slip under the threshold, and a published cut may be refused for a blink that is fine. → §UR45
- 📋 **UR48** (deps: UR2 ✅) **[shorts] is read by two cutters with different keys, so nothing says which cutter a key belongs to** — The scenes selection and urdido shorts share one table name, and a declaration can mix their keys unnoticed. → §UR48
- 📋 **UR53** (deps: UR51 ✅) **An explainer's page film and terminal session are recorded by scripts copied into each video** — The Scion and Docker videos film a highlighted web page and a real shell session with their own bin scripts. → §UR53

## Done when — UR19

- **0.1.0 installs from PyPI and urdido build --help answers** In a fresh virtualenv,
  pip install urdido==0.1.0 succeeds and urdido build --help prints its usage, which
  needs the trusted publishers registered and the build command in the wheel.

## Done when — UR30

- **urdido-record installs from the npm registry by name** npm install urdido-record in
  a fresh folder brings the helpers at the Python package's version, and an import of
  urdido-record/terminal-replay resolves.

## Done when — UR39

- **urdido's suite runs in CI with no path outside its repository** With
  URDIDO_MARKETING pointing nowhere, the gate's summary names no test skipped for the
  marketing checkout or a sibling repository.

## Done when — UR5

- **The review names the uploaded variant and its retention report** A variant's review
  records which cut was uploaded and the retention report it is compared against, so two
  openings of one episode are judged side by side.

## Done when — UR4

- **The Japode videos build with urdido and drop their bin scripts** japode/scion and
  japode/docker each build from a video.toml with urdido build, their bin/build.py and
  short.py are gone, and the published cuts come out the same.

## Done when — UR43

- **No baseline is left in pyproject.toml** pyproject.toml has neither per-file ignores
  nor format exclusions, and ruff check and ruff format --check pass on the whole tree.

## Non-goals
