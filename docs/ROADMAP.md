# Roadmap (active backlog)

## Block A — Package foundation (urdido installable from PyPI)

- ⏳ **UR19** (deps: UR18 ✅, UR24) **A version cannot reach PyPI except by a hand-run upload with a token** — Releasing 0.1.0 still needs the trusted publishers registered on PyPI and TestPyPI, and a wheel that carries urdido build and its package data. → §UR19
- 📋 **UR20** (deps: UR16 ✅, UR17 ✅) **An agent working in this repo or driving urdido has no CLAUDE.md, skill or friction path** — Marketing's rule that every friction becomes a framework task only works if the agent knows where and how to file it. → §UR20
- 📋 **UR35** (deps: UR16 ✅, UR23) **Nobody outside this machine can learn what a declaration accepts or how to build a first video** — A package on PyPI is read by people who never saw marketing, and today the only manual is a 600-line README full of VM ids. → §UR35

## Block B — The engine extracted (videomaker without marketing)

- 📋 **UR21** (deps: UR16 ✅) **urdido holds none of the videomaker code, and marketing's history of each module would be lost by a copy** — Sixty-six shipped tasks explain why each module is the way it is, and the blame is how the next change finds them. → §UR21
- 📋 **UR22** (deps: UR21) **The build defaults its roots to sibling Turing and Shio checkouts and writes to a fixed video/ folder** — A video declared anywhere else gets paths that climb out of its own project, and the root names are wired into the code. → §UR22
- 📋 **UR23** (deps: UR21) **A misspelled or missing key in video.toml fails as a KeyError deep inside the build** — Only the illustrated path is checked before rendering, so a typo in any other table costs a partial build to find. → §UR23
- 📋 **UR24** (deps: UR21) **Library code raises SystemExit and the CLI is an if-chain, so urdido can be neither embedded nor discovered** — A package is used from other Python code and by agents reading --help, and both see an exit or a usage line naming two of seven commands. → §UR24
- 📋 **UR25** (deps: UR21, UR24) **Polyweave is called through three separate subprocess wrappers, and its polyweave.toml is read directly** — Each wrapper parses answers its own way and a change to polyweave's config breaks urdido silently. → §UR25
- 📋 **UR26** (deps: UR25) **Word times come from a direct ElevenLabs Scribe call inside the package, with no provider seam** — polyweave PW703 is meant to supply word times, and a second transcriber should not mean editing every caller. → §UR26
- 📋 **UR27** (deps: UR21) **Description, chapter and credit texts are hardcoded in Portuguese, and the description is shaped only for YouTube** — An English video gets Capitulos and Introducao, and a target other than YouTube cannot change the limits or the links. → §UR27
- 📋 **UR28** (deps: UR22) **The Turing WordPress demo's store scraper, stills and transcript publishing live inside the core build** — WooCommerce selectors and writes into the Turing repository are one video's needs, and every user of the package carries them. → §UR28
- 📋 **UR29** (deps: UR21) **Cards render only with a Windows Edge install, and thumbnail layouts load any brand.py by its path** — A Linux CI or another user has no msedge.exe, and executing a file named in a declaration is a plugin system with no contract. → §UR29
- 📋 **UR30** (deps: UR21) **The Python build shells out to node for the opening gate, and the JavaScript helpers have no install path** — A pip install brings no .mjs files, and eight project scripts and Turing's e2e specs import them by relative path. → §UR30
- 📋 **UR31** (deps: UR21) **Ten test files read japode, shio and turing folders, so the suite cannot run outside marketing** — CI here has none of those folders, and a test that skips everywhere but one machine proves nothing. → §UR31
- 📋 **UR32** (deps: UR21, UR22) **Every stage cache is keyed on absolute module and input paths, so moving the code invalidates every cache** — Each marketing video would rebuild from scratch on install, and caches would never be shared between two checkouts. → §UR32
- 📋 **UR33** (deps: UR22, UR28, UR23) **build.py holds both pipelines, the mux, the mix and every root in one 600-line class** — Each new source kind or check lands in that class, and nobody can test one pipeline without loading the others. → §UR33
- 📋 **UR34** (deps: —) **Polyweave's open tasks PW712 to PW716 describe video composition that urdido now owns** — Two roadmaps planning the same preflight, preview, progress and claims will build them twice or wait on each other. → §UR34

## Block C — Adoption in marketing (video-maker replaced by urdido)

