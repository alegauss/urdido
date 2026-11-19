---
name: urdido-friction
description: File a task in urdido's own roadmap (D:\Git\alegauss\urdido, roadkeep, prefix UR) the moment urdido - the video framework that was video-maker - causes friction or lacks something while making a video - a step done by hand (measuring a cut, copying a folder to keep a revision, timing a shot from word files, editing storyboard.json with a one-off script, typing docker setup), a value the declaration cannot express (a level, a placement, an anchor), a check that should have refused something the owner had to catch (a shot that contradicts its sentence, two labels that collide, a stale report), a silent failure, or a hard-coded text that turned false. Use while working on any video built by urdido (marketing's japode/*, shio/promo, turing/wordpress, ...), whenever you reach for a workaround outside urdido, whenever the owner reports a problem in a cut that a check could have caught, and before finishing any task. Trigger words: urdido, video-maker, videomaker build, video.toml, storyboard, fricção, friction, à mão, workaround.
---

# urdido friction becomes a UR task

The owner's standing rule (2026-11-13): **file the task without hesitating.** Every place
where a video needed work by hand, or a check missed what the owner later caught, is a
missing urdido feature. File it as a UR line **in the same session**. Don't ask first,
and don't wait until the end of the task.

polyweave and the products have their own friction skills: `polyweave-friction` (PW) for
capture, stock, sound and measurement operations, and `viglet-friction` for Turing and
Dumont. A gap in urdido itself (build, storyboard, mix, captions, highlights, cuts, the
docs it writes) is a UR line. When one problem has two owners, file both.

## When

- **At the start of the task:** read `urdido build --help` and the declaration before
  designing anything. A missing option is a signal.
- **Before the workaround:** file the line first, then write the workaround, and name the
  UR id beside it (a comment, the README, the commit body).
- **When the owner reports a problem in a cut:** fix the video, then ask "what check
  would have refused this?" and file that check.
- **Before committing:** scan the session for the signals below. Each one not yet filed
  gets filed now, and the commit body lists the UR ids.

## Signals

- You measured, copied, renamed or summed something about a cut by hand (ffprobe,
  loudnorm, hashes, shot counts, `-v3` copies).
- You edited `storyboard.json`, `highlights.json` or `video.toml` with a throwaway
  script, or a setting you needed did not exist in the declaration.
- You read `*.words.json` or `edit.json` to compute a time by hand.
- You ran setup by hand (docker, wp-cli, a shim) to give a scene a clean product instance.
- A text the framework writes became false for this video (a credit, a description line).
- The owner found something in a cut that `build` or `--plan` could have refused or
  shown: a shot unrelated to its sentence, readable third-party text or names, two labels
  at once, a person under someone else's name, a repeated clip, a level that distracts.
- A build ran on stale input, or failed without saying what to change.

## How to file

Run roadkeep from the project you are working in, pointed at urdido with `-C`. Your
project declares urdido under `[projects]` (marketing does), so the line arrives marked
`(from: <your project>)`: a report for urdido to re-analyse, not a design to build as is.
Never hand-edit urdido's `docs/` files: roadkeep owns them.

```
roadkeep -C D:\Git\alegauss\urdido block list
roadkeep -C D:\Git\alegauss\urdido delivered <block> --near "<symptom>" --open
roadkeep -C D:\Git\alegauss\urdido non-goal list
roadkeep -C D:\Git\alegauss\urdido budget --block <block> --symptom "..." --why "..."
roadkeep -C D:\Git\alegauss\urdido add --block <block> --symptom "..." --why "..." \
    --section "<title>" --section-body-file <absolute path to a scratchpad .md>
roadkeep -C D:\Git\alegauss\urdido lint
```

When a line in your own project waits on the one you filed, give it the dep:
`roadkeep amend <id> --add-dep "urdido: UR<n>"`.

- **Is it already there?** When an open line covers it, extend that line's section with
  `section amend` instead of filing a second one. Never file what a non-goal forbids.
- **The block:** a new feature of the framework goes to Block D; a defect in code
  still being extracted goes to Block B while that block is open.
- **symptom:** what does not work, as the person making a video meets it. Never the fix.
- **why:** one sentence on what it costs the video or the owner.
- **section** (at most 250 words, written to a scratchpad file first, passed by absolute
  path): the video and the command where it happened, what you did by hand and where that
  lives, what the owner saw, and what urdido should do instead.

## Committing

Before committing, run `git -C D:\Git\alegauss\urdido status --short`:

- If the tree holds **only** the docs roadkeep just wrote, commit there with
  `run-commit.cmd -m "docs(roadmap): file <what> (UR<n>)" -- docs`. No attribution
  trailer, and never push.
- If the tree carries anyone else's change, **do not commit**: leave the line written
  and say so in your report.

In the project you were working in, keep the workaround thin, name the UR id beside it,
and list each UR id you filed in your report, one line each.
