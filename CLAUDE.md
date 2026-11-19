# urdido

urdido builds a narrated video from a declaration (`video.toml`): the timeline, the cuts,
the mix, the cards, the captions and the export. It is being extracted from the
`video-maker/` folder of the Viglet marketing repository (`D:\Git\viglet\marketing`),
which is its first and, for now, only consumer. Block A of the roadmap is the package and
its tooling, Block B the extraction, Block C marketing's switch, Block D the features
that moved here from marketing.

## The roadmap

roadkeep owns `docs/ROADMAP.md`, `docs/CHANGELOG.md`, `docs/IMPROVEMENTS.md`,
`docs/STRATEGY.md` and `docs/DEFERRED.md` (prefix `UR`). Never read or edit them by hand:
`list`, `show`, `brief`/`claim`, `ship`, `add` and `lint` through the roadkeep MCP tools
or `python .claude/hooks/roadkeep-launch.py <verb>`. `roadkeep.toml` declares `marketing`
and `polyweave` as sibling projects, so a dep on their work is spelled
`marketing: VM28` or `polyweave: PW699` and resolves from their ledgers.

## The gates

```
pip install -e .[test]
ruff check .
ruff format --check .
python tools/gate.py
```

`tools/gate.py` runs pytest, keeps the log under `.urdido/gate/` and names every skipped
test with its reason. A test marked `full` encodes minutes of video and runs only where
`URDIDO_FULL=1`; CI runs those nightly. CI (`.github/workflows/gates.yml`) runs the same
gates on Ubuntu and Windows with Python 3.12 and 3.13.

## Commits

One finished task, one local commit, through `run-commit.cmd -m "<title>" -- <paths>`:
a conventional-commits title in ASCII ending with the task id, the code and the governed
docs roadkeep wrote in the same commit, only this task's paths staged, no attribution
trailer, never pushed. A release is `python tools/release.py patch|minor|major`, which
the owner runs: it pushes a tag that `publish.yml` takes to PyPI.

## The rules the code keeps

- **Nothing on screen is staged.** A scene is the product working on a clean instance,
  and an agent appears through its real session's record, replayed, never a hand-written
  terminal.
- **A product's brand, words and URLs live in the declaration, never in a module.** A
  text the framework writes (a credit, a chapter title, a description line) comes from
  the declaration or a per-language default, so a second product or language changes no
  code.
- **Media is never versioned.** Footage, takes and renders stay out of git; scripts,
  declarations, `.prov.json` and ledgers are versioned.
- **An optional dependency refuses by name.** Code that needs an extra calls
  `urdido.extras.require`, which names the `pip install urdido[<extra>]` that fixes it.
  DaVinci Resolve and Docker are programs: find the binary and refuse by name.

## Friction from consumers

A project that drives urdido files what got in its way here, through the
`urdido-friction` skill (`skills/urdido-friction/SKILL.md`, installed in
`~/.claude/skills/`). A line filed that way carries `(from: <project>)`. polyweave gaps go
to polyweave through `polyweave-friction`.
