"""VM44: declared Compose fixtures behind visits; PW710 tracks capture.web support.

VM85: an instance can instead be one `docker run`, declared exactly as a person types it
(`run = "docker run -p 2710:2710 ghcr.io/openviglet/shio"`), so a scene that shows the start shows
the command that really ran. It runs in the foreground, as typed, from a detached process whose
output is the instance's log; its container is the one that publishes the declared host port,
which must be free before it starts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
import tomllib
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import urlopen


class Instance:
    def __init__(self, declaration: Path, name: str):
        self.root = declaration.resolve().parent
        with declaration.open("rb") as file:
            self.spec = tomllib.load(file)["instances"][name]
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,39}", name):
            raise ValueError("instance names use lowercase letters, digits and hyphens")
        self.mode = "run" if "run" in self.spec else "compose"
        if self.mode == "run":
            self.command = run_command(self.spec["run"])
            self.port = published_port(self.command)
            if self.spec.get("setup"):
                raise ValueError("a run instance takes no setup: declare a Compose file for one")
            self.compose = None
        else:
            self.compose = (self.root / self.spec["compose"]).resolve()
            self.compose.relative_to(self.root)
        self.project = "vm-" + name + "-" + hashlib.sha256(str(self.root).encode()).hexdigest()[:10]
        self.record = self.root / ".instances" / f"{name}.json"
        self.name = name
        self.spec_sha = hashlib.sha256(json.dumps(self.spec, sort_keys=True).encode()).hexdigest()
        self.startup = None

    def run(self, *args: str) -> str:
        try:
            result = subprocess.run(["docker", "compose", "-p", self.project, "-f", str(self.compose), *args],
                                    cwd=self.root, capture_output=True, text=True, encoding="utf-8", check=True)
        except subprocess.CalledProcessError as error:
            raise RuntimeError(f"instance Docker command failed: {error.stderr}") from None
        if args and args[0] == "up":
            self.startup = {"command": subprocess.list2cmdline(result.args),
                            "answered": result.stdout + result.stderr}
        return result.stdout

    def containers(self) -> list[dict]:
        if self.mode == "run":
            return self.run_containers(self.recorded_ids())
        text = self.run("ps", "--format", "json").strip()
        if not text:
            return []
        data = json.loads(text) if text.startswith("[") else [json.loads(line) for line in text.splitlines()]
        return [{k: row.get(k) for k in ("ID", "Image", "Service", "State")} for row in data]

    def recorded_ids(self) -> list[str]:
        data = json.loads(self.record.read_text(encoding="utf-8")) if self.record.exists() else {}
        return [row["ID"] for row in data.get("containers", [])] or data.get("starting", [])

    def run_containers(self, ids: list[str]) -> list[dict]:
        rows = []
        for cid in ids:
            text = docker("ps", "-a", "--filter", f"id={cid}", "--format", "json").strip()
            for line in text.splitlines():
                row = json.loads(line)
                rows.append({"ID": row["ID"], "Image": row.get("Image"), "Service": self.name,
                             "State": row.get("State")})
        return rows

    def publishing(self) -> list[str]:
        return docker("ps", "-q", "--filter", f"publish={self.port}").split()

    def run_up(self, data: dict) -> dict:
        if self.publishing():
            raise RuntimeError(f"instance {self.name}: port {self.port} is already published by a container "
                               "video-maker did not start; stop it first")
        log = self.record.with_suffix(".log")
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        with log.open("wb") as out:
            process = subprocess.Popen(self.command, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                       cwd=self.root, creationflags=flags, start_new_session=os.name != "nt")
        deadline = time.monotonic() + self.spec.get("timeout", 120)
        ids = []
        while not ids:
            if process.poll() is not None:
                raise RuntimeError(f"instance {self.name}: `{self.spec['run']}` exited: "
                                   + log.read_text(encoding="utf-8", errors="replace")[-2000:])
            if time.monotonic() > deadline:
                raise RuntimeError(f"instance {self.name}: no container published port {self.port}")
            ids = self.publishing()
            time.sleep(0.5)
        data["starting"] = ids
        self.record.write_text(json.dumps(data), encoding="utf-8")
        self.wait()
        # What the foreground run prints is the container's own output, which `docker logs` reads
        # back whole (the detached client's file can stay empty on Windows).
        logs = subprocess.run(["docker", "logs", *ids[:1]], capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        self.startup = {"command": self.spec["run"], "answered": "", "logs_command": "",
                        "logs": (logs.stdout + logs.stderr) or log.read_text(encoding="utf-8", errors="replace")}
        return data

    def owned(self) -> dict | None:
        data = json.loads(self.record.read_text(encoding="utf-8")) if self.record.exists() else None
        if self.mode == "run":
            return data
        if data and data["project"] != self.project:
            raise RuntimeError("instance ownership record names a different Compose project")
        if self.containers() and data is None:
            raise RuntimeError("existing Compose containers have no instance ownership record")
        return data

    def wait(self):
        deadline = time.monotonic() + self.spec.get("timeout", 120)
        url = self.spec.get("ready", self.spec["url"])
        expected = self.spec.get("ready_status", [200])
        while time.monotonic() < deadline:
            try:
                with urlopen(url, timeout=3) as response:
                    status = response.status
            except HTTPError as error:
                status = error.code
            except (URLError, OSError):
                status = None
            if status in expected:
                return
            time.sleep(0.5)
        raise RuntimeError(f"instance {self.name}: readiness timed out at {url}")

    def plan(self) -> dict:
        if self.mode == "run":
            return {"instance": self.name, "run": self.spec["run"], "port": self.port, "url": self.spec["url"],
                    "reset": "docker rm --force --volumes, then the same run"}
        return {"instance": self.name, "project": self.project, "compose": str(self.compose),
                "url": self.spec["url"], "setup": self.spec.get("setup", []),
                "reset": "down --volumes --remove-orphans, then up and setup"}

    def up(self) -> dict:
        previous = self.owned()
        if self.mode == "run":
            if previous:
                self.status()
                return previous
            data = {"project": self.project, "generation": uuid.uuid4().hex, "ready": False}
            self.record.parent.mkdir(parents=True, exist_ok=True)
            self.record.write_text(json.dumps(data), encoding="utf-8")
            self.run_up(data)
            containers = self.containers()
            data.pop("starting", None)
            inspect = subprocess.run(["docker", "inspect", "--format", "{{.Id}} {{.Image}}",
                                      *[row["ID"] for row in containers]], capture_output=True, text=True, check=True)
            data.update(ready=True, containers=containers, images=inspect.stdout.splitlines(),
                        instance_spec_sha256=self.spec_sha, url=self.spec["url"], startup=self.startup)
            self.record.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            return data
        before = self.containers()
        config = json.loads(self.run("config", "--format", "json"))
        if any(service.get("container_name") for service in config["services"].values()) \
                or any(item.get("external") or item.get("name") and not item["name"].startswith(self.project + "_")
                       for kind in ("volumes", "networks") for item in config.get(kind, {}).values()):
            raise RuntimeError("instance Compose files must use project-owned containers, volumes and networks")
        generation = previous.get("generation") if previous else uuid.uuid4().hex
        data = {"project": self.project, "generation": generation, "ready": False}
        self.record.parent.mkdir(parents=True, exist_ok=True)
        self.record.write_text(json.dumps(data), encoding="utf-8")
        self.run("up", "-d", "--wait", "--wait-timeout", str(self.spec.get("timeout", 120)))
        if not previous or not previous.get("ready") or before != self.containers() \
                or previous.get("compose_sha256") != hashlib.sha256(self.compose.read_bytes()).hexdigest() \
                or previous.get("instance_spec_sha256") != self.spec_sha:
            for command in self.spec.get("setup", []):
                self.run(*command)
        self.wait()
        containers = self.containers()
        if not containers:
            raise RuntimeError("instance started no running containers")
        inspect = subprocess.run(["docker", "inspect", "--format", "{{.Id}} {{.Image}}",
                                  *[row["ID"] for row in containers]], capture_output=True, text=True, check=True)
        data.update(ready=True, containers=containers, images=inspect.stdout.splitlines(),
                    instance_spec_sha256=self.spec_sha,
                    compose_sha256=hashlib.sha256(self.compose.read_bytes()).hexdigest(), url=self.spec["url"])
        if self.spec.get("startup_logs_service"):
            args = ("logs", "--no-color", "--no-log-prefix", self.spec["startup_logs_service"])
            logs = self.run(*args)
            data["startup"] = {**self.startup, "logs": logs,
                               "logs_command": subprocess.list2cmdline([
                                   "docker", "compose", "-p", self.project, "-f", str(self.compose), *args])}
        self.record.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data

    def down(self):
        data = self.owned()
        if data is None:
            raise RuntimeError("instance has not been created by video-maker")
        if self.mode == "run":
            # only those still there: a run interrupted mid-recording can leave a record whose
            # container is already gone
            ids = [row["ID"] for row in self.containers()]
            if ids:
                docker("rm", "--force", "--volumes", *ids)
            self.record.unlink()
            return
        self.run("down", "--volumes", "--remove-orphans")
        self.record.unlink()

    def status(self) -> dict:
        data = self.owned()
        # The same containers, by id, service and state. Not by `Image`: compose prints the tag while it
        # still names the running image and its digest once the tag moves on (a release published
        # mid-recording, 2026-11-17), though the container and what it runs are unchanged.
        same = lambda rows: [{k: row.get(k) for k in ("ID", "Service", "State")} for row in rows]
        if not data or not data.get("ready") or same(self.containers()) != same(data["containers"]) \
                or data.get("instance_spec_sha256") != self.spec_sha:
            raise RuntimeError("instance is not ready or its containers changed; run instance up/reset")
        return data

    def capture(self, visit: Path):
        raw = visit.read_bytes()
        source = raw.decode("utf-8")
        original = tomllib.loads(source)
        web = original["web"]
        origin = lambda url: (urlsplit(url).scheme, urlsplit(url).netloc)
        if web.get("instance") != self.name or origin(web["url"]) != origin(self.spec["url"]):
            raise ValueError("visit must name this instance and use its declared origin")
        out = (self.root / web["out"]).resolve()
        out.relative_to(self.root)
        before = out.stat().st_mtime_ns if out.exists() else None
        data = self.status()
        self.wait()
        # PW710: capture.web's strict web schema does not yet accept instance.
        compatible = re.sub(r"(?m)^[ \t]*instance[ \t]*=.*(?:\n|$)", "", source, count=1)
        expected = {**original, "web": {k: v for k, v in web.items() if k != "instance"}}
        if tomllib.loads(compatible) != expected:
            raise ValueError("visit instance must be a single-line unquoted instance key")
        capture_sha = hashlib.sha256(compatible.encode()).hexdigest()
        forwarded = self.record.parent / f"capture-{capture_sha}.web.toml"
        forwarded.write_text(compatible, encoding="utf-8", newline="")
        try:
            result = subprocess.run([sys.executable, "-m", "polyweave", "capture.web", "--source",
                                     str(forwarded.relative_to(self.root)), "--root", str(self.root), "--json"],
                                    capture_output=True, text=True, encoding="utf-8", check=True,
                                    env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        except subprocess.CalledProcessError as error:
            raise RuntimeError(f"capture.web failed: {error.stdout or error.stderr}") from None
        answer = json.loads(result.stdout)
        if answer.get("ok") is False:
            raise RuntimeError("capture.web refused the visit: " + str(answer.get("why", answer)))
        if self.containers() != data["containers"]:
            raise RuntimeError("instance changed during capture")
        if not out.is_file() or out.stat().st_mtime_ns == before:
            raise RuntimeError("capture.web did not produce the declared recording")
        out.with_suffix(out.suffix + ".instance.json").write_text(json.dumps({
            "instance": self.name, "visit": str(visit), "fixture": data,
            "visit_sha256": hashlib.sha256(raw).hexdigest(), "capture_spec_sha256": capture_sha,
            "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}, indent=2) + "\n", encoding="utf-8")
        return out


def docker(*args: str) -> str:
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"instance Docker command failed: {error.stderr}") from None


def run_command(text: str) -> list[str]:
    """The declared `docker run`, split as a shell would. Detached or named runs are refused: the
    point of `run` is the command a person types, which keeps the terminal and names nothing."""
    words = shlex.split(text)
    if words[:2] != ["docker", "run"]:
        raise ValueError(f"an instance's run must be a `docker run` command, got {text!r}")
    if any(w in {"-d", "--detach", "--name", "--rm"} or w.startswith("--name=") for w in words[2:]):
        raise ValueError("an instance's run is the command as a person types it: no -d, --name or --rm")
    return words


def published_port(words: list[str]) -> int:
    """The one host port the run publishes (`-p 2710:2710`, `-p 127.0.0.1:2710:2710`)."""
    ports = [words[i + 1] for i, w in enumerate(words[:-1]) if w in {"-p", "--publish"}]
    ports += [w.split("=", 1)[1] for w in words if w.startswith("--publish=")]
    if len(ports) != 1:
        raise ValueError("an instance's run must publish exactly one port with -p")
    parts = ports[0].split("/")[0].split(":")
    if len(parts) < 2 or not parts[-2].isdigit():
        raise ValueError(f"an instance's run must name its host port, got -p {ports[0]}")
    return int(parts[-2])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "up", "fresh", "reset", "down", "capture", "status"])
    parser.add_argument("declaration", type=Path)
    parser.add_argument("name")
    parser.add_argument("--visit", type=Path)
    args = parser.parse_args(argv)
    instance = Instance(args.declaration, args.name)
    if args.action == "plan":
        print(json.dumps(instance.plan(), indent=2))
    elif args.action == "down":
        instance.down()
    elif args.action == "status":
        print(json.dumps(instance.status(), indent=2))
    elif args.action == "capture":
        if not args.visit:
            parser.error("capture requires --visit")
        print(instance.capture(args.visit))
    else:
        if args.action == "reset" or args.action == "fresh" and instance.record.exists():
            instance.down()
        print(json.dumps(instance.up(), indent=2))
    return 0
