# Build a first video

This walks through building `examples/first-video`: two lines of narration over
footage, with a title, a closing card and captions. Nothing is bought or recorded.
The media is generated with ffmpeg so you can see the whole build before you
write a video of your own.

## What you need

- Python 3.12 or newer.
- ffmpeg and ffprobe on your PATH.

## Install urdido

From a clone of the repository:

```
pip install -e .
```

## Make the example's media

urdido never stores media in git, so the example makes its own: a tone in place of
each narration take, and a test pattern in place of the footage.

```
python examples/first-video/make_media.py
```

This writes `narration/en/intro.mp3`, `narration/en/outro.mp3` and
`footage/src/pattern.mp4` inside `examples/first-video/`.

## Check the declaration

```
urdido check examples/first-video/video.toml
```

It prints `passes`. A misspelled key would be named here, with the nearest valid one.

## Build it

```
urdido build examples/first-video/video.toml --language en
```

The build writes into `examples/first-video/video/`:

- `first-video.en.mp4`, the video;
- `first-video.en.srt`, its captions;
- `first-video.en.qa.json`, what the final check measured.

## What the declaration says

`video.toml` names the video and its language, says it is an explainer (narration
over shots), and points at three files:

- `script.json`: each line of narration, by take (`intro`, chapters, `outro`);
- `shots.json`: what plays under each take, by source and start second;
- `narration/`: the takes, one folder per language.

To make it your own, change the lines in `script.json`, buy real takes with
`urdido prepare`, and put your footage under `footage/src/`. Every key a declaration
can hold is in [the declaration reference](specs/declaration.md); the other kinds of
video are in [the source kinds](sources.md), what urdido refuses and measures is in
[the checks](checks.md), and what each extra needs is in [the extras](extras.md).
