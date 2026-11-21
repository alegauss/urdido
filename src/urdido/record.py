"""Record a scene video with one command, as its declaration lists the steps (UR10).

    urdido record <video.toml>                 every step, in order
    urdido record <video.toml> --from agent    resume a failed run at that step
    urdido record <video.toml> --list          the steps, and what a failed run left

The steps live in video.toml, each a command and what it makes:

    [[record.step]]
    name = "scenes"
    command = ["npm", "run", "scenes"]       # a list as is; a string in a shell
    makes = ["recordings/scenes", "recordings/instance.json"]

    [[record.step]]
    name = "down"
    command = "npm run instance:down"
    always = true                            # runs last, even after a failure

The run stops at the first step that fails. What the steps make is the recording, and
the last complete one is kept until a new one is: before the first step, everything the
steps make is moved aside to `.urdido/record/previous/`. A run that completes drops it.
A run that fails moves what its finished steps made to `.urdido/record/pending/`, puts
the previous recording back, and names the step to resume from; `--from <step>` puts
the pending outputs of the steps before it back in place and carries on from there.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

STATE = Path(".urdido") / "record"


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str] | str
    makes: tuple[str, ...]
    always: bool = False


class RecordFailed(Exception):
    """A step failed; the message names it and the step to resume from."""


def steps_of(document: dict) -> list[Step]:
    rows = document.get("record", {}).get("step")
    if not rows:
        raise ValueError("record: video.toml declares no [[record.step]]")
    steps, names = [], set()
    for row in rows:
        name, command = row.get("name"), row.get("command")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("record: each [[record.step]] has a name of its own")
        names.add(name)
        if not command or not isinstance(command, (str, list)):
            raise ValueError(f"record: step {name} needs a command, a list or a string")
        makes = row.get("makes", [])
        if not isinstance(makes, list) or not all(isinstance(m, str) for m in makes):
            raise ValueError(f"record: step {name}'s makes is a list of paths")
        if any(Path(m).is_absolute() or ".." in Path(m).parts for m in makes):
            raise ValueError(
                f"record: step {name} makes paths inside the video's folder"
            )
        steps.append(Step(name, command, tuple(makes), bool(row.get("always", False))))
    return steps


def move(source: Path, target: Path) -> None:
    if not source.exists():
        return
    if target.exists():
        remove(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))


def remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


class Recorder:
    def __init__(self, here: Path, steps: list[Step], run=None):
        self.here = here
        self.steps = steps
        self.state = here / STATE
        self.run = run or self._run

    def _run(self, step: Step) -> int:
        shell = isinstance(step.command, str)
        return subprocess.run(step.command, cwd=self.here, shell=shell).returncode

    @property
    def record(self) -> Path:
        return self.state / "state.json"

    def pending(self) -> dict:
        try:
            return json.loads(self.record.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def shelve(self, area: str, makes) -> None:
        for made in makes:
            move(self.here / made, self.state / area / made)

    def unshelve(self, area: str, makes) -> None:
        for made in makes:
            move(self.state / area / made, self.here / made)

    def recording(self, steps) -> list[str]:
        return [made for step in steps for made in step.makes]

    def start(self, resume: str | None) -> list[Step]:
        ordered = [s for s in self.steps if not s.always]
        if resume is None:
            if self.pending():
                self.discard()
            remove(self.state / "previous")
            self.shelve("previous", self.recording(ordered))
            return ordered
        names = [s.name for s in ordered]
        if resume not in names:
            raise ValueError(
                f"record: no step named {resume}; the steps are {', '.join(names)}"
            )
        state = self.pending()
        done = state.get("done", [])
        before = names[: names.index(resume)]
        if not state or any(name not in done for name in before):
            raise ValueError(
                f"record: no failed run finished every step before {resume}; "
                "run every step"
            )
        kept = [s for s in ordered if s.name in before]
        remove(self.state / "previous")
        self.shelve("previous", self.recording(ordered))
        self.unshelve("pending", self.recording(kept))
        return ordered[names.index(resume) :]

    def discard(self) -> None:
        remove(self.state / "pending")
        self.record.unlink(missing_ok=True)

    def fail(self, step: Step, done: list[str]) -> None:
        self.shelve("pending", self.recording(s for s in self.steps if s.name in done))
        for made in step.makes:
            remove(self.here / made)
        self.unshelve("previous", self.recording(self.steps))
        self.state.mkdir(parents=True, exist_ok=True)
        self.record.write_text(
            json.dumps({"done": done, "failed": step.name}, indent=2) + "\n",
            encoding="utf-8",
        )

    def go(self, resume: str | None = None) -> list[str]:
        """Run the steps; the names of those that ran, or RecordFailed."""
        todo = self.start(resume)
        done = list(self.pending().get("done", [])) if resume else []
        failed = None
        for step in todo:
            print(f"record: {step.name}", flush=True)
            if self.run(step) != 0:
                failed = step
                break
            done.append(step.name)
        problems = []
        for step in (s for s in self.steps if s.always):
            print(f"record: {step.name} (always)", flush=True)
            if self.run(step) != 0:
                problems.append(step.name)
        if failed:
            self.fail(failed, done)
            raise RecordFailed(
                f"record: {failed.name} failed; the previous recording is back in "
                f"place and what {', '.join(done) or 'no step'} made is kept aside. "
                f"Resume with --from {failed.name}"
            )
        remove(self.state / "previous")
        self.discard()
        if problems:
            raise RecordFailed(
                f"record: the recording is complete, but {', '.join(problems)} failed"
            )
        return done


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="urdido record")
    p.add_argument("declaration")
    p.add_argument("--from", dest="resume", help="resume a failed run at this step")
    p.add_argument(
        "--list", action="store_true", help="the steps, and what a failed run left"
    )
    args = p.parse_args(argv)
    declaration = Path(args.declaration).resolve()
    try:
        steps = steps_of(tomllib.loads(declaration.read_text(encoding="utf-8")))
        recorder = Recorder(declaration.parent, steps)
        if args.list:
            state = recorder.pending()
            for step in steps:
                mark = "done" if step.name in state.get("done", []) else ""
                mark = "failed" if step.name == state.get("failed") else mark
                print(
                    f"{step.name}{' (always)' if step.always else ''}  {mark}".rstrip()
                )
            return 0
        recorder.go(args.resume)
    except (ValueError, RecordFailed) as stopped:
        print(stopped, file=sys.stderr)
        return 1
    print("record: complete")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
