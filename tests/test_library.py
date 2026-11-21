"""VM58: review declarations cannot silently approve stale, rejected or uncertain media."""
import copy
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from urdido import library
from urdido.cache import file_hash
from urdido.sources.model import RecordingRefused
from test_preflight import cut


@pytest.fixture
def candidate(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg and ffprobe required")
    source = tmp_path / "Matt.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=blue:s=64x64:r=30:d=4", "-c:v", "libx264", str(source)], check=True)
    Path(str(source) + ".prov.json").write_text(json.dumps({"artefact": {"sha256": file_hash(source)},
        "source_page": "https://example.org/source", "author": "Fixture author", "licence": "Own fixture", "kind": "fetch", "produced_at": "2026-11-01T12:00:00Z"}))
    catalogue = tmp_path / "library.json"
    record = library.imported(source, {"title": "Fixture video", "people": ["Unconfirmed filename identity"]}, catalogue)
    library.update(catalogue, "new", lambda data: library.add(data, "fixture", record))
    return SimpleNamespace(file=source, catalogue=catalogue, record=record)


def approve(candidate, *, start=.5, end=2.5):
    review = {"reviewer": "Test fixture reviewer", "date": "2026-11-14", "reason": "Synthetic test decision",
              "rights": {"status": "approved"}, "ranges": [
                  {"id": "usable", "status": "accepted", "start": start, "end": end, "people": ["Confirmed fixture actor"], "events": ["Fixture event"]}]}
    library.update(candidate.catalogue, file_hash(candidate.catalogue), lambda data: library.review(data, "fixture", review))


def reference(candidate, range="usable"):
    return {"library": str(candidate.catalogue), "candidate": "fixture", "range": range}


def test_import_preserves_provenance_without_approving_identity_rights_or_ranges(candidate):
    record = candidate.record
    assert record["rights"] == {"status": "unknown"} and record["ranges"] == []
    assert record["url"] == "https://example.org/source" and record["author"] == "Fixture author"
    assert record["measurements"]["width"] == 64 and record["measurements"]["fps"] == 30
    assert record["retrieved_at"] == "2026-11-01T12:00:00Z"
    assert "people" not in record
    with pytest.raises(RecordingRefused, match="rights are unknown"):
        library.resolve_asset(reference(candidate), candidate.catalogue.parent)


def test_selection_inherits_confirmed_metadata_and_stays_within_accepted_range(candidate):
    approve(candidate)
    resolved = library.resolve_asset(reference(candidate), candidate.catalogue.parent)
    assert resolved["people"] == ["Confirmed fixture actor"]
    assert resolved["license"] == "Own fixture" and resolved["title"] == "Fixture video"
    assert library.source_start({}, resolved) == .5
    library.check_range({"layout": "footage"}, resolved, 60)
    with pytest.raises(RecordingRefused, match="exceeds"):
        library.check_range({"layout": "footage"}, resolved, 61)
    with pytest.raises(RecordingRefused, match="only visual"):
        library.resolve_asset({**reference(candidate), "people": ["Unreviewed override"]}, candidate.catalogue.parent)
    candidate.file.write_bytes(b"changed source")
    with pytest.raises(RecordingRefused, match="media changed"):
        library.resolve_asset(reference(candidate), candidate.catalogue.parent)


def test_rejected_ranges_persist_and_conflicting_decisions_are_refused(candidate):
    approve(candidate)
    payload = {"reviewer": "Test fixture reviewer", "date": "2026-11-14", "reason": "Blurred test range",
               "ranges": [{"id": "bad", "start": 0, "end": 4, "status": "rejected"}]}
    library.update(candidate.catalogue, file_hash(candidate.catalogue), lambda data: library.review(data, "fixture", payload))
    with pytest.raises(RecordingRefused, match="accepted library range"):
        library.resolve_asset(reference(candidate, "bad"), candidate.catalogue.parent)
    value = library.read(candidate.catalogue)["candidates"]["fixture"]
    assert value["ranges"][0]["reason"] == "Blurred test range"
    assert value["reviews"][-1]["previous_ranges"][0]["id"] == "usable"
    conflict = copy.deepcopy(value)
    conflict["ranges"].append({**conflict["ranges"][0], "id": "contradiction", "status": "accepted"})
    with pytest.raises(ValueError, match="overlap"):
        library.validate(conflict)


def test_atomic_updates_refuse_stale_edits_clean_locks_and_reset_changed_rights(candidate):
    old = file_hash(candidate.catalogue)
    approve(candidate)
    current = candidate.catalogue.read_bytes()
    with pytest.raises(ValueError, match="stale library"):
        library.update(candidate.catalogue, old, lambda data: data.clear())
    assert candidate.catalogue.read_bytes() == current
    assert not candidate.catalogue.with_name("library.json.edit.lock").exists()
    record = {"reviewer": "Test reviewer", "date": "2026-11-14", "reason": "Metadata correction", "metadata": {"license": "Uncertain replacement"}}
    library.update(candidate.catalogue, file_hash(candidate.catalogue), lambda data: library.review(data, "fixture", record))
    assert library.read(candidate.catalogue)["candidates"]["fixture"]["rights"]["status"] == "unknown"


