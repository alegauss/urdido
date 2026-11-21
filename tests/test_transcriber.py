"""Word times come through a transcriber seam, in the declared language (UR26)."""

import json

import pytest

from urdido.cache import file_hash
from urdido.narration_words import main, transcribe


class Fake:
    """A transcriber hearing the same words in every take, keeping what it was asked."""

    service = "fake transcriber"

    def __init__(self):
        self.asked = []

    def __call__(self, name, audio, language):
        self.asked.append((name, audio, language))
        return [
            {"text": "Olá", "start": 0.1, "end": 0.4},
            {"text": "mundo", "start": 0.5, "end": 0.9},
        ]


def test_a_take_is_transcribed_by_the_given_transcriber_and_bound_to_its_hash(tmp_path):
    audio = tmp_path / "intro.mp3"
    audio.write_bytes(b"take bytes")
    fake = Fake()
    assert transcribe(audio, "por", transcriber=fake) == "transcribed intro: 2 words"
    assert fake.asked == [("intro.mp3", b"take bytes", "por")]
    record = json.loads(audio.with_suffix(".words.json").read_text(encoding="utf-8"))
    assert record["sha256"] == file_hash(audio)
    assert record["service"] == "fake transcriber"
    assert transcribe(audio, "por", transcriber=fake) == "current intro"
    assert len(fake.asked) == 1  # a current record is never heard again


def test_there_is_no_default_language(tmp_path):
    audio = tmp_path / "intro.mp3"
    audio.write_bytes(b"x")
    with pytest.raises(ValueError, match="declared language"):
        transcribe(audio, "", transcriber=Fake())


def test_the_command_reads_takes_and_language_from_the_declaration(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.delenv("STORY_VIDEO_DIR", raising=False)
    script = {
        "intro": {"pt-BR": "Olá mundo"},
        "chapters": {},
        "outro": {"pt-BR": "Tchau"},
    }
    (tmp_path / "script.json").write_text(json.dumps(script), encoding="utf-8")
    for take in ("intro", "outro"):
        folder = tmp_path / "narration" / "pt-BR"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{take}.mp3").write_bytes(take.encode())
    toml = tmp_path / "video.toml"
    toml.write_text(
        '[video]\nname = "x"\nlanguages = { "pt-BR" = "por" }\n'
        '[narration]\nscript = "script.json"\ntakes = "narration"\n',
        encoding="utf-8",
    )
    fake = Fake()
    assert main([str(toml), "--language", "pt-BR"], transcriber=fake) == 0
    assert sorted((name, language) for name, _, language in fake.asked) == [
        ("intro.mp3", "por"),
        ("outro.mp3", "por"),
    ]
    assert "transcribed intro: 2 words" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main([str(toml)], transcriber=fake)  # --language is required: no default
