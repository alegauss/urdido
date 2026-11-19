"""VM43: competing captions fail, unverified identities remain human review."""
import pytest

from urdido.labels import check
from urdido.sources.model import RecordingRefused


def fixture():
    document = {"scenes": {"intro": [{"title": "WordPress 0.71", "asset": "stock", "layout": "footage",
                                        "overlay_seconds": 1}, {"title": "next", "caption": "", "asset": "stage"}]},
                "media": {"stock": {"people": []}, "stage": {"events": ["WordCamp Brasil"]}}}
    edit = {"beats": [{"beat": "intro-0", "at": 0, "seconds": 3},
                      {"beat": "intro-1", "at": 3, "seconds": 3}]}
    return document, edit


def test_overlapping_caption_rejected_with_both_labels_and_time_vm43():
    document, edit = fixture()
    with pytest.raises(RecordingRefused, match="intro-0.*WordPress 0.7.*WordPress 0.71.*2.500"):
        check(document, edit, [{"at": 2.5, "end": 2.9, "show": "WordPress 0.7"}], opening=2)


def test_highlight_at_caption_disappearance_is_allowed_vm43():
    document, edit = fixture()
    assert check(document, edit, [{"at": 3, "end": 4, "show": "WordPress 0.7"}], opening=2) == []


def test_person_warning_cannot_be_silenced_by_unrelated_stock_vm43():
    document, edit = fixture()
    with pytest.warns(UserWarning, match="Michel.*not verified"):
        notes = check(document, edit, [{"at": 1.5, "end": 2, "show": "Michel", "person": "Michel Valdrighi"}])
    assert len(notes) == 1
    document["media"]["stock"]["people"] = ["Michel Valdrighi"]
    assert check(document, edit, [{"at": 1.5, "end": 2, "show": "Michel", "person": "Michel Valdrighi"}]) == []


def test_event_spilling_to_another_beat_warns_vm43():
    document, edit = fixture()
    document["entities"] = {"WordCamp Brasil": "event"}
    with pytest.warns(UserWarning) as notes:
        check(document, edit, [{"at": 2, "end": 4, "show": "WordCamp Brasil"}])
    assert len(notes) == 2  # Stock does not depict the event, and the highlight crosses a cut.
