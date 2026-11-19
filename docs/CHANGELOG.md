# Shipped Ledger

## Block A — Package foundation (urdido installable from PyPI)

- ✅ **UR16** **There is no urdido package to install: no pyproject, source tree, console script or version** — urdido installs with pip install -e .[test], answers urdido --version, and refuses a missing extra (cards, narration, polyweave) by naming its pip install (design recorded in `README.md`).
- ✅ **UR17** **A dep on another project's task is free text, so a marketing or polyweave ship never resolves here** — urdido and marketing declare each other and polyweave as siblings, so deps resolves UR1-UR3's waits on PW697-PW699 and VM28 from those ledgers (design recorded in `roadkeep.toml`).
- ✅ **UR18** **Nothing checks a push: no CI runs ruff and pytest on Linux and Windows** — gates.yml runs ruff and tools/gate.py on Ubuntu and Windows with Python 3.12 and 3.13, naming each skip, though no push has run it yet (design recorded in `.github/workflows/gates.yml`).

## Block B — The engine extracted (videomaker without marketing)

## Block C — Adoption in marketing (video-maker replaced by urdido)

## Block D — Inherited from video-maker (marketing Block B)

