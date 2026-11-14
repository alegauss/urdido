"""VM44: declared Compose fixtures behind visits; PW710 tracks capture.web support."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
        self.compose = (self.root / self.spec["compose"]).resolve()
        self.compose.relative_to(self.root)
        self.project = "vm-" + name + "-" + hashlib.sha256(str(self.root).encode()).hexdigest()[:10]
        self.record = self.root / ".instances" / f"{name}.json"
        self.name = name
        self.spec_sha = hashlib.sha256(json.dumps(self.spec, sort_keys=True).encode()).hexdigest()

    def run(self, *args: str) -> str:
        try:
            result = subprocess.run(["docker", "compose", "-p", self.project, "-f", str(self.compose), *args],
                                    cwd=self.root, capture_output=True, text=True, encoding="utf-8", check=True)
        except subprocess.CalledProcessError as error:
            raise RuntimeError(f"instance Docker command failed: {error.stderr}") from None
        return result.stdout

    def containers(self) -> list[dict]:
        text = self.run("ps", "--format", "json").strip()
        if not text:
            return []
        data = json.loads(text) if text.startswith("[") else [json.loads(line) for line in text.splitlines()]
        return [{k: row.get(k) for k in ("ID", "Image", "Service", "State")} for row in data]

    def owned(self) -> dict | None:
        data = json.loads(self.record.read_text(encoding="utf-8")) if self.record.exists() else None
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
            except (URLError, TimeoutError):
                status = None
            if status in expected:
                return
            time.sleep(0.5)
        raise RuntimeError(f"instance {self.name}: readiness timed out at {url}")

    def plan(self) -> dict:
        return {"instance": self.name, "project": self.project, "compose": str(self.compose),
                "url": self.spec["url"], "setup": self.spec.get("setup", []),
                "reset": "down --volumes --remove-orphans, then up and setup"}

    def up(self) -> dict:
        previous = self.owned()
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
        self.record.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data

    def down(self):
        data = self.owned()
        if data is None:
            raise RuntimeError("instance has not been created by video-maker")
        self.run("down", "--volumes", "--remove-orphans")
        self.record.unlink()

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
        data = self.owned()
        if not data or not data.get("ready") or self.containers() != data["containers"] \
                or data.get("instance_spec_sha256") != self.spec_sha:
            raise RuntimeError("instance is not ready or its containers changed; run instance up/reset")
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "up", "reset", "down", "capture"])
    parser.add_argument("declaration", type=Path)
    parser.add_argument("name")
    parser.add_argument("--visit", type=Path)
    args = parser.parse_args(argv)
    instance = Instance(args.declaration, args.name)
    if args.action == "plan":
        print(json.dumps(instance.plan(), indent=2))
    elif args.action == "down":
        instance.down()
    elif args.action == "capture":
        if not args.visit:
            parser.error("capture requires --visit")
        print(instance.capture(args.visit))
    else:
        if args.action == "reset":
            instance.down()
        print(json.dumps(instance.up(), indent=2))
    return 0
