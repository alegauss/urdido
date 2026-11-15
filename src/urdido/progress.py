"""VM63 / PW715: live build stages, cache outcomes and bounded JSON events."""
from __future__ import annotations

import json
import sys
import threading
import time
from collections import defaultdict
from contextlib import contextmanager, nullcontext, redirect_stdout
from contextvars import ContextVar
from pathlib import Path

CURRENT = ContextVar("build_progress", default=None)
UNIT = ContextVar("progress_unit", default=None)
ALIASES = {"illustrated clip": "source clips", "illustrated take join": "join", "audio mix": "mix", "final mux": "mux",
           "preview mux": "mux", "preview trim": "source clips"}
STAGES = ("validation", "raster", "source clips", "join", "highlights", "mix", "mux", "verification")


class Session:
    def __init__(self, report, mode="human", stream=None, heartbeat=10):
        self.report, self.mode, self.stream = Path(report), mode, stream or (sys.stdout if mode == "json" else sys.stderr)
        self.started = time.monotonic()
        self.lock = threading.RLock()
        self.counts = defaultdict(lambda: {"completed": 0, "total": None, "cache_hits": 0, "cache_misses": 0})
        self.active, self.finished, self.sequence = {}, set(), 0
        self.failed = set()
        self.last_success = None
        self.events = []
        self.report.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.report.open("w", encoding="utf-8")
        self.stop = threading.Event()
        self.heartbeat = heartbeat
        self.thread = threading.Thread(target=self.pulse, daemon=True)

    def emit(self, event, stage="build", subject="", **detail):
        with self.lock:
            self.sequence += 1
            row = {"sequence": self.sequence, "event": event, "stage": stage, "subject": subject,
                   "elapsed_seconds": round(time.monotonic() - self.started, 3),
                   **self.counts[stage], "last_success": self.last_success, **detail}
            self.events.append(row)
            self.file.write(json.dumps(row, ensure_ascii=False) + "\n")
            self.file.flush()
            if self.mode == "json":
                print(json.dumps(row, ensure_ascii=False), file=self.stream, flush=True)
            elif self.mode == "human":
                units = f"{row['completed']}/{row['total'] if row['total'] is not None else '?'}"
                text = f"[{row['elapsed_seconds']:.1f}s] {stage} {event} {units}"
                if subject:
                    text += f" {subject}"
                if event == "cache":
                    text += " hit" if detail["hit"] else " miss"
                if event == "failed":
                    text += f" ({detail['error_type']}); last success: {self.last_success}"
                if event == "heartbeat":
                    text += " " + ", ".join(f"{v['stage']}:{v['subject']} ({v['seconds']:.1f}s)" for v in detail["active"])
                print(text, file=self.stream, flush=True)
            return row

    def pulse(self):
        while not self.stop.wait(self.heartbeat):
            with self.lock:
                active = [{"stage": v["stage"], "subject": v["subject"], "seconds": round(time.monotonic() - v["started"], 3)}
                          for v in self.active.values()]
                if active:
                    self.emit("heartbeat", active=active)

    def plan(self, stage, total):
        with self.lock:
            self.counts[stage]["total"] = (self.counts[stage]["total"] or 0) + total
            self.emit("planned", stage)

    def close(self, error=None):
        self.stop.set()
        self.thread.join()
        self.emit("failed" if error else "finished", error_type=type(error).__name__ if error else None,
                  pending=[stage for stage, counts in self.counts.items() if stage in self.failed
                           or (counts["total"] is not None and counts["completed"] < counts["total"])],
                  not_observed=[stage for stage in STAGES if stage not in self.finished],
                  counts={key: dict(value) for key, value in self.counts.items()})
        self.file.close()


def plan(stage, total):
    current = CURRENT.get()
    if current:
        current.plan(stage, total)


def cache_status(hit):
    current, unit = CURRENT.get(), UNIT.get()
    if current and unit:
        with current.lock:
            current.counts[unit["stage"]]["cache_hits" if hit else "cache_misses"] += 1
            current.emit("cache", unit["stage"], unit["subject"], hit=hit)


def run(stage, subject, action):
    with unit(stage, subject):
        return action()


@contextmanager
def unit(stage, subject=""):
    current = CURRENT.get()
    if current is None:
        yield
        return
    stage = ALIASES.get(stage, stage)
    row = {"stage": stage, "subject": str(subject), "started": time.monotonic()}
    token = UNIT.set(row)
    key = id(row)
    with current.lock:
        if stage in {"validation", "highlights", "mix", "mux", "verification"}:
            counts = current.counts[stage]
            if counts["total"] is None or counts["completed"] >= counts["total"]:
                counts["total"] = counts["completed"] + 1
        current.active[key] = row
        current.emit("started", stage, row["subject"])
    try:
        yield
    except BaseException as exc:
        # Exception messages can contain encoder argv, URLs or credentials. Keep them
        # in the normal exception channel; progress records only type and known subject.
        with current.lock:
            current.failed.add(stage)
            current.emit("failed", stage, row["subject"], error_type=type(exc).__name__,
                         unit_seconds=round(time.monotonic() - row["started"], 3))
        raise
    else:
        with current.lock:
            current.counts[stage]["completed"] += 1
            current.finished.add(stage)
            current.last_success = {"stage": stage, "subject": row["subject"]}
            current.emit("finished", stage, row["subject"], unit_seconds=round(time.monotonic() - row["started"], 3))
    finally:
        with current.lock:
            current.active.pop(key, None)
        UNIT.reset(token)


@contextmanager
def configured(report, *, mode="human", stream=None, heartbeat=10):
    if mode not in {"human", "json", "off"}:
        raise ValueError("progress mode must be human, json or off")
    session = Session(report, mode, stream, heartbeat)
    token = CURRENT.set(session)
    session.emit("started")
    session.thread.start()
    error = None
    try:
        with redirect_stdout(sys.stderr) if mode == "json" else nullcontext():
            yield session
    except BaseException as exc:
        error = exc
        raise
    finally:
        session.close(error)
        CURRENT.reset(token)
