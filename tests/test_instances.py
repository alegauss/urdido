"""VM44: ownership, explicit reset and recording provenance for product fixtures."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from videomaker.instances import Instance


@pytest.fixture
def instance(tmp_path):
    declaration = tmp_path / "video.toml"
    declaration.write_text('[instances.demo]\ncompose="compose.yaml"\nurl="http://localhost:8999/"\n'
                           'setup=[["run","--rm","seed"]]\n', encoding="utf-8")
    (tmp_path / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
    return Instance(declaration, "demo")


def test_plan_has_no_docker_side_effects_vm44(instance, monkeypatch):
    monkeypatch.setattr(instance, "run", lambda *args: pytest.fail("plan called Docker"))
    assert instance.plan()["setup"] == [["run", "--rm", "seed"]]
    assert not instance.record.exists()


def test_unowned_containers_cannot_be_removed_vm44(instance, monkeypatch):
    monkeypatch.setattr(instance, "containers", lambda: [{"ID": "somebody-else"}])
    with pytest.raises(RuntimeError, match="ownership"):
        instance.down()


def test_up_reuses_setup_and_reset_creates_new_generation_vm44(instance, monkeypatch):
    calls, active = [], []

    def docker(*args):
        calls.append(args)
        if args[0] == "config":
            return json.dumps({"services": {"web": {"image": "nginx"}}})
        if args[0] == "up":
            active[:] = [{"ID": "container", "Image": "nginx", "State": "running", "Service": "web"}]
        if args[0] == "down":
            active.clear()
        return ""

    monkeypatch.setattr(instance, "run", docker)
    monkeypatch.setattr(instance, "containers", lambda: active.copy())
    monkeypatch.setattr(instance, "wait", lambda: None)
    monkeypatch.setattr("videomaker.instances.subprocess.run", lambda *args, **kwargs: SimpleNamespace(stdout="container sha256:actual\n"))
    first = instance.up()
    assert first["ready"] and first["images"] == ["container sha256:actual"]
    assert instance.up()["generation"] == first["generation"]
    assert calls.count(("run", "--rm", "seed")) == 1
    instance.down()
    assert instance.up()["generation"] != first["generation"]
    assert calls.count(("run", "--rm", "seed")) == 2


def test_external_resources_are_refused_before_up_vm44(instance, monkeypatch):
    calls = []
    monkeypatch.setattr(instance, "containers", lambda: [])

    def run(*args):
        calls.append(args)
        return json.dumps({"services": {"web": {"image": "nginx"}}, "volumes": {"db": {"external": True}}})

    monkeypatch.setattr(instance, "run", run)
    with pytest.raises(RuntimeError, match="project-owned"):
        instance.up()
    assert all(c[0] != "up" for c in calls)


def test_capture_records_hash_and_refuses_changed_containers_vm44(instance, monkeypatch):
    current = [{"ID": "one"}]
    instance.record.parent.mkdir()
    data = {"project": instance.project, "generation": "fresh", "ready": True, "containers": current,
            "instance_spec_sha256": instance.spec_sha}
    instance.record.write_text(json.dumps(data), encoding="utf-8")
    visit = instance.root / "visit.web.toml"
    visit.write_bytes(b'[web]\r\ninstance="demo"\r\nurl="http://localhost:8999/"\r\nout="capture.webm"\r\n')
    monkeypatch.setattr(instance, "containers", lambda: current.copy())
    monkeypatch.setattr(instance, "wait", lambda: None)

    def capture(*args, **kwargs):
        import hashlib

        forwarded = instance.root / args[0][args[0].index("--source") + 1]
        assert 'instance="demo"' not in forwarded.read_text()
        assert hashlib.sha256(forwarded.read_bytes()).hexdigest() in forwarded.name
        (instance.root / "capture.webm").write_bytes(b"actual capture")
        return SimpleNamespace(stdout='{"ok": true}')

    monkeypatch.setattr("videomaker.instances.subprocess.run", capture)
    output = instance.capture(visit)
    proof = json.loads(output.with_suffix(".webm.instance.json").read_text())
    assert proof["fixture"]["generation"] == "fresh" and len(proof["sha256"]) == 64
    assert proof["visit_sha256"] != proof["capture_spec_sha256"]
    current[:] = [{"ID": "recreated"}]
    with pytest.raises(RuntimeError, match="containers changed"):
        instance.capture(visit)


def test_readiness_retries_connection_closed_during_server_start_vm44(instance, monkeypatch):
    from http.client import RemoteDisconnected
    from urllib.error import HTTPError

    instance.spec["ready_status"] = [401]
    answers = iter([RemoteDisconnected("server starting"), HTTPError("http://localhost", 401, "ready", {}, None)])

    def request(*args, **kwargs):
        raise next(answers)

    monkeypatch.setattr("videomaker.instances.urlopen", request)
    monkeypatch.setattr("videomaker.instances.time.sleep", lambda seconds: None)
    instance.wait()


def test_a_tag_moving_on_does_not_change_the_containers(instance, monkeypatch):
    recorded = [{"ID": "one", "Image": "ghcr.io/openviglet/shio:latest", "Service": "shio", "State": "running"}]
    instance.record.parent.mkdir()
    instance.record.write_text(json.dumps({"project": instance.project, "ready": True, "containers": recorded,
                                           "instance_spec_sha256": instance.spec_sha}), encoding="utf-8")
    # a release was published meanwhile: compose now prints the running image by its digest
    monkeypatch.setattr(instance, "containers", lambda: [{**recorded[0], "Image": "sha256:c5d5abd4"}])
    assert instance.status()["containers"] == recorded
    monkeypatch.setattr(instance, "containers", lambda: [{**recorded[0], "ID": "two"}])
    with pytest.raises(RuntimeError, match="containers changed"):
        instance.status()
