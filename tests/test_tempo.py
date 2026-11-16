"""VM72: a narration declared faster is heard from a stretched copy of each bought take."""
import json
import subprocess
from pathlib import Path

import pytest

from videomaker import media
from videomaker.cache import file_hash
from videomaker.keywords import word_record
from videomaker.narration import Takes, stretched

SCRIPT = {"voice": "v", "model": "m", "intro": {"pt-BR": "Oi"}, "chapters": {}, "outro": {"pt-BR": "Tchau"}}


def take(folder: Path, seconds=2.0) -> Path:
    file = folder / "pt-BR" / "intro.mp3"
    file.parent.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=300:duration={seconds}",
                    "-c:a", "libmp3lame", str(file)], check=True)
    words = [{"text": "Oi", "start": 0.2, "end": 0.8}, {"text": "gente", "start": 1.0, "end": 1.9}]
    file.with_suffix(".words.json").write_text(json.dumps({"sha256": file_hash(file), "words": words}), "utf-8")
    return file


def test_stretched_take_is_shorter_and_its_words_follow(tmp_path):
    source = take(tmp_path)
    out = Path(stretched(str(source), 1.25))
    assert out.parent.name == "tempo-1.25"
    assert media.seconds(str(out)) == pytest.approx(media.seconds(str(source)) / 1.25, abs=0.08)
    words = word_record(out)
    assert [w["start"] for w in words] == [0.16, 0.8]
    assert [w["end"] for w in words] == [0.64, 1.52]


def test_stretched_take_is_rebuilt_when_the_bought_take_changes(tmp_path):
    source = take(tmp_path)
    first = file_hash(stretched(str(source), 1.2))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=500:duration=3",
                    "-c:a", "libmp3lame", str(source)], check=True)
    assert file_hash(stretched(str(source), 1.2)) != first


def test_takes_hear_the_stretched_copy_and_buying_keeps_the_source(tmp_path):
    source = take(tmp_path)
    assert Takes(SCRIPT, str(tmp_path)).take_file("pt-BR", "intro") == str(source)
    faster = Takes(SCRIPT, str(tmp_path), 1.15)
    assert Path(faster.take_file("pt-BR", "intro")).parent.name == "tempo-1.15"
    assert faster.source_file("pt-BR", "intro") == str(source)


def test_a_stretched_copy_is_current_exactly_when_its_source_is(tmp_path):
    source = take(tmp_path)
    prov = {"artefact": {"sha256": file_hash(source)}, "prompt": "Oi", "details": {"voice": "v"},
            "engine": {"model": "m"}}
    Path(f"{source}.prov.json").write_text(json.dumps(prov), "utf-8")
    faster = Takes(SCRIPT, str(tmp_path), 1.15)
    heard = faster.take_file("pt-BR", "intro")
    assert faster.current(heard, "pt-BR", "Oi")
    assert not faster.current(heard, "pt-BR", "Olá")


def test_fixed_beat_seconds_shrink_with_the_tempo():
    from videomaker.sources.illustrated import paced

    beats = [{"seconds": 2.3, "asset": "a"}, {"asset": "b"}]
    assert paced(beats, 1.0) is beats
    assert paced(beats, 1.15) == [{"seconds": 2.0, "asset": "a"}, {"asset": "b"}]
    assert beats[0]["seconds"] == 2.3


def test_an_absurd_tempo_is_refused(tmp_path):
    with pytest.raises(ValueError, match="tempo"):
        Takes(SCRIPT, str(tmp_path), 3)
