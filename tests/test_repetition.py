"""VM59: overlapping intervals and declared activity budgets, independently of filenames."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_preflight import cut  # noqa: F401  (the preflight fixture)
from urdido.repetition import enforce, inspect
from urdido.sources.illustrated import validate
from urdido.sources.model import RecordingRefused


def story(tmp_path, shots):
    media = {}
    beats, audit, clock = [], [], 0
    for i, (key, at, duration, categories) in enumerate(shots):
        if key is not None:
            media.setdefault(key, {"file": f"{key}.mp4", "license": "Own", "author": "Fixture", "url": "https://example.org"})
            (tmp_path / f"{key}.mp4").write_bytes(key.encode())
        beats.append({"id": f"b{i}", "title": f"Shot {i}", "source": "own", "layout": "footage" if key else "date",
                      "asset": key, "at": at, "categories": categories})
        audit.append({"beat": f"intro-{i}", "at": clock, "seconds": duration})
        clock += duration
    return {"sources": {"own": {"label": "Fixture", "url": "https://example.org"}}, "media": media,
            "scenes": {"intro": beats}}, {"beats": audit}


def test_copied_source_aliases_share_overlap_time_adjacency_and_gap_budgets(tmp_path):
    document, edit = story(tmp_path, [("a", 0, 2, []), ("copy", 1, 2, [])])
    (tmp_path / "copy.mp4").write_bytes(b"a")
    document["repetition"] = {"action": "error", "max_overlap_seconds": 0, "max_source_seconds": 3,
                              "max_adjacent": 1, "min_gap_seconds": 5}
    report = inspect(document, edit, tmp_path)
    assert {f["rule"] for f in report["findings"]} == {"overlap", "source_seconds", "adjacent", "gap"}
    assert report["overlaps"][0]["source_start"] == 1 and report["overlaps"][0]["source_end"] == 2
    assert report["sources"][0]["aliases"] == ["a", "copy"]
    with pytest.raises(RecordingRefused, match="b0, b1"):
        enforce(report)
    document["repetition"]["sources"] = {"a": {"max_source_seconds": 5}}
    assert not any(f["rule"] == "source_seconds" for f in inspect(document, edit, tmp_path)["findings"])
    document["repetition"]["sources"]["copy"] = {"max_source_seconds": 4}
    with pytest.raises(ValueError, match="conflicting"):
        inspect(document, edit, tmp_path)


def test_distinct_navigation_ranges_replace_legacy_file_counts_explicitly(tmp_path):
    document, edit = story(tmp_path, [("nav", n * 3, 3, ["navigation"]) for n in range(4)])
    document["max_asset_uses"] = 1
    voices = SimpleNamespace(lines={"intro": {}}, takes=lambda *args, **kwargs: [SimpleNamespace(length=11.1)])
    with pytest.raises(RecordingRefused, match="reuse exceeds"):
        validate(document, voices, "en")
    document["repetition"] = {"replace_file_counts": True, "max_overlap_seconds": 0, "action": "error"}
    validate(document, voices, "en")
    report = inspect(document, edit, tmp_path)
    assert report["overlaps"] == [] and report["findings"] == []
    assert report["sources"][0]["screen_seconds"] == 12
    enforce(report)


def test_a_budget_on_an_unused_alias_still_governs_the_selected_copy(tmp_path):
    document, edit = story(tmp_path, [("original", 0, 2, []), ("copy", 1, 2, [])])
    (tmp_path / "copy.mp4").write_bytes(b"original")
    document["scenes"]["intro"][0]["asset"] = "copy"
    document["repetition"] = {"action": "error", "sources": {"original": {"max_source_seconds": 3}}}
    report = inspect(document, edit, tmp_path)
    assert report["sources"][0]["aliases"] == ["copy", "original"]
    assert report["findings"][0]["rule"] == "source_seconds"
    with pytest.raises(RecordingRefused):
        enforce(report)


def test_different_files_can_exceed_a_declared_activity_share_and_exceptions_stay_visible(tmp_path):
    document, edit = story(tmp_path, [("one", 0, 2, ["typing"]), ("two", 0, 2, ["typing"]), (None, 0, 2, [])])
    document["repetition"] = {"action": "warn", "max_category_share": {"typing": .5}}
    report = inspect(document, edit, tmp_path)
    assert report["overlaps"] == []
    assert report["categories"]["typing"]["share"] == pytest.approx(2 / 3)
    with pytest.warns(UserWarning, match="typing"):
        enforce(report)
    document["repetition"].update(action="error", exceptions=[{
        "rule": "category_share", "beats": ["b0", "b1"], "reason": "Continuous keyboard tutorial"}])
    report = inspect(document, edit, tmp_path)
    enforce(report)
    assert report["findings"][0]["exception"] == "Continuous keyboard tutorial"
    document["scenes"]["intro"][2]["categories"] = ["typing"]
    assert inspect(document, edit, tmp_path)["categories"]["typing"]["share"] == 1
    with pytest.raises(RecordingRefused):
        enforce(inspect(document, edit, tmp_path))  # the exception did not include the card
    document["repetition"]["exceptions"][0]["reason"] = ""
    with pytest.raises(ValueError, match="explicit reason"):
        inspect(document, edit, tmp_path)


def test_declared_original_source_offsets_find_repeated_intervals_across_different_exports(tmp_path):
    document, edit = story(tmp_path, [("one", 0, 3, []), ("two", 0, 3, [])])
    document["media"]["one"].update(source_id="declared-talk", source_offset=100)
    document["media"]["two"].update(source_id="declared-talk", source_offset=102)
    document["repetition"] = {"max_overlap_seconds": 0}
    report = inspect(document, edit, tmp_path)
    assert report["overlaps"][0]["basis"] == "declared source"
    assert report["overlaps"][0]["source_start"] == 102 and report["overlaps"][0]["seconds"] == 1
    # Different declared IDs/offsets cannot disguise copies of the same source bytes.
    (tmp_path / "two.mp4").write_bytes(b"one")
    document["media"]["two"].update(source_id="different-name", source_offset=999)
    assert inspect(document, edit, tmp_path)["overlaps"][0]["seconds"] == 3


def test_long_adjacent_runs_name_every_affected_beat_and_unclassified_media_is_explicit(tmp_path):
    document, edit = story(tmp_path, [("same", n, 1, []) for n in range(4)])
    document["repetition"] = {"max_adjacent": 1}
    report = inspect(document, edit, tmp_path)
    assert report["findings"][0]["beats"] == ["b0", "b1", "b2", "b3"]
    assert report["unclassified_media_seconds"] == 4


def test_repetition_failure_precedes_renderer_and_encoder_for_plan_and_full_build(cut, monkeypatch):
    from urdido import media
    from urdido.build import main
    from urdido.preflight import PreflightRefused

    source = cut.folder / "source.mp4"
    source.write_bytes(b"same source")
    monkeypatch.setattr(media, "seconds", lambda file: 4 if Path(file) == source else 3)
    cut.story["media"] = {"a": {"file": "source.mp4", "author": "Fixture", "url": "https://example.org", "license": "Own"}}
    for values in cut.story["scenes"].values():
        values[0].update(asset="a", layout="footage")
    cut.story["repetition"] = {"action": "error", "max_overlap_seconds": 0}
    cut.write("story.json", cut.story)
    for extra in ([], ["--plan"]):
        with pytest.raises(PreflightRefused, match="repeated source interval"):
            main([str(cut.declaration), "--language", "en", *extra])
    assert not (cut.folder / "video/parts/illustrated").exists()