def test_library_binding_is_validated_before_render_and_catalogue_hash_is_recorded(candidate, cut, monkeypatch):
    from urdido.build import Build
    from urdido.preflight import illustrated
    from urdido import media

    monkeypatch.setattr(media, "seconds", lambda file: 4.0 if Path(file) == candidate.file else 3.0)
    approve(candidate, start=.1, end=4)
    cut.story["media"] = {"selected": reference(candidate)}
    for beats in cut.story["scenes"].values():
        beats[0].update(layout="footage", asset="selected")
    cut.write("story.json", cut.story)
    build = Build(cut.declaration, SimpleNamespace(language="en"))
    _, _, document = illustrated(build)
    assert document["scenes"]["intro"][0]["at"] == .1
    assert document["media"]["selected"]["author"] == "Fixture author"
    assert candidate.catalogue.resolve() in build.input_hashes
    approve(candidate, start=0, end=1)
    with pytest.raises(RecordingRefused, match="exceeds its accepted"):
        illustrated(Build(cut.declaration, SimpleNamespace(language="en")))
    with pytest.raises(RecordingRefused, match="changed during build"):
        build.write_inputs()


def test_preview_delegates_register_and_frames_and_sheet_does_not_edit_reviews(candidate, tmp_path, monkeypatch):
    calls = []
    def delegate(operation, root, **parameters):
        calls.append((operation, parameters))
        if operation == "reference.frames":
            folder = Path(root) / parameters["out"]
            folder.mkdir(parents=True)
            (folder / "sheet.png").write_bytes(b"fixture image")
            (folder / "frames.json").write_text(json.dumps({"sheets": ["sheet.png"]}))
        return {"ok": True}
    monkeypatch.setattr(library, "delegate", delegate)
    assert library.main(["preview", str(candidate.catalogue), "--id", "fixture", "--expected-sha256", file_hash(candidate.catalogue),
                         "--root", str(tmp_path), "--out", "preview"]) == 0
    assert [c[0] for c in calls] == ["reference.register", "reference.frames"]
    before = candidate.catalogue.read_bytes()
    html = library.sheet(candidate.catalogue, tmp_path / "review.html").read_text("utf-8")
    assert "unknown" in html and "<video" in html and "sheet.png" in html
    assert candidate.catalogue.read_bytes() == before
    assert library.read(candidate.catalogue)["candidates"]["fixture"]["ranges"] == []


def test_picture_review_applies_to_whole_image_and_filename_does_not_confirm_identity(tmp_path):
    from PIL import Image

    photo = tmp_path / "Matt.png"
    Image.new("RGB", (16, 16), "blue").save(photo)
    catalogue = tmp_path / "photos.json"
    record = library.imported(photo, {"title": "Fixture", "author": "Test", "license": "Own", "url": "https://example.org"}, catalogue)
    assert record["kind"] == "picture" and record["retrieved_at"] is None
    library.update(catalogue, "new", lambda data: library.add(data, "photo", record))
    review = {"reviewer": "Test reviewer", "date": "2026-11-14", "reason": "Fixture", "rights": {"status": "approved"},
              "ranges": [{"id": "whole", "whole": True, "status": "accepted"}]}
    library.update(catalogue, file_hash(catalogue), lambda data: library.review(data, "photo", review))
    asset = library.resolve_asset({"library": str(catalogue), "candidate": "photo", "range": "whole"}, tmp_path)
    assert asset["people"] == []
    library.check_range({"layout": "picture"}, asset, 120)


def test_delegate_surfaces_refusal_and_boolean_flags(monkeypatch, tmp_path):
    from urdido.providers import polyweave as provider

    seen = []
    def run(args, **kwargs):
        seen.extend(args)
        return SimpleNamespace(returncode=0, stdout='{"ok":false,"why":"source refused"}', stderr="")
    monkeypatch.setattr(provider, "RUN", run)
    with pytest.raises(RuntimeError, match="source refused"):
        library.delegate("provenance.credits", tmp_path, all=True)
    assert "--all" in seen and "True" not in seen


def test_fetch_uses_stock_adapter_and_retains_only_matching_credit_record(candidate, tmp_path, monkeypatch):
    calls = []
    def delegated(operation, root, **parameters):
        calls.append(operation)
        if operation == "stock.fetch":
            target = Path(root) / parameters["out"]
            shutil.copyfile(candidate.file, target)
            shutil.copyfile(Path(str(candidate.file) + ".prov.json"), Path(str(target) + ".prov.json"))
            return {"ok": True, "file": parameters["out"]}
        assert parameters["all"] is True
        return {"artefacts": [{"file": "download.mp4", "licence": "Own fixture"}, {"file": "unrelated.mp4"}]}
    monkeypatch.setattr(library, "delegate", delegated)
    args = ["fetch", str(candidate.catalogue), "--id", "download", "--expected-sha256", file_hash(candidate.catalogue),
            "--stock-id", "1", "--root", str(tmp_path), "--out", "download.mp4"]
    assert library.main(args) == 0
    assert calls == ["stock.fetch", "provenance.credits"]
    record = library.read(candidate.catalogue)["candidates"]["download"]
    assert record["rights"]["status"] == "unknown"
    assert record["imported_metadata"]["credits_record"] == [{"file": "download.mp4", "licence": "Own fixture"}]
    with pytest.raises(ValueError, match="stale library"):
        library.main(args)
    assert calls == ["stock.fetch", "provenance.credits"]
