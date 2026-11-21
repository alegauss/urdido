# urdido

urdido builds a narrated video from a declaration: the timeline, the cuts, the mix,
the cards, the captions and the export.

- [Build a first video](docs/quickstart.md), with nothing bought or recorded.
- [The declaration reference](docs/specs/declaration.md): every key a `video.toml` takes.
- [Source kinds](docs/sources.md), [what urdido checks](docs/checks.md) and
  [the extras and their tools](docs/extras.md).
- [The module reference](docs/video-maker.md), for working on urdido itself.

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

## From Python

The commands are also three calls, with the options by keyword:

```python
import urdido

problems = urdido.check("promo/video.toml")  # [] when the declaration passes
project = urdido.load("promo/video.toml", "en")  # .decl, .roots, .out, .load()
urdido.make("promo/video.toml", "en", plan=True, progress="off")  # 0 when it passed
```

`make` takes the options `urdido build` takes (`cut="chapter:2"`, `vertical`,
`revision`, ...) and refuses an unknown one by name. A refused build raises
`urdido.UrdidoError` (`Refused`, `DeclarationError`, `MissingTool`); the library never
exits.

## Develop

```
ruff check .
pytest
```

The plan lives in `docs/ROADMAP.md`, which [roadkeep](https://github.com/alegauss/roadkeep)
maintains.
