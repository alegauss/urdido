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


def test_a_typo_in_the_cards_or_highlights_is_refused_ur47(tmp_path):
    from urdido.declaration import check_side_files

    (tmp_path / "cards.json").write_text(
        json.dumps({"theme": {"colours": {}, "fonts": {"dir": "f"}}, "words": {}}),
        encoding="utf-8",
    )
    (tmp_path / "highlights.json").write_text(
        json.dumps({"style": {"font": "A"}, "lines": {"intro": [{"shwo": "Git"}]}}),
        encoding="utf-8",
    )
    decl = {
        "cards": {"declaration": "cards.json"},
        "highlights": {"declaration": "highlights.json"},
    }
    found = check_side_files(decl, lambda declared: tmp_path / declared)
    assert any("[theme]: unknown key colours; did you mean colors?" in f for f in found)
    assert any(
        "[lines.intro]: unknown key shwo; did you mean show?" in f for f in found
    )
    assert any("[lines.intro]: needs show" in f for f in found)


def test_a_translation_table_takes_lists_of_sentences_and_a_note_ur47(tmp_path):
    from urdido.declaration import check_side_files

    table = {"_": "one sentence per spoken sentence", "intro": ["Hi."], "outro": "Bye."}
    (tmp_path / "en.json").write_text(json.dumps(table), encoding="utf-8")
    found = check_side_files(GOOD, lambda declared: tmp_path / declared)
    assert len(found) == 1
    assert found[0].endswith("en.json [outro]: is 'Bye.', and it takes a array")


def test_one_shorts_table_declares_one_cutter_ur48(tmp_path):
    from urdido import shorts
    from urdido.declaration import reference, shorts_cutter

    selection = {"declaration": "demo/shorts.json"}
    feed = {"plan": "p.json", "cut": [{"n": 1}]}
    assert check({**GOOD, "shorts": selection}) == []
    assert check({**GOOD, "shorts": feed}) == []
    assert check({**GOOD, "shorts": {**selection, **feed}}) == [
        "video.toml [shorts]: declaration is a scenes build's selection "
        "(--cut short:<c>) and plan, cut belong to urdido shorts; "
        "one [shorts] table declares one cutter"
    ]
    assert shorts_cutter(selection) == "selection"
    assert shorts_cutter(feed) == "urdido shorts"
    assert "## Shorts cutters" in reference()

    toml = tmp_path / "video.toml"
    toml.write_text('[shorts]\ndeclaration = "demo/shorts.json"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="declares a scenes selection"):
        shorts.declared(toml)


def test_an_absent_key_reads_the_default_the_schema_holds_ur47():
    from urdido.audio import mix
    from urdido.declaration import DEFAULTS, reference, setting

    assert setting(GOOD, "narration", "tempo") == 1.0
    assert setting({**GOOD, "narration": {"tempo": 1.1}}, "narration", "tempo") == 1.1
    assert setting(GOOD, "video", "frame") == [1920, 1080]
    assert setting(GOOD, "narration", "script") == "script.json"
    assert setting({}, "cards", "channel") is None  # no default: absent stays absent
    assert "`tempo`: a number, 1.0 if absent" in reference()
    assert json_schema()["properties"]["qa"]["properties"]["flash_refuse"] == {
        "type": "number",
        "default": 40.0,
    }
    # The mix's own dataclasses hold the same numbers the schema states.
    loudness, duck, bed = mix.Loudness(), mix.Duck(), mix.Bed("bed.mp3")
    assert {k: getattr(loudness, k) for k in DEFAULTS["audio"]} == DEFAULTS["audio"]
    assert duck.between == DEFAULTS["music"]["between"]
    assert duck.ramp == DEFAULTS["music"]["ramp"]
    assert bed.reference == DEFAULTS["music"]["reference"]


def test_a_value_of_the_wrong_type_is_refused_ur47():
    bad = {
        **GOOD,
        "narration": {"script": "s.json", "takes": "n", "tempo": "fast"},
        "cuts": {"teaser": "yes"},
        "audio": {"peak": True},
    }
    found = check(bad)
    assert "video.toml [narration.tempo]: is 'fast', and it takes a number" in found
    assert "video.toml [cuts.teaser]: is 'yes', and it takes a boolean" in found
    assert (
        "video.toml [audio.peak]: is True, and it takes a number" in found
    )  # not a bool
    assert check({**GOOD, "audio": {"peak": -1, "target": -14.0}}) == []


def test_a_typo_inside_the_script_or_the_storyboard_is_refused_ur47(tmp_path, capsys):
    toml = tmp_path / "video.toml"
    toml.write_text(
        '[video]\nname = "x"\nlanguages = { en = "eng" }\n'
        '[source]\nkind = "illustrated"\ndeclaration = "story.json"\n'
        '[narration]\nscript = "script.json"\ntakes = "narration"\n',
        encoding="utf-8",
    )
    script = {
        "intro": {"en": "Hi"},
        "chapters": {"1": {"titel": {"en": "One"}}},
        "outro": {"en": "Bye"},
    }
    (tmp_path / "script.json").write_text(json.dumps(script), encoding="utf-8")
    story = {"scenes": {"intro": [{"title": "A", "captoin": "x"}]}, "media": {}}
    (tmp_path / "story.json").write_text(json.dumps(story), encoding="utf-8")
    assert main([str(toml)]) == 1
    err = capsys.readouterr().err
    assert "script.json [chapters.1]: unknown key titel; did you mean title?" in err
    assert (
        "story.json [scenes.intro]: unknown key captoin; did you mean caption?" in err
    )

    from urdido.build import Build

    with pytest.raises(DeclarationError, match="a side file is refused"):
        Build(toml, SimpleNamespace(language="en", cut="full", vertical=False))


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
