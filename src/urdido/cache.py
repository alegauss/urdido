"""VM55: verified, independently resumable production stages (HTML gap: PW700)."""
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


class Session:
    def __init__(self, report: Path):
        self.report = report
        self.hashes = {}
        self.lock = threading.RLock()
        self.events = []
        self.tools = {}

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
            return [(str(p.relative_to(path)), self.hash(p)) for p in sorted(path.rglob("*")) if p.is_file()]
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
        data = [settings, [(str(p), self.signature(p)) for p in inputs],
                [(t, self.tool(t)) for t in tools]]
        return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def run(self, name, outputs, settings, action, *, inputs=(), tools=()):
        outputs = [Path(p) for p in outputs]
        stamp = outputs[0].with_name(outputs[0].name + ".cache.json")
        key = self.key(settings, [Path(__file__), *inputs], tools)
        try:
            prior = json.loads(stamp.read_text("utf-8"))
            valid = prior["key"] == key and prior["outputs"] == [self.hash(p) for p in outputs]
        except (OSError, ValueError, KeyError, TypeError):
            valid = False
        with self.lock:
            self.events.append({"stage": name, "hit": valid, "outputs": [str(p) for p in outputs]})
        from urdido.progress import cache_status

        cache_status(valid)
        if valid:
            return prior.get("result")
        stamp.unlink(missing_ok=True)
        result = action()
        if self.key(settings, [Path(__file__), *inputs], tools) != key:
            raise RuntimeError(f"{name}: inputs changed during the stage; build again")
        record = {"key": key, "outputs": [self.hash(p) for p in outputs], "result": result}
        temporary = stamp.with_name(stamp.name + f".{os.getpid()}.tmp")
        try:
            temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, stamp)
        finally:
            temporary.unlink(missing_ok=True)
        return result

    def publish(self):
        self.report.parent.mkdir(parents=True, exist_ok=True)
        self.report.write_text(json.dumps({"stages": self.events}, indent=2) + "\n", encoding="utf-8")
        hits = sum(e["hit"] for e in self.events)
        print(f"cache: {hits} hit(s), {len(self.events) - hits} miss(es); {self.report}")


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
def configured(report: Path, *, enabled=True):
    current = Session(report) if enabled else None
    token = CURRENT.set(current)
    try:
        yield current
    finally:
        CURRENT.reset(token)
        if current:
            current.publish()
