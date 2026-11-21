"""A misspelled or missing key in video.toml is refused before the build (UR23)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from urdido.declaration import SCHEMA, check, json_schema, main
from urdido.errors import DeclarationError

GOOD = {
    "video": {
        "name": "promo",
        "languages": {"pt-BR": "por"},
        "folders": {"pt-BR": "pt"},
    },
    "source": {"kind": "scenes", "listing": "scenes.json"},
    "narration": {"script": "script.json", "takes": "narration"},
    "captions": {"translations": {"en": {"file": "en.json"}}},
    "instances": {"shio": {"url": "http://localhost:2710", "compose": "compose.yml"}},
    "record": {"step": [{"name": "scenes", "command": "npm run scenes"}]},
}


def test_a_complete_declaration_passes():
    assert check(GOOD) == []


def test_a_misspelled_key_is_refused_with_its_table_and_the_nearest_name():
    bad = {**GOOD, "narration": {"script": "s.json", "takes": "n", "tempoo": 1.1}}
    assert check(bad, "promo/video.toml") == [
        "promo/video.toml [narration]: unknown key tempoo; did you mean tempo?"
    ]
    assert check({**GOOD, "captons": {}}) == [
        "video.toml the top level: unknown key captons; did you mean captions?"
    ]


def test_keys_inside_maps_and_lists_are_checked_too():
    bad = json.loads(json.dumps(GOOD))
    bad["captions"]["translations"]["en"]["fiel"] = "x"
    bad["record"]["step"].append({"name": "down"})
    found = check(bad)
    assert (
        "video.toml [captions.translations.en]: unknown key fiel; did you mean file?"
        in found
    )
    assert "video.toml [record.step]: needs command" in found


def test_a_missing_key_and_a_source_without_what_its_kind_needs_are_refused():
    assert check({"video": {"name": "x"}}) == ["video.toml [video]: needs languages"]
    found = check({**GOOD, "source": {"kind": "chaptered", "folder": "rec"}})
    assert found == [
        "video.toml [source]: a chaptered source needs recording",
        "video.toml [source]: a chaptered source needs chapters",
    ]
    assert "it is one of chaptered" in check({**GOOD, "source": {"kind": "film"}})[0]


def test_the_build_refuses_a_bad_declaration_before_any_work(tmp_path):
    from urdido.build import Build

    toml = tmp_path / "video.toml"
    toml.write_text(
        '[video]\nname = "x"\nlanguages = { en = "eng" }\n[musc]\nbed = "a"\n',
        encoding="utf-8",
    )
    with pytest.raises(DeclarationError, match="unknown key musc; did you mean music"):
        Build(toml, SimpleNamespace(language="en", cut="full", vertical=False))
    assert not (tmp_path / "video").exists()


def test_the_cli_checks_a_file_and_prints_the_json_schema(tmp_path, capsys):
    toml = tmp_path / "video.toml"
    toml.write_text(
        '[video]\nname = "x"\nlanguages = { en = "eng" }\n', encoding="utf-8"
    )
    assert main([str(toml)]) == 0
    assert "passes" in capsys.readouterr().out
    toml.write_text('[video]\nname = "x"\nlanguage = "en"\n', encoding="utf-8")
    assert main([str(toml)]) == 1
    assert "did you mean languages" in capsys.readouterr().err
    assert main(["--schema"]) == 0
    schema = json.loads(capsys.readouterr().out)
    assert schema["required"] == ["video"]
    assert schema["properties"]["narration"]["additionalProperties"] is False
    assert schema["properties"]["roots"] == {
        "type": "object",
        "additionalProperties": {},
    }


def test_the_committed_reference_is_the_one_the_schema_writes_ur35():
    from urdido.declaration import PURPOSE, reference

    committed = (
        Path(__file__).resolve().parents[1] / "docs" / "specs" / "declaration.md"
    )
    assert committed.read_text(encoding="utf-8") == reference(), (
        "docs/specs/declaration.md is stale: urdido check --reference > it"
    )
    assert set(PURPOSE) == set(SCHEMA["keys"])  # every table says what it is for


def test_every_table_the_code_reads_is_in_the_schema():
    source = Path(__file__).resolve().parents[1] / "src" / "urdido"
    import re

    read = set()
    for file in source.rglob("*.py"):
        read |= set(
            re.findall(r'self\.decl(?:\.get\(|\[)"([a-z_]+)"', file.read_text("utf-8"))
        )
    assert read <= set(SCHEMA["keys"]), read - set(SCHEMA["keys"])
    assert json_schema()["type"] == "object"