- 📋 **UR36** (deps: UR21) **Marketing installs the framework from its own folder with pip -e, with no version pinned** — Replacing the folder needs an install that does not point into it, and a pin says which urdido a video was built with. → §UR36
- 📋 **UR37** (deps: UR36, UR24) **Marketing's npm scripts, READMEs, bin scripts and brand code call python -m videomaker or import videomaker** — A flag-day rename across about twenty files would break whichever video is mid-build, so the switch needs a bridge. → §UR37
- 📋 **UR38** (deps: UR30, UR36) **Project scripts and Turing's e2e specs import narration and recording helpers by a relative path into video-maker/** — Turing's story specs reach takes.mjs through marketing, so removing the folder breaks a recording in another repository. → §UR38
- 📋 **UR39** (deps: UR36, UR31) **The golden check proves one marketing video but lives inside the framework, reading the Turing repository** — It belongs to the WordPress demo, and in urdido it would be a test that only runs on one machine. → §UR39
- 📋 **UR40** (deps: UR20) **Marketing's video-maker gate hook, friction skill and CLAUDE.md rules point at a folder and a Block B that will be gone** — The rule that every friction becomes a framework task stops working the day the folder leaves, unless it points here. → §UR40
- 📋 **UR41** (deps: UR37, UR38, UR39) **Nothing proves that each published video comes out the same when built by urdido instead of video-maker** — A changed cut found after re-upload costs a published video, and the owner should not be the check. → §UR41
- 📋 **UR42** (deps: UR41, UR40) **video-maker/ still sits in marketing after every video is built by urdido** — Two copies of the framework drift on the first fix applied to only one of them. → §UR42

## Block D — Inherited from video-maker (marketing Block B)

- 📋 **UR1** (deps: polyweave: PW699) **Titles and thumbnails go out unchecked, so the Scion thumbnail repeats its title and the feed cuts the title** — A thumbnail should add what the title leaves out, and a title keeps its point inside 40 to 60 characters or the feed cuts it. → §UR1
- 📋 **UR2** (deps: polyweave: PW697, polyweave: PW698) **Each video cuts its Shorts with its own copied script, and the Shorts rules live only in japode/scion** — Shorts are how a new channel gets found, and the loop, pacing, safe-area and loudness rules learned on 2026-11-12 must hold for every video. → §UR2
- 📋 **UR3** (deps: marketing: VM28) **Published videos have no end screen or cards pointing to the next video on the subject** — A viewer who finishes the Docker video is not offered the Scion one, and the end screen should point at the continuation, not the newest upload. → §UR3
- 📋 **UR4** (deps: UR2) **The Japode explainer videos are built by scripts copied into each video, outside video-maker** — video-maker only knows the recorded product demo, so the first video of another kind went around it, and its two copies already differ. → §UR4
- 📋 **UR5** (deps: UR21) **A second cut of a video, to test a new opening, means copying the whole video folder and its declaration** — Retention tests need several openings of the same episode, and each copy duplicates 722 MB and drifts from the published cut on every later fix. → §UR5
- 📋 **UR6** (deps: UR21) **A stock clip already rejected for contradicting the narration can come back into a cut without any check refusing it** — The review that removed it is lost on the next edit, and the owner has to catch the same bad shot again. → §UR6
- 📋 **UR7** (deps: UR21) **A narration take with the wrong accent cannot be bought again unless its text changes** — eleven_v3 sometimes drifts into European Portuguese, and the only way to re-roll the take is to rewrite a line that was already right. → §UR7
- 📋 **UR8** (deps: UR21) **A thumbnail picture can be any file in the folder, unchecked against the video's media or its licence** — The thumbnail is the promise the video must keep, and a logo or photo fetched by hand reaches it with no provenance check. → §UR8
- 📋 **UR9** (deps: UR21) **A video made of filmed scenes gets no YouTube description or chapter times from its build** — The Viglet Shio promo's chapter times were read by hand from its captions, and every new cut moves them. → §UR9
- 📋 **UR10** (deps: UR21) **A scene video is recorded by running its README's commands in order by hand, and a failed step does not stop the next** — The Viglet Shio promo's agent session ran on an instance whose Marketplace scene had failed, and the order lives only in prose. → §UR10
- 📋 **UR11** (deps: UR21) **An agent's recorded session is not checked against what the narration says it shows** — The Shio promo's sessions were read by hand three times for a skill, one verify and an error the lines claim, and two lacked them. → §UR11
- 📋 **UR12** (deps: UR21) **A scene video has no review sheet: frames to look at are pulled one by one with ffmpeg** — Checking the Shio promo's mark, cards, search and terminal took about ten hand-made ffmpeg grabs; illustrated videos get a sheet. → §UR12
- 📋 **UR13** (deps: UR21) **A bought take is never heard back, so a word the voice says wrong is caught only by the owner watching** — The Alexandre heard "Ía" for IA in the Shio promo; after the pronounce fix nothing could confirm "iá" was what the voice said. → §UR13
- 📋 **UR14** (deps: UR21) **A cut that flashes white for one frame passes the build's verification** — The Shio promo flashed white at 0:40, the browser's blank page before chapter 2's console, and only the Alexandre watching caught it. → §UR14

## Done when — UR19

- **0.1.0 installs from PyPI and urdido build --help answers** In a fresh virtualenv,
  pip install urdido==0.1.0 succeeds and urdido build --help prints its usage, which
  needs the trusted publishers registered and the build command in the wheel.

## Non-goals
