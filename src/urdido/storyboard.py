"""VM46: optimistic, atomic storyboard edits addressed by persistent beat IDs."""
from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import os
import re
import tempfile
import uuid
from pathlib import Path


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def indexed(document: dict) -> dict[str, tuple[str, dict]]:
    found = {}
    for take, beats in document["scenes"].items():
        if not isinstance(beats, list) or not beats:
            raise ValueError(f"{take}: a scene needs beats")
        for beat in beats:
            key = beat.get("id")
            if key is not None:
                if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", key) or key in found:
                    raise ValueError(f"invalid or duplicate beat id: {key!r}")
                found[key] = (take, beat)
    return found


def changes(document: dict, operations: list[dict], seed: str) -> dict:
    result = copy.deepcopy(document)
    for number, op in enumerate(operations):
        ids = indexed(result)
        kind = op["op"]
        if kind == "assign-ids":
            for take, beats in result["scenes"].items():
                for i, beat in enumerate(beats):
                    beat.setdefault("id", "b_" + uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:{take}:{i}").hex[:16])
        elif kind == "credits":
            if not isinstance(op["value"], str):
                raise ValueError("credits must be text")
            result["credits"] = op["value"]
        elif kind == "media":
            result.setdefault("media", {}).setdefault(op["key"], {}).update(op["values"])
        elif kind == "insert":
            take = op["take"]
            beats = result["scenes"][take]
            after = op.get("after")
            at = insertion_index(beats, after)
            beat = copy.deepcopy(op["value"])
            beat.setdefault("id", "b_" + uuid.uuid5(uuid.NAMESPACE_URL, f"{seed}:insert:{number}").hex[:16])
            beats.insert(at, beat)
        elif kind in {"set", "remove", "move"}:
            if op["beat"] not in ids:
                raise ValueError(f"unknown beat id {op['beat']!r}; assign IDs before editing legacy beats")
            take, beat = ids[op["beat"]]
            if kind == "set":
                if "id" in op["values"]:
                    raise ValueError("a beat's stable id cannot be changed")
                beat.update(op["values"])
            else:
                result["scenes"][take].remove(beat)
                if kind == "move":
                    target = result["scenes"][op["take"]]
                    after = op.get("after")
                    at = insertion_index(target, after)
                    target.insert(at, beat)
        else:
            raise ValueError(f"unknown storyboard operation {kind!r}")
    indexed(result)
    return result


def insertion_index(beats: list[dict], after: str | None) -> int:
    if after is None:
        return 0
    for i, beat in enumerate(beats):
        if beat.get("id") == after:
            return i + 1
    raise ValueError(f"insertion anchor {after!r} is not in the destination take")


def edit(file: Path, expected: str, operations: list[dict], *, dry_run: bool = False) -> dict:
    file = file.resolve()
    raw = file.read_bytes()
    if digest(raw) != expected:
        raise ValueError("stale storyboard: expected SHA-256 does not match; inspect the current file")
    text = raw.decode("utf-8-sig")
    before = json.loads(text)
    after = changes(before, operations, expected)
    indent = re.search(r"\n([ \t]+)\S", text)
    spacing = indent.group(1) if indent else "  "
    newline = "\r\n" if b"\r\n" in raw else "\n"
    rendered = json.dumps(after, ensure_ascii=False, indent=spacing)
    rendered = rendered.replace("\n", newline) + (newline if text.endswith("\n") else "")
    output = (b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + rendered.encode("utf-8")
    if before == after:
        output = raw
    diff = "".join(difflib.unified_diff(text.replace("\r\n", "\n").splitlines(keepends=True),
                                        output.decode("utf-8-sig").replace("\r\n", "\n").splitlines(keepends=True),
                                        fromfile=str(file), tofile=str(file)))
    result = {"before": expected, "after": digest(output), "changed": output != raw, "diff": diff}
    if dry_run or output == raw:
        return result
    lock = file.with_name(file.name + ".edit.lock")
    pending = None
    handle = lock.open("x", encoding="utf-8")
    try:
        if digest(file.read_bytes()) != expected:
            raise ValueError("storyboard changed while preparing edit")
        with tempfile.NamedTemporaryFile(dir=file.parent, prefix=".storyboard-", delete=False) as temp:
            pending = Path(temp.name)
            temp.write(output)
            temp.flush()
            os.fsync(temp.fileno())
        if digest(file.read_bytes()) != expected:
            raise ValueError("storyboard changed before atomic write")
        os.replace(pending, file)
    finally:
        if pending:
            pending.unlink(missing_ok=True)
        handle.close()
        lock.unlink()
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="urdido storyboard", description=__doc__)
    parser.add_argument("action", choices=["inspect", "assign-ids", "edit"])
    parser.add_argument("file", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--operations", type=Path, help="JSON array of edits")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "inspect":
        raw = args.file.read_bytes()
        document = json.loads(raw.decode("utf-8-sig"))
        print(json.dumps({"sha256": digest(raw), "beats": [
            {"take": take, "id": beat.get("id"), "title": beat.get("title")}
            for take, beats in document["scenes"].items() for beat in beats]}, ensure_ascii=False, indent=2))
        return 0
    if not args.expected_sha256:
        parser.error("writes and dry runs require --expected-sha256")
    if args.action == "edit" and not args.operations:
        parser.error("edit requires --operations")
    operations = [{"op": "assign-ids"}] if args.action == "assign-ids" else json.loads(args.operations.read_text(encoding="utf-8-sig"))
    result = edit(args.file, args.expected_sha256, operations, dry_run=args.dry_run)
    print(result["diff"], end="")
    print(json.dumps({k: v for k, v in result.items() if k != "diff"}))
    return 0
