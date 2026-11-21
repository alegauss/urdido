"""A video's declaration, loaded once: its roots, its paths and its folders (UR33).

`Project` is what every pipeline reads before it builds anything: the `video.toml`
checked against its schema, the roots its `<name>` paths start at, the output and work
folders (inside an immutable revision when one is asked for), and the side files it
names, each loaded once and pinned by its hash so a declaration edited mid-build is
refused. `urdido.build.Build` runs the pipelines on top of it; UR5's variant overlay
resolves its paths here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from urdido.errors import DeclarationError
from urdido.sources import RecordingRefused

TAB, NEWLINE = chr(9), chr(10)

#: The environment variables that filled a root before `[roots]` (UR22), kept for one
#: release.
LEGACY_ROOTS = {
    "video": "STORY_VIDEO_DIR",
    "recordings": "STORY_RECORDINGS",
    "plugin": "TURING_WORDPRESS",
    "shio": "SHIO_REPO",
}


def roots_of(here: Path, decl: Mapping, env: Mapping[str, str] | None = None) -> dict:
    """The roots a declaration's `<name>` paths start at, all declared or inside its
    folder.

    `[roots]` names each one, as a path relative to the declaration or as `$VAR` /
    `${VAR}`; `[output] folder` is `<video>`. An undeclared legacy root is still read
    from its old environment variable, with a notice; an undeclared one with no variable
    does not exist."""
    env = os.environ if env is None else env
    output = decl.get("output") or {}
    roots = {
        "root": str(here),
        "video": str((here / output.get("folder", "video")).resolve()),
        "recordings": str(here / "recordings"),
    }
    declared = dict(decl.get("roots") or {})
    for name, value in declared.items():
        if name in ("root", "video") or not isinstance(value, str) or not value:
            raise DeclarationError(
                f"urdido build: [roots] {name} must be a path, and "
                "root and video are not declared there"
            )
        if value.startswith("$"):
            variable = value.strip("${}")
            if not env.get(variable):
                raise DeclarationError(
                    f"urdido build: [roots] {name} reads ${variable}, which is not set"
                )
            value = env[variable]
        roots[name] = str((here / value).resolve())
    for name, variable in LEGACY_ROOTS.items():
        if (
            name in declared
            or (name == "video" and "folder" in output)
            or not env.get(variable)
        ):
            continue
        roots[name] = str(Path(env[variable]).resolve())
        print(
            f"urdido build: {variable} is deprecated; declare [roots] {name}"
            + (" or [output] folder" if name == "video" else ""),
            file=sys.stderr,
        )
    return roots


#: What a base folder holds that a variant's view leaves out (UR5).
NOT_SHARED = {".git", ".urdido", "node_modules", "__pycache__", "video.toml"}


def merged(base, over):
    """`over` laid on `base`: tables merge key by key, anything else is replaced."""
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for key, value in over.items():
            out[key] = merged(base[key], value) if key in base else value
        return out
    return over


def link(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError as failed:
        raise DeclarationError(
            f"urdido build: cannot link {source} into the variant's view ({failed}); a "
            "variant shares its base's files without copying them, so both folders "
            "must "
            "be on one disk"
        ) from None


def overlay(base: Path, variant: Path, view: Path, skip: set[str]) -> int:
    """`view` as `base` with `variant` laid over it, by hard link (UR5).

    No byte is copied: each base file is linked in, then each variant file replaces
    it, and a JSON file both hold is written as the variant's merged over the base's
    (so a variant storyboard can carry only the scene lists it changes). The view is
    made again on every build, so a fix in the base reaches the variant. Returns how
    many files were linked."""
    import shutil

    if view.exists():
        shutil.rmtree(view)
    count = 0
    for folder in (base, variant):
        for file in sorted(folder.rglob("*")):
            relative = file.relative_to(folder)
            if not file.is_file() or relative.parts[0] in skip or view in file.parents:
                continue
            target = view / relative
            if folder == variant and target.exists():
                target_text = (
                    target.read_text("utf-8-sig") if file.suffix == ".json" else ""
                )
                target.unlink()
                if file.suffix == ".json":
                    joined = merged(
                        json.loads(target_text), json.loads(file.read_text("utf-8-sig"))
                    )
                    target.write_text(
                        json.dumps(joined, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    continue
            link(file, target)
            count += 1
    return count


class Project:
    """A declaration loaded for one language, with its roots and folders.

    A declaration with `[video] base = "../published"` is a variant (UR5): its tables
    are laid over the base's, it resolves every relative path through a view of the
    base folder with its own files laid over (`overlay`), its declared roots join the
    base's (each resolved from the folder that declared it), and it builds into its own
    output folder."""

    def __init__(self, toml: Path, args: argparse.Namespace):
        from urdido.declaration import check as check_declaration

        self.here = toml.parent.resolve()
        self.variant = None
        raw = toml.read_bytes()
        self.decl = tomllib.loads(raw.decode("utf-8-sig"))
        self.input_hashes = {toml.resolve(): hashlib.sha256(raw).hexdigest()}
        own = self.decl
        base_decl, base_folder = self._base(own)
        if base_decl is not None:
            tables = {k: v for k, v in own.items() if k not in ("output", "roots")}
            self.decl = merged(base_decl, tables)
            self.decl["video"].pop("base", None)
            self.decl["output"] = own.get("output") or {}
            self.decl["roots"] = {
                **(base_decl.get("roots") or {}),
                **(own.get("roots") or {}),
            }
        problems = check_declaration(self.decl, str(toml))
        if problems:
            raise DeclarationError(
                "urdido build: the declaration is refused:\n" + "\n".join(problems)
            )
        self.args = args
        if base_decl is None:
            self.roots = roots_of(self.here, self.decl)
        else:
            base_roots = roots_of(base_folder, base_decl)
            mine = roots_of(
                self.here,
                {"roots": own.get("roots") or {}, "output": own.get("output") or {}},
            )
            self.roots = {**base_roots, **mine}
            view = Path(mine["video"]) / "base-view"
            overlay(
                base_folder,
                self.here,
                view,
                NOT_SHARED | {Path(base_roots["video"]).name, Path(mine["video"]).name},
            )
            self.variant, self.here = self.here, view
            self.roots.update(root=str(view), recordings=str(view / "recordings"))
        self.out = Path(self.roots["video"])

        self.language = args.language
        video = self.decl["video"]
        self.name = video["name"]
        if self.language not in video["languages"]:
            spoken = ", ".join(video["languages"])
            raise DeclarationError(
                f"urdido build: {self.name} speaks {spoken}, not {self.language}"
            )
        self.revision = None
        self.checked: list[str] = []
        revision = getattr(args, "revision", None) or video.get("revision")
        drafting = getattr(args, "plan", False) or getattr(args, "cards", False)
        if revision and not drafting:
            from urdido.revisions import Revision

            cut = args.cut + ("-vertical" if args.vertical else "")
            if getattr(args, "preview", None):
                asked = [
                    args.preview,
                    args.context_before,
                    args.context_after,
                    args.preview_occurrence,
                ]
                digest = hashlib.sha256(json.dumps(asked).encode()).hexdigest()[:12]
                cut = "preview-" + digest
            self.revision = Revision(self.out, self.name, self.language, cut, revision)
            self.out = self.revision.folder
        from urdido.declaration import check_side_files

        inside = check_side_files(self.decl, self.path)
        if inside:
            raise DeclarationError(
                "urdido build: a side file is refused:\n" + "\n".join(inside)
            )
        self.parts = self.out / (self.decl.get("output") or {}).get("parts", "parts")
        self.parts.mkdir(parents=True, exist_ok=True)

    def _base(self, own: dict):
        """The base declaration and its folder for a variant, else (None, None)."""
        declared = (own.get("video") or {}).get("base")
        if not declared:
            return None, None
        base_toml = (self.here / declared).resolve()
        if base_toml.is_dir():
            base_toml = base_toml / "video.toml"
        if not base_toml.is_file():
            raise DeclarationError(
                f"urdido build: [video] base names {declared}, "
                "where there is no video.toml"
            )
        base_raw = base_toml.read_bytes()
        base_decl = tomllib.loads(base_raw.decode("utf-8-sig"))
        if (base_decl.get("video") or {}).get("base"):
            raise DeclarationError("urdido build: a base cannot itself be a variant")
        self.input_hashes[base_toml] = hashlib.sha256(base_raw).hexdigest()
        return base_decl, base_toml.parent

    # -- paths -------------------------------------------------------------------------

    def path(self, declared: str) -> str:
        """A declared path, from its root or the declaration's folder."""
        for name, root in self.roots.items():
            if declared.startswith(f"<{name}>"):
                return os.path.normpath(declared.replace(f"<{name}>", root))
        if declared.startswith("<") and ">" in declared:
            name = declared[1 : declared.index(">")]
            raise DeclarationError(
                f"urdido build: {declared} starts at <{name}>, "
                "which the declaration does not declare; add it "
                "under [roots]"
            )
        return os.path.normpath(str(self.here / declared))

    def portable(self, text: str) -> str:
        """Paths named by the folder they are under, as story-video.mjs's plan writes
        them."""
        folders = sorted(
            ((root, f"<{k}>") for k, root in self.roots.items()),
            key=lambda p: -len(p[0]),
        )
        for folder, name in folders:
            text = text.replace(folder, name).replace(folder.replace("\\", "/"), name)
        return text.replace("\\", "/")

    def _portable_all(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.portable(value)
        if isinstance(value, dict):
            return {k: self._portable_all(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._portable_all(v) for v in value]
        return value

    def write_plan(self, name: str, data: Mapping) -> Path:
        from urdido.timeline import _rounded

        file = self.parts / f"{name}.{self.language}.plan.json"
        rounded = _rounded(self._portable_all(dict(data)))
        text = json.dumps(rounded, ensure_ascii=False, indent=TAB) + NEWLINE
        file.write_text(text, encoding="utf-8", newline="")
        return file

    # -- side files --------------------------------------------------------------------

    def load(self, declared: str):
        """A side file the declaration names, pinned by its hash for the build."""
        file = Path(self.path(declared)).resolve()
        raw = file.read_bytes()
        if not file.is_relative_to(self.parts):
            sha = hashlib.sha256(raw).hexdigest()
            if file in self.input_hashes and self.input_hashes[file] != sha:
                raise RecordingRefused(f"declaration changed during build: {file}")
            self.input_hashes[file] = sha
        return json.loads(raw.decode("utf-8-sig"))

    def write_inputs(self) -> Path:
        """Every declaration file the build read, with its hash, checked unchanged."""
        for file, sha in self.input_hashes.items():
            if hashlib.sha256(file.read_bytes()).hexdigest() != sha:
                raise RecordingRefused(f"declaration changed during build: {file}")
        manifest = self.parts / f"{self.name}.{self.language}.inputs.json"
        rows = [
            {"file": str(file), "sha256": sha}
            for file, sha in self.input_hashes.items()
        ]
        manifest.write_text(
            json.dumps({"declarations": rows}, indent=2) + "\n", encoding="utf-8"
        )
        for file, sha in self.input_hashes.items():
            print(f"input sha256 {sha} {file}")
        return manifest

    def frame(self):
        """The declared `[video] frame = [width, height]`, 1920x1080 unless said."""
        from urdido.cards import html

        size = (self.decl.get("video") or {}).get("frame", [1920, 1080])
        if not (
            isinstance(size, list)
            and len(size) == 2
            and all(isinstance(v, int) and v >= 16 and v % 2 == 0 for v in size)
        ):
            raise DeclarationError(
                "urdido build: [video] frame must be [width, height] "
                f"in even pixels, got {size!r}"
            )
        return html.Frame(*size)
