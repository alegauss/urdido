"""One adapter runs the provider, behind seams the rest of the code calls (UR25)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from urdido import providers
from urdido.providers import polyweave as provider

SOURCE = Path(__file__).resolve().parents[1] / "src" / "urdido"


@pytest.fixture
def fake(monkeypatch):
    """A provider that records each call and answers what the test sets."""
    calls, answers = [], []

    def run(args, **options):
        calls.append(args)
        code, out = answers.pop(0) if answers else (0, "{}")
        return SimpleNamespace(
            returncode=code, stdout=out, stderr="it broke" if code else ""
        )

    monkeypatch.setattr(provider, "RUN", run)
    return SimpleNamespace(calls=calls, answers=answers)


def test_voice_lines_passes_its_flags_as_the_provider_reads_them(fake, tmp_path):
    fake.answers.append((0, json.dumps({"ok": True, "current": []})))
    answer = providers.voice_lines(
        tmp_path, "lines.json", "pt-BR", "eleven", keys=["intro", "outro"]
    )
    assert answer == {"ok": True, "current": []}
    args = fake.calls[0]
    assert args[1:4] == ["-m", "polyweave", "voice.lines"]
    assert args[4:] == [
        "--script",
        "lines.json",
        "--locale",
        "pt-BR",
        "--service",
        "eleven",
        "--spend",
        "false",
        "--keys",
        "intro",
        "outro",
        "--root",
        str(tmp_path.resolve()),
        "--json",
    ]


def test_a_refusal_and_a_failed_answer_are_provider_refusals(fake, tmp_path):
    fake.answers += [(2, ""), (0, '{"ok": false, "why": "no credit"}'), (0, "not json")]
    with pytest.raises(
        providers.ProviderRefused, match="capture.web refused: it broke"
    ):
        providers.capture_web(tmp_path, "visit.web.toml")
    with pytest.raises(
        RuntimeError, match="no credit"
    ):  # still a RuntimeError for callers
        providers.operation("stock.fetch", tmp_path, id=1)
    with pytest.raises(providers.ProviderRefused, match="answered no JSON"):
        providers.operation("stock.fetch", tmp_path)


def test_flags_spell_booleans_lists_and_absent_values():
    assert provider.flags(
        {"all": True, "dry": False, "keys": ["a", "b"], "out": None, "n": 3}
    ) == ["--all", "--keys", "a", "b", "--n", "3"]


def test_without_the_provider_installed_the_real_call_refuses_by_extra(
    monkeypatch, tmp_path
):
    from urdido.extras import MissingExtra

    monkeypatch.setattr(provider.importlib.util, "find_spec", lambda name: None)
    assert not providers.available()
    with pytest.raises(MissingExtra, match=r"pip install urdido\[polyweave\]"):
        providers.operation("voice.lines", tmp_path)
    assert "pip install urdido[polyweave]" in providers.unavailable()


def test_the_project_file_and_work_folder_are_named_by_the_adapter_alone(tmp_path):
    (tmp_path / "polyweave.toml").write_text(
        '[service.eleven]\nkey_env = "K"\n', encoding="utf-8"
    )
    assert providers.config(tmp_path) == {"service": {"eleven": {"key_env": "K"}}}
    assert (
        providers.work_dir(tmp_path, "prepare", "x")
        == tmp_path / ".polyweave" / "prepare" / "x"
    )


def test_no_module_outside_the_adapter_runs_or_reads_the_provider():
    for file in SOURCE.rglob("*.py"):
        if "providers" in file.parts or file.name == "extras.py":
            continue
        text = file.read_text(encoding="utf-8")
        assert "polyweave" not in text, file
