"""Publishing a video's words and pictures outside it, as its declaration says (VM15).

A video's `publish.json` names each target: where the narration's transcript goes (a TypeScript
module and a block between markers in a docs page, one entry per language) and where the
chapter stills go (for which story and language). A build writes into another repository only
where its declaration says so; nothing here names a product or a path.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from typing import Mapping, Sequence

_TAGS = re.compile(r"\[[^\]]*\]")
_SPACE = re.compile(r"\s+")


def resolved(path: str, roots: Mapping[str, str]) -> str:
    for name, root in roots.items():
        path = path.replace(f"<{name}>", root)
    return os.path.normpath(path)


def spoken(line: str) -> str:
    """A line as said: no voice directions, single spaces."""
    return _SPACE.sub(" ", _TAGS.sub("", line)).strip()


def transcript(script: Mapping, language: str) -> list[str]:
    """Every line of one language, in the order the video says them."""
    parts = [script["intro"]]
    for key in sorted(script["chapters"], key=int):
        parts += [script["chapters"][key]["card"], script["chapters"][key]["result"]]
    parts.append(script["outro"])
    return [said for said in (spoken((part or {}).get(language, "")) for part in parts) if said]


def _js_json(value) -> str:
    """JSON.stringify(value, null, 2): two-space indents, characters as they are."""
    return json.dumps(value, ensure_ascii=False, indent=2)


def transcript_outputs(declared: Mapping, script: Mapping, roots: Mapping[str, str]) -> list[tuple[str, str]]:
    """Each transcript target and the text it must hold."""
    languages: Sequence[Sequence[str]] = declared["languages"]
    by_language = {language: transcript(script, language) for language, _ in languages}
    outputs = []

    module = declared.get("module")
    if module:
        text = "\n".join([*module["header"], f"export const {module['const']}: Record<string, string[]> = "
                          f"{_js_json(by_language)};", ""])
        outputs.append((resolved(module["path"], roots), text))

    page = declared.get("page")
    if page:
        path = resolved(page["path"], roots)
        with open(path, encoding="utf-8", newline="") as f:
            current = f.read()
        start, end = current.find(page["find"]), current.find(page["end"])
        if start < 0 or end < start:
            raise ValueError(f"{path} has no transcript markers")
        lines = [page["start"]]
        for language, label in languages:
            lines += ["", "<details>", f"<summary>Transcript ({label})</summary>", ""]
            for paragraph in by_language[language]:
                lines += [paragraph, ""]
            lines.append("</details>")
        lines += ["", page["end"]]
        outputs.append((path, current[:start] + "\n".join(lines) + current[end + len(page["end"]):]))
    return outputs


def write_outputs(outputs: Sequence[tuple[str, str]], check: bool = False) -> list[str]:
    """Write what changed (line endings aside); with `check`, write nothing and name what is stale."""
    stale = []
    for path, content in outputs:
        try:
            with open(path, encoding="utf-8", newline="") as f:
                current = f.read()
        except FileNotFoundError:
            current = ""
        if current.replace("\r\n", "\n") == content.replace("\r\n", "\n"):
            continue
        stale.append(path)
        if not check:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(content)
    return stale


def publish_stills(declared: Mapping, stills: Sequence[str], story: str, language: str,
                   roots: Mapping[str, str]) -> list[str]:
    """Copy a build's chapter stills where its declaration says, when the build is the declared
    story and language; return what was written."""
    if not declared or declared.get("story") != story or declared.get("language") != language:
        return []
    written = []
    for n, still in enumerate(stills, 1):
        target = resolved(declared["to"].replace("{n}", str(n)), roots)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(still, target)
        written.append(target)
    return written
