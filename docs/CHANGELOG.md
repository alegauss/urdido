# Shipped Ledger

## Block A — Package foundation (urdido installable from PyPI)

- ✅ **UR16** **There is no urdido package to install: no pyproject, source tree, console script or version** — urdido installs with pip install -e .[test], answers urdido --version, and refuses a missing extra (cards, narration, polyweave) by naming its pip install (design recorded in `README.md`).
- ✅ **UR17** **A dep on another project's task is free text, so a marketing or polyweave ship never resolves here** — urdido and marketing declare each other and polyweave as siblings, so deps resolves UR1-UR3's waits on PW697-PW699 and VM28 from those ledgers (design recorded in `roadkeep.toml`).
- ✅ **UR18** **Nothing checks a push: no CI runs ruff and pytest on Linux and Windows** — gates.yml runs ruff and tools/gate.py on Ubuntu and Windows with Python 3.12 and 3.13, naming each skip, though no push has run it yet (design recorded in `.github/workflows/gates.yml`).
- ✅ **UR19 (release tooling)** **A version cannot reach PyPI except by a hand-run upload with a token** — publish.yml takes a v* tag through build, twine check, a tag-versus-package check and a wheel install to TestPyPI, PyPI and a GitHub release, and tools/release.py tags it.
- ✅ **UR20 (CLAUDE.md and friction skill)** **An agent working in this repo or driving urdido has no CLAUDE.md, skill or friction path** — CLAUDE.md gives the gates, commits and code rules, and the urdido-friction skill, installed globally, files from a consumer through roadkeep -C with (from:).

## Block B — The engine extracted (videomaker without marketing)

- ✅ **UR21** **urdido holds none of the videomaker code, and marketing's history of each module would be lost by a copy** — video-maker's 75 commits merged into src/urdido, tests and js under the urdido name; the suite passes here and skips by name without marketing (design recorded in `tests/marketing.py`).

## Block C — Adoption in marketing (video-maker replaced by urdido)

## Block D — Inherited from video-maker (marketing Block B)

- ✅ **UR6** **A stock clip already rejected for contradicting the narration can come back into a cut without any check refusing it** — Storyboard media can carry rejected with a reason, whole or by range, and preflight and build refuse any beat that meets it (design recorded in `docs/video-maker.md`).
- ✅ **UR7** **A narration take with the wrong accent cannot be bought again unless its text changes** — urdido prepare --retake buys an unchanged take again, keeps the old one and records the reason, voice and model in retakes.json (design recorded in `docs/video-maker.md`).
- ✅ **UR1** **Titles and thumbnails go out unchecked, so the Scion thumbnail repeats its title and the feed cuts the title** — urdido thumbnail checks the declared title and thumbnail as a pair, refusing a long, vague or shouting title or a repeating thumbnail, as with Scion (design recorded in `docs/video-maker.md`).
