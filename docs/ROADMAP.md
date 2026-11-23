# Roadmap (active backlog)

## Block A — Package foundation (urdido installable from PyPI)

## Block B — The engine extracted (videomaker without marketing)

## Block C — Adoption in marketing (video-maker replaced by urdido)

## Block D — Inherited from video-maker (marketing Block B)

- 📋 **UR3** (deps: marketing: VM28) **Published videos have no end screen or cards pointing to the next video on the subject** — A viewer who finishes the Docker video is not offered the Scion one, and the end screen should point at the continuation, not the newest upload. → §UR3
- 🛠 **UR4** (deps: UR2 ✅, UR33 ✅, UR36 ✅, UR53 ⏳) **The Japode explainer videos are built by scripts copied into each video, outside video-maker** — The Japode videos declare their styles, closing, mark and credits, build with urdido, drop their bin scripts and reproduce their published cuts. → §UR4
- ⏳ **UR5** (deps: UR21 ✅, marketing: VM32) **A second cut of a video, to test a new opening, means copying the whole video folder and its declaration** — The review records which variant was uploaded and which retention report it is compared against, once marketing's VM32 review exists. → §UR5
- 📋 **UR44** (deps: polyweave: PW720) **A retake moves the old take's files aside by hand because voice.lines cannot buy a current take again** — Moving files behind polyweave's back is a workaround that a crash mid-run can leave half done. → §UR44
- ⏳ **UR53** (deps: UR51 ✅, polyweave: PW721) **An explainer's page film and terminal session are recorded by scripts copied into each video** — The page film (find and highlight a quoted sentence) waits on polyweave capture.web; then Scion's bin scripts go. → §UR53
- 📋 **UR64** (deps: —) **A video's long cut and its Shorts take one build call each, and nothing says a Short is older than its scenes** — The Viglet Shio promo's Shorts stayed cut from scenes replaced on 2026-11-18 while its long cut was current. → §UR64
- 📋 **UR65** (deps: —) **urdido check passes a declaration whose cards have no words for a declared language, and build dies on a KeyError** — The Viglet Shio promo's English build crashed on cards.json after its scenes were filmed, though check had said it passes. → §UR65
- 📋 **UR66** (deps: —) **A take bought without word times passes check, and the build's refusal names a module instead of the command** — The Viglet Shio promo's English build stopped on 'run urdido.narration_words' after check passed and ten takes were bought. → §UR66
- 🛠 **UR70** (deps: —) **A chaptered video cannot open on its product working: the opening order is fixed and takes nothing from the recording** — The Turing WordPress demo shows its first search answering at 1:08, and only a cold open from its recording can bring it under 20 s. → §UR70

## Done when — UR19

- **0.1.0 installs from PyPI and urdido build --help answers** In a fresh virtualenv,
  pip install urdido==0.1.0 succeeds and urdido build --help prints its usage, which
  needs the trusted publishers registered and the build command in the wheel.

## Done when — UR30

- **urdido-record installs from the npm registry by name** npm install urdido-record in
  a fresh folder brings the helpers at the Python package's version, and an import of
  urdido-record/terminal-replay resolves.

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

## Done when — UR53

- **Scion's page shots are filmed by a declared visit through capture.web.** urdido
  record on the Scion declaration makes footage/page/*.webm with no bin script.

## Non-goals
