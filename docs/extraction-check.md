# The extraction check

Each video marketing published was rebuilt with urdido and compared with video-maker, the
copy it was extracted from, before video-maker's folder could go. This is the record of
that comparison (2026-11-23, Windows, the media and takes on the owner's machine).

## How it was compared

- **Plans**: every declared video was planned by both (`--plan`, into scratch folders) and
  every file each wrote was compared byte for byte: the timeline, captions, credits, claims
  and description.
- **Full builds**: each video was built in full by both on the same inputs and its outputs
  compared: captions exactly, and the QA sidecar (`*.qa.json`) value by value.
- **The WordPress demo** has its own golden check in marketing
  (`turing/wordpress/test/golden/run.mjs`), which rebuilds its five variants from frozen
  fixture recordings with urdido.

## Results

| Video | Plan | Captions | Duration, loudness, streams |
|---|---|---|---|
| japode/primeiro-bug | same, 25 files | same | same |
| japode/wordpress | same, 96 files | same | same |
| japode/wordpress2 | same, 94 files | same | same |
| shio/promo, long cut | same | same | same |
| shio/promo, Shorts c1, c2, c3 | same | same | same |
| turing/wordpress, five variants (golden check) | same | same | same |

## Differences, each explained

- **The encoded bytes** (`sha256`, `bytes`, the first frame's hash, the bit rate within
  0.03%) differ between any two builds, video-maker against itself included: rebuilt
  today, video-maker does not reproduce its own last build's bytes either. Duration,
  loudness and streams are equal.
- **`as_of`** in the claims and credits files is the build's date.
- **The cache sidecar** (`*.mp4.cache.json`) has urdido's own format.
- **`flashes`** in the QA sidecar is the flash report urdido adds; video-maker had none.
- **`texts`** in the QA sidecar lists the files it checked by path, so the paths differ
  while their hashes are equal.

## Not rebuilt yet

The Viglet Turing Search for WordPress demo's own recordings (the story and the developer
walkthrough, in both languages) are older than the story spec they were recorded from, so
both tools refuse to build them until they are recorded again on the demo stack
(`npm run e2e:story:record`, `npm run e2e:developer:record`). Its build logic is covered
by the golden check above.
