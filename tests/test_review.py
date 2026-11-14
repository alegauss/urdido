"""VM41: review labels follow actual timed words rather than take filenames."""
import hashlib
import json

import pytest

from videomaker import review
from videomaker.sources.model import RecordingRefused


def inputs(tmp_path):
    audio = tmp_path / "intro.mp3"
    audio.write_bytes(b"audio")
    audio.with_suffix(".words.json").write_text(json.dumps({
        "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
        "words": [{"text": "first", "start": 0, "end": 1},
                  {"text": "second", "start": 1, "end": 2}]}), encoding="utf-8")
    placed = [{"file": str(audio), "at": 2.4, "length": 2, "text": "first second"}]
    document = {"scenes": {"intro": [{"title": "<person>", "layout": "footage", "asset": "a", "at": 5},
                                         {"title": "card"}]},
                "media": {"a": {"file": "source.mp4", "people": ["identity unverified"], "url": "https://example.test"}}}
    edit = {"beats": [{"beat": "intro-0", "at": 0, "seconds": 1.4},
                      {"beat": "intro-1", "at": 1.4, "seconds": 1.5}]}
    return document, edit, placed


def test_words_overlap_beats_with_opening_offset_vm41(tmp_path):
    document, edit, placed = inputs(tmp_path)
    rows = review.rows(document, edit, placed, [{"at": 3.5, "end": 4, "show": "second"}], opening=2)
    assert rows[0]["spoken"] == "first"
    assert rows[1]["spoken"] == "second"
    assert rows[0]["source_start"] == 5
    assert rows[0]["source_end"] == 6.4
    assert rows[0]["tags"]["people"] == ["identity unverified"]
    assert rows[1]["highlights"] == ["second"]
    assert rows[0]["captions"]


@pytest.mark.parametrize("missing", [True, False])
def test_unverified_word_times_refused_before_images_vm41(tmp_path, missing):
    document, edit, placed = inputs(tmp_path)
    audio = tmp_path / "intro.mp3"
    if missing:
        audio.with_suffix(".words.json").unlink()
    else:
        audio.write_bytes(b"retake")
    with pytest.raises(RecordingRefused, match="word times"):
        review.sheet(document, edit, placed, [], tmp_path, tmp_path / "parts", tmp_path)
    assert not (tmp_path / "review").exists()


def test_sheet_extracts_source_midpoint_draws_card_and_escapes_labels_vm41(tmp_path, monkeypatch):
    document, edit, placed = inputs(tmp_path)
    parts = tmp_path / "parts"
    (parts / "illustrated").mkdir(parents=True)
    (parts / "illustrated/intro-1.html").write_text("card", encoding="utf-8")
    calls = []

    def extract(args):
        calls.append(args)
        from pathlib import Path
        Path(args[-1]).write_bytes(b"image")

    def draw(pages, frame, out):
        assert pages == {"intro-1": "card"}
        (tmp_path / "review/intro-1.png").write_bytes(b"card")

    monkeypatch.setattr(review.media, "ffmpeg", extract)
    monkeypatch.setattr(review, "render", draw)
    file = review.sheet(document, edit, placed, [], tmp_path, parts, tmp_path, opening=2)
    assert calls[0][1] == "5.7"
    text = file.read_text(encoding="utf-8")
    assert "&lt;person&gt;" in text and "<person>" not in text
    assert "Source midpoint" in text and "Production card" in text
    data = json.loads((file.parent / "review.json").read_text())
    assert all((file.parent / row["image"]).is_file() for row in data)


def test_picture_preview_does_not_seek_past_single_image_vm41(tmp_path, monkeypatch):
    import shutil
    from PIL import Image

    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required")
    document, edit, placed = inputs(tmp_path)
    document["scenes"]["intro"] = [{"title": "portrait", "layout": "picture", "asset": "a"}]
    document["media"]["a"]["file"] = "source.jpg"
    edit["beats"] = edit["beats"][:1]
    Image.new("RGB", (64, 64), "red").save(tmp_path / "source.jpg")
    file = review.sheet(document, edit, placed, [], tmp_path, tmp_path / "parts", tmp_path)
    assert (file.parent / "intro-0.png").is_file()
