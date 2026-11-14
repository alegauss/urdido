"""VM40: immutable build packages and an atomic current-package pointer."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from uuid import uuid4


class Revision:
    def __init__(self, root: Path, name: str, language: str, cut: str, revision: str):
        cut = cut.replace(":", "-")
        for value in (name, language, cut, revision):
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value):
                raise ValueError(f"invalid revision package component: {value!r}")
        self.root = root
        self.key = f"{name}.{language}.{cut}"
        self.revision = revision
        self.folder = root / "revisions" / self.key / revision
        # An exclusive directory reservation also refuses retries over a failed cut.
        self.folder.mkdir(parents=True, exist_ok=False)
        (self.folder / "INCOMPLETE").write_text("Build has not completed.\n", encoding="utf-8")

    def complete(self, checked: list[str]) -> Path:
        if not checked:
            raise RuntimeError("revision has no measured video outputs")
        files = []
        for file in checked:
            video = Path(file)
            video.relative_to(self.folder)
            for required in (video, video.with_suffix(".qa.json"), video.with_suffix(".first.png")):
                if not required.is_file():
                    raise RuntimeError(f"revision package missing {required}")
            files.append(video.relative_to(self.root).as_posix())
        data = {"revision": self.revision, "videos": files,
                "folder": self.folder.relative_to(self.root).as_posix(),
                "review": (self.folder / "index.md").relative_to(self.root).as_posix()}
        rows = ["| Video | Subtitles | QA | First frame |", "|---|---|---|---|"]
        for file in checked:
            video = Path(file)
            captions = [f"[{p.suffix[1:]}]({p.name})" for suffix in (".srt", ".vtt")
                        if (p := video.with_suffix(suffix)).is_file()]
            rows.append(f"| [{video.name}]({video.name}) | {' '.join(captions)} | "
                        f"[QA]({video.with_suffix('.qa.json').name}) | "
                        f"[Frame]({video.with_suffix('.first.png').name}) |")
        descriptions = sorted(self.folder.glob("*.description.txt"))
        rows += ["", *[f"[Description and credits]({p.name})" for p in descriptions]]
        (self.folder / "index.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        (self.folder / "package.json").write_text(text, encoding="utf-8")
        (self.folder / "INCOMPLETE").unlink()
        pointer = self.root / f"{self.key}.current.json"
        temporary = pointer.with_name(f".{pointer.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_text(text, encoding="utf-8")
            os.replace(temporary, pointer)
        finally:
            temporary.unlink(missing_ok=True)
        return pointer
