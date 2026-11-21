# urdido

urdido builds a narrated video from a declaration: the timeline, the cuts, the mix,
the cards, the captions and the export. It is being extracted from the `video-maker`
folder of the Viglet marketing repository; until that lands, the package holds only
its command line and its packaging.

## Install

```
pip install -e .[test]
urdido --version
```

Python 3.12 or newer. The base install needs only `opentimelineio`. Heavier parts are
extras, and code that needs a missing one stops with the `pip install` that fixes it:

| Extra       | Brings                 | For                          |
| ----------- | ---------------------- | ---------------------------- |
| `cards`     | playwright, fonttools  | title cards and thumbnails   |
| `narration` | requests               | buying narration takes       |
| `polyweave` | polyweave-gamekit      | the polyweave operations     |
| `shorts`    | pillow                 | `urdido shorts` backgrounds  |
| `test`      | pytest, pillow, ruff   | the suite and the lint       |

DaVinci Resolve and Docker are programs rather than Python packages, so the commands
that use them look for the program and stop by name when it is missing.

## Develop

```
ruff check .
pytest
```

The plan lives in `docs/ROADMAP.md`, which [roadkeep](https://github.com/alegauss/roadkeep)
maintains.
