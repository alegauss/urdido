---
name: urdido
description: Declare and build a narrated video with urdido - write its video.toml, pick a source kind (explainer, scenes, illustrated, chaptered), check the declaration, buy and hear back the takes, build, read what the checks refused, cut Shorts, draw the thumbnail and record scenes. Use whenever a task creates, edits or builds a video with urdido (marketing's japode/*, shio/promo, turing/wordpress, or a new one), or when a build, check or take is refused and you need to know what fixes it. Trigger words: urdido, video.toml, urdido build, urdido check, urdido prepare, urdido shorts, urdido thumbnail, urdido record, storyboard, shots.json, narration takes.
---

# Declaring and building a video with urdido

A video is one `video.toml` and the side files it names. urdido reads it, refuses what
it can catch before spending time or money, builds, and measures the result. The
manual is in the urdido repository (`D:\Git\alegauss\urdido\docs`): start with
`quickstart.md`, keep `specs/declaration.md` open for every key, `sources.md` for the
kinds of video and `checks.md` for what refuses.

## The order of work

1. **Check the declaration first.** `urdido check video.toml` refuses an unknown key
   with the nearest valid name. Fix the key; never work around a refusal.
2. **Buy the takes, then hear them.** `urdido prepare video.toml --language <l>` plans
   the narration (nothing is paid without `--authorize-take` and `--execute`). The
   opening gate refuses a preamble or a first proof later than 20 s before anything is
   bought. After purchase, a word the `pronounce` map names that the take did not say
   refuses it: re-buy with `--retake <take> --retake-reason "<what was wrong>"`.
3. **Plan before you render.** `urdido build video.toml --language <l> --plan` stops
   at the timeline; read the plan (`<name>.<l>.plan.json`) before a long encode.
4. **Build.** `urdido build video.toml --language <l>`. The final verification measures
   loudness, true peak and flashes on the finished file; a refusal names the second and
   the clip.
5. **Publish.** `urdido thumbnail video.toml --language <l> --check` checks the title
   and thumbnail as a pair; `urdido shorts video.toml --language <l>` cuts the Shorts.

## Choosing the source kind

- Narration over Creative Commons footage, with callouts: `explainer`.
- A product filmed scene by scene (`urdido record` runs the declared steps): `scenes`.
- Editorial cards and declared media per beat: `illustrated`.
- One recording cut into chapters: `chaptered`.
- A second opening of a published video: keep the kind and add `[video] base =
  "../published"`; the variant carries only what changes.

## Rules urdido keeps, and you keep with it

- Nothing on screen is staged: a scene is the product working, an agent appears through
  its real session's record.
- A product's brand, words and URLs live in the declaration, never in urdido's code.
- Media is never versioned; scripts, declarations, `.prov.json` and ledgers are.
- A path starts at the declaration's folder or a root it declares under `[roots]`.

## When urdido gets in the way

Anything done by hand, a value the declaration cannot express, or a check that missed
what the owner caught is a missing urdido feature: file it through the
`urdido-friction` skill, in the same session, before writing the workaround.
