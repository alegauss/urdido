"""VM55: verified, independently resumable production stages (HTML gap: PW700).

A stage's key survives a move (UR32): every input is named by where it sits, under a
declared root (`<root>/narration/en/intro.mp3`) or inside the urdido package
(`urdido:cache.py`), and hashed by content; a path inside the stage's settings is
rewritten the same way. So a build cached in one checkout hits from another of the same
version, and an upgrade misses only where the code a stage runs changed, the modules
being inputs like any other. A stamp written before this (no `format`) cannot be verified:
it rebuilds, and the report counts it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

CURRENT = ContextVar("build_cache", default=None)
FORMAT = 2
PACKAGE = Path(__file__).resolve().parent


class Session:
    def __init__(self, report: Path, roots: dict[str, str] | None = None):
        self.report = report
        self.hashes = {}
        self.lock = threading.RLock()
        self.events = []
        self.tools = {}
        # Longest first, so <video> (inside <root>) names its own files.
        self.roots = sorted(
            ((name, Path(path).resolve()) for name, path in (roots or {}).items()),
            key=lambda row: -len(str(row[1])),
        )

    def label(self, file) -> str:
        """Where a file sits, independent of the checkout: a root's or the package's."""
        path = Path(file).resolve()
        if path.is_relative_to(PACKAGE):
            return "urdido:" + path.relative_to(PACKAGE).as_posix()
        for name, root in self.roots:
            if path.is_relative_to(root):
                return f"<{name}>/" + path.relative_to(root).as_posix()
        return path.as_posix()

    def portable(self, value):
        """`value` with every path under a root or the package written by its label."""
        if isinstance(value, str):
            for folder, name in [
                (PACKAGE, "urdido:"),
                *((root, f"<{n}>") for n, root in self.roots),
            ]:
                for spelling in {str(folder), folder.as_posix()}:
                    value = value.replace(spelling, name)
            return value
        if isinstance(value, dict):
            return {key: self.portable(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.portable(item) for item in value]
        return value

    def hash(self, file):
        path = Path(file).resolve()
        stat = path.stat()
        key = (str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        with self.lock:
            if key not in self.hashes:
                with path.open("rb") as stream:
                    self.hashes[key] = hashlib.file_digest(stream, "sha256").hexdigest()
            return self.hashes[key]

    def signature(self, file):
        path = Path(file)
        if path.is_dir():
            return [
                (str(p.relative_to(path)), self.hash(p))
                for p in sorted(path.rglob("*"))
                if p.is_file()
            ]
        return self.hash(path)

    def tool(self, name):
        with self.lock:
            if name not in self.tools:
                executable = shutil.which(name)
                if not executable:
                    raise FileNotFoundError(name)
                self.tools[name] = self.hash(executable)
            return self.tools[name]

    def key(self, settings, inputs=(), tools=()):
        # No version in the key: the modules a stage runs are inputs hashed by content, so
        # an upgrade misses only the stages whose code changed.
        data = [
            self.portable(settings),
            [(self.label(p), self.signature(p)) for p in inputs],
            [(t, self.tool(t)) for t in tools],
        ]
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    def run(self, name, outputs, settings, action, *, inputs=(), tools=()):
        outputs = [Path(p) for p in outputs]
        stamp = outputs[0].with_name(outputs[0].name + ".cache.json")
        key = self.key(settings, [Path(__file__), *inputs], tools)
        old = False
        try:
            prior = json.loads(stamp.read_text("utf-8"))
            old = prior.get("format") != FORMAT
            valid = (
                not old
                and prior["key"] == key
                and prior["outputs"] == [self.hash(p) for p in outputs]
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            valid = False
        with self.lock:
            self.events.append(
                {
                    "stage": name,
                    "hit": valid,
                    "outputs": [str(p) for p in outputs],
                    **({"old_format": True} if old else {}),
                }
            )
        from urdido.progress import cache_status

        cache_status(valid)
        if valid:
            return prior.get("result")
        stamp.unlink(missing_ok=True)
        result = action()
        if self.key(settings, [Path(__file__), *inputs], tools) != key:
            raise RuntimeError(f"{name}: inputs changed during the stage; build again")
        record = {
            "format": FORMAT,
            "key": key,
            "outputs": [self.hash(p) for p in outputs],
            "result": result,
        }
        temporary = stamp.with_name(stamp.name + f".{os.getpid()}.tmp")
        try:
            temporary.write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, stamp)
        finally:
            temporary.unlink(missing_ok=True)
        return result

    def publish(self):
        self.report.parent.mkdir(parents=True, exist_ok=True)
        self.report.write_text(
            json.dumps({"stages": self.events}, indent=2) + "\n", encoding="utf-8"
        )
        hits = sum(e["hit"] for e in self.events)
        old = sum(e.get("old_format", False) for e in self.events)
        stale = (
            f", {old} from an older urdido that could not be verified" if old else ""
        )
        print(
            f"cache: {hits} hit(s), {len(self.events) - hits} miss(es){stale}; {self.report}"
        )


def file_hash(file):
    current = CURRENT.get()
    if current:
        return current.hash(file)
    with Path(file).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(name, outputs, settings, action, *, inputs=(), tools=()):
    from urdido.progress import unit

    with unit(name, Path(outputs[0]).name):
        current = CURRENT.get()
        if current is None:
            return action()
        return current.run(name, outputs, settings, action, inputs=inputs, tools=tools)


@contextmanager
def configured(report: Path, *, enabled=True, roots: dict[str, str] | None = None):
    current = Session(report, roots) if enabled else None
    token = CURRENT.set(current)
    try:
        yield current
    finally:
        CURRENT.reset(token)
        if current:
            current.publish()
