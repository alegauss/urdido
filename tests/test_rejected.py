"""UR6: a media entry a review rejected cannot come back into a cut."""

from types import SimpleNamespace

import pytest

from test_preflight import cut  # noqa: F401  (the preflight fixture)
from urdido import library
from urdido.build import Build
from urdido.preflight import PreflightRefused, illustrated
from urdido.sources.model import RecordingRefused

REASON = "hacker terminal with SECURITY ALERT; contradicts the line"


def test_a_whole_rejection_refuses_every_beat_and_cites_the_reason():
    asset = {"file": "code.mp4", "rejected": REASON}
    with pytest.raises(RecordingRefused, match="media code was rejected: hacker"):
        library.check_rejected({"asset": "code", "at": 12}, asset, 30)


def test_a_ranged_rejection_refuses_only_beats_that_overlap_it():
    asset = {"file": "code.mp4", "rejected": [{"reason": REASON, "start": 4, "end": 8}]}
    library.check_rejected({"asset": "code", "at": 0}, asset, 120)  # 0 s to 4 s
    library.check_rejected({"asset": "code", "at": 8}, asset, 60)
    with pytest.raises(RecordingRefused, match="between 4 s and 8 s"):
        library.check_rejected({"asset": "code", "at": 2}, asset, 90)  # 2 s to 5 s


def test_an_open_ended_range_runs_to_the_end_of_the_source():
    asset = {"file": "code.mp4", "rejected": {"reason": REASON, "start": 10}}
    library.check_rejected({"asset": "code", "at": 0}, asset, 300)
    with pytest.raises(RecordingRefused, match="between 10 s and inf s"):
        library.check_rejected({"asset": "code", "at": 30}, asset, 30)


def test_an_unrejected_asset_passes():
    library.check_rejected({"asset": "code"}, {"file": "code.mp4"}, 300)


@pytest.mark.parametrize(
    "declared",
    [
        "",
        [{"start": 1, "end": 2}],
        [{"reason": REASON, "start": 5, "end": 5}],
        [{"reason": REASON, "start": -1}],
        42,
    ],
)
def test_a_rejection_without_a_reason_or_a_valid_range_is_refused(declared):
    with pytest.raises(RecordingRefused):
        library.rejections({"rejected": declared})


def test_a_library_asset_may_carry_its_rejection(monkeypatch):
    asset = {"library": "lib.json", "candidate": "c", "range": "r", "rejected": REASON}
    catalogue = {
        "candidates": {
            "c": {
                "rights": {"status": "approved"},
                "ranges": [{"id": "r", "status": "accepted", "start": 0, "end": 9}],
                "file": "c.mp4",
                "sha256": "x",
                "kind": "video",
            }
        }
    }
    monkeypatch.setattr(library, "validate", lambda candidate: None)
    monkeypatch.setattr(library, "file_hash", lambda file: "x")
    resolved = library.resolve_asset(asset, ".", lambda path: catalogue)
    assert resolved["rejected"] == REASON


def test_preflight_names_the_rejected_beat_before_any_render(cut):  # noqa: F811
    (cut.folder / "code.mp4").write_bytes(b"probed by fixture")
    cut.story["media"] = {
        "code": {
            "file": "code.mp4",
            "license": "Own",
            "author": "Fixture",
            "url": "https://example.org",
            "rejected": REASON,
        }
    }
    cut.story["scenes"]["intro"] = [
        {
            "id": "back-again",
            "title": "Code",
            "source": "own",
            "asset": "code",
            "layout": "footage",
        }
    ]
    cut.write("story.json", cut.story)
    with pytest.raises(PreflightRefused) as failure:
        illustrated(Build(cut.declaration, SimpleNamespace(language="en")))
    assert any(
        f["field"] == "media.code.rejected"
        and f["beat"] == "back-again"
        and REASON in f["message"]
        for f in failure.value.findings
    )
