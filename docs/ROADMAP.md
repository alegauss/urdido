# Roadmap (active backlog)

## Block A — Package foundation (urdido installable from PyPI)

## Block B — The engine extracted (videomaker without marketing)

## Block C — Adoption in marketing (video-maker replaced by urdido)

## Block D — Inherited from video-maker (marketing Block B)

- 📋 **UR1** (deps: polyweave PW699) **Titles and thumbnails go out unchecked, so the Scion thumbnail repeats its title and the feed cuts the title** — A thumbnail should add what the title leaves out, and a title keeps its point inside 40 to 60 characters or the feed cuts it. → §UR1
- 📋 **UR2** (deps: polyweave PW697, polyweave PW698) **Each video cuts its Shorts with its own copied script, and the Shorts rules live only in japode/scion** — Shorts are how a new channel gets found, and the loop, pacing, safe-area and loudness rules learned on 2026-11-12 must hold for every video. → §UR2
- 📋 **UR3** (deps: marketing VM28) **Published videos have no end screen or cards pointing to the next video on the subject** — A viewer who finishes the Docker video is not offered the Scion one, and the end screen should point at the continuation, not the newest upload. → §UR3
- 📋 **UR4** (deps: UR2) **The Japode explainer videos are built by scripts copied into each video, outside video-maker** — video-maker only knows the recorded product demo, so the first video of another kind went around it, and its two copies already differ. → §UR4
- 📋 **UR5** (deps: —) **A second cut of a video, to test a new opening, means copying the whole video folder and its declaration** — Retention tests need several openings of the same episode, and each copy duplicates 722 MB and drifts from the published cut on every later fix. → §UR5
- 📋 **UR6** (deps: —) **A stock clip already rejected for contradicting the narration can come back into a cut without any check refusing it** — The review that removed it is lost on the next edit, and the owner has to catch the same bad shot again. → §UR6
- 📋 **UR7** (deps: —) **A narration take with the wrong accent cannot be bought again unless its text changes** — eleven_v3 sometimes drifts into European Portuguese, and the only way to re-roll the take is to rewrite a line that was already right. → §UR7
- 📋 **UR8** (deps: —) **A thumbnail picture can be any file in the folder, unchecked against the video's media or its licence** — The thumbnail is the promise the video must keep, and a logo or photo fetched by hand reaches it with no provenance check. → §UR8
- 📋 **UR9** (deps: —) **A video made of filmed scenes gets no YouTube description or chapter times from its build** — The Viglet Shio promo's chapter times were read by hand from its captions, and every new cut moves them. → §UR9
- 📋 **UR10** (deps: —) **A scene video is recorded by running its README's commands in order by hand, and a failed step does not stop the next** — The Viglet Shio promo's agent session ran on an instance whose Marketplace scene had failed, and the order lives only in prose. → §UR10
- 📋 **UR11** (deps: —) **An agent's recorded session is not checked against what the narration says it shows** — The Shio promo's sessions were read by hand three times for a skill, one verify and an error the lines claim, and two lacked them. → §UR11
- 📋 **UR12** (deps: —) **A scene video has no review sheet: frames to look at are pulled one by one with ffmpeg** — Checking the Shio promo's mark, cards, search and terminal took about ten hand-made ffmpeg grabs; illustrated videos get a sheet. → §UR12
- 📋 **UR13** (deps: —) **A bought take is never heard back, so a word the voice says wrong is caught only by the owner watching** — The Alexandre heard "Ía" for IA in the Shio promo; after the pronounce fix nothing could confirm "iá" was what the voice said. → §UR13
- 📋 **UR14** (deps: —) **A cut that flashes white for one frame passes the build's verification** — The Shio promo flashed white at 0:40, the browser's blank page before chapter 2's console, and only the Alexandre watching caught it. → §UR14

## Non-goals
