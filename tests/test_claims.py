"""VM64: evidence is declared, approval is human, freshness is input-bound."""
import copy
import json
from datetime import date, timedelta

import pytest

from urdido import cache, claims
from urdido.narration import Takes
from urdido.sources.model import RecordingRefused
from test_preflight import cut


@pytest.fixture
def evidence(cut):
    data = {"version": 1, "claims": [{"id": "greeting", "kind": "historical", "language": "en", "take": "intro",
        "text": "Hello <script>unsafe</script>", "anchor": "Hello", "evidence": [{"source": "own", "note": "Explicit supporting note",
        "event_date": "2003-05-27", "published_at": "2021-01-08", "retrieved_at": date.today().isoformat()}]}]}
    cut.write("claims.json", data)
    takes = Takes(cut.script, str(cut.folder / "narration"))
    def inspect():
        return claims.inspect(claims.read(cut.folder / "claims.json"), takes, "en", cut.story, cut.folder)
    def review(**fields):
        return {"status": "approved", "reviewer": "Owner", "date": date.today().isoformat(), "reason": "Reviewed the supplied evidence",
                "fingerprint": inspect()["claims"][0]["fingerprint"], **fields}
    return cut, data, takes, inspect, review


def test_url_is_not_approval_and_dates_remain_distinct_in_review_view(evidence):
    cut, data, takes, inspect, review = evidence
    report = inspect()
    assert report["claims"][0]["effective_status"] == "unreviewed"
    assert claims.citations(report) == []
    claims.publish(report, cut.folder / "review.html")
    page = (cut.folder / "review.html").read_text("utf-8")
    assert "&lt;script&gt;unsafe&lt;/script&gt;" in page and "<script>unsafe" not in page
    assert "2003-05-27" in page and "2021-01-08" in page
    assert json.loads((cut.folder / "review.json").read_text())["coverage"] == "declared claims only"


def test_review_binds_to_claim_narration_and_evidence_and_preserves_history(evidence):
    cut, data, takes, inspect, review = evidence
    file = cut.folder / "claims.json"
    claims.record_review(file, cache.file_hash(file), "greeting", inspect(), review())
    approved = inspect()
    assert approved["claims"][0]["effective_status"] == "approved"
    assert claims.citations(approved)[0]["url"] == "https://example.org"
    cut.story["sources"]["own"]["url"] = "https://example.org/changed"
    assert inspect()["claims"][0]["effective_status"] == "needs_review"
    cut.story["sources"]["own"]["url"] = "https://example.org"
    takes.script["intro"]["en"] = "Hello again"
    assert "stale" in " ".join(inspect()["claims"][0]["review_reasons"])
    takes.script["intro"]["en"] = "Hello"
    changed = claims.read(file)
    changed["claims"][0]["text"] = "Changed assertion"
    cut.write("claims.json", changed)
    assert inspect()["claims"][0]["effective_status"] == "needs_review"
    claims.record_review(file, cache.file_hash(file), "greeting", inspect(), review(status="rejected"))
    assert inspect()["claims"][0]["effective_status"] == "rejected"
    assert len(claims.read(file)["claims"][0]["reviews"]) == 2


def test_statistic_requires_deadline_and_expired_review_is_not_published(evidence):
    cut, data, takes, inspect, review = evidence
    data["claims"][0]["kind"] = "statistic"
    cut.write("claims.json", data)
    file = cut.folder / "claims.json"
    with pytest.raises(ValueError, match="deadline"):
        claims.record_review(file, cache.file_hash(file), "greeting", inspect(), review())
    claims.record_review(file, cache.file_hash(file), "greeting", inspect(), review(valid_until=date.today().isoformat()))
    future = claims.inspect(claims.read(file), takes, "en", cut.story, cut.folder, today=date.today() + timedelta(days=1))
    assert future["claims"][0]["effective_status"] == "needs_review"
    assert claims.citations(future) == []


def test_missing_retrieval_date_or_anchor_cannot_be_approved(evidence):
    cut, data, takes, inspect, review = evidence
    file = cut.folder / "claims.json"
    for field, value in (("anchor", "not narrated"), ("evidence", [{"source": "own", "note": "No retrieval date"}])):
        changed = copy.deepcopy(data)
        changed["claims"][0][field] = value
        cut.write("claims.json", changed)
        with pytest.raises(ValueError, match="approval needs"):
            claims.record_review(file, cache.file_hash(file), "greeting", inspect(), review())
    data["claims"][0]["evidence"][0]["url"] = "javascript:alert(1)"
    cut.write("claims.json", data)
    with pytest.raises(ValueError, match="HTTP"):
        inspect()


def test_evidence_snapshot_and_illustrative_media_changes_invalidate_review(evidence):
    cut, data, takes, inspect, review = evidence
    (cut.folder / "source.txt").write_text("Evidence snapshot")
    (cut.folder / "film.mp4").write_bytes(b"Illustrative footage")
    cut.story["media"] = {"film": {"file": "film.mp4", "url": "https://example.org/film"}}
    row = data["claims"][0]
    row["evidence"][0]["file"] = "source.txt"
    row["illustrations"] = [{"asset": "film", "event_date": "2003-05-27", "published_at": "2021-01-08"}]
    cut.write("claims.json", data)
    file = cut.folder / "claims.json"
    claims.record_review(file, cache.file_hash(file), "greeting", inspect(), review())
    assert inspect()["claims"][0]["effective_status"] == "approved"
    (cut.folder / "film.mp4").write_bytes(b"Different film")
    assert inspect()["claims"][0]["effective_status"] == "needs_review"
    (cut.folder / "source.txt").write_text("Changed evidence")
    assert claims.citations(inspect()) == []


def test_review_cas_refuses_stale_input_and_cleans_lock(evidence):
    cut, data, takes, inspect, review = evidence
    file = cut.folder / "claims.json"
    before = file.read_bytes()
    with pytest.raises(ValueError, match="stale claims"):
        claims.record_review(file, "stale", "greeting", inspect(), review())
    assert file.read_bytes() == before and not list(cut.folder.glob("*.review.lock"))
    decision = review()
    cut.story["sources"]["own"]["url"] = "https://example.org/changed-after-review"
    with pytest.raises(ValueError, match="fingerprint is stale"):
        claims.record_review(file, cache.file_hash(file), "greeting", inspect(), decision)
    assert file.read_bytes() == before


def test_claim_gate_fails_before_renderer_and_is_bound_into_build_inputs(evidence):
    cut, data, takes, inspect, review = evidence
    from urdido.build import main
    from urdido.preflight import PreflightRefused

    with cut.declaration.open("a", encoding="utf-8") as file:
        file.write('\n[claims]\ndeclaration="claims.json"\naction="error"\n')
    with pytest.raises(PreflightRefused) as failure:
        main([str(cut.declaration), "--language", "en", "--cards", "--progress", "off"])
    assert any(f["field"] == "claims" for f in failure.value.findings)
    assert not (cut.folder / "video/parts/illustrated").exists()
    file = cut.folder / "claims.json"
    claims.record_review(file, cache.file_hash(file), "greeting", inspect(), review())
    with pytest.warns(UserWarning):
        assert main([str(cut.declaration), "--language", "en", "--cards", "--progress", "off"]) == 0
    manifest = json.loads((cut.folder / "video/parts/test.en.inputs.json").read_text())
    assert "claims.json" in json.dumps(manifest)
    assert (cut.folder / "video/test.en.claims.html").is_file()


def test_bounded_publishing_reuses_only_current_approved_claim_citations(evidence):
    cut, data, takes, inspect, review = evidence
    from urdido.publish.description import illustrated, units

    document = {**cut.story, "description": "Summary", "credits": "Credits", "generated": "", "media": {}}
    data["claims"][0]["evidence"][0]["url"] = "https://example.org/evidence"
    cut.write("claims.json", data)
    file = cut.folder / "claims.json"
    document["_claims_report"] = inspect()
    text, provenance = illustrated(document, ["0:00 Intro"])
    assert "https://example.org/evidence" not in text
    claims.record_review(file, cache.file_hash(file), "greeting", inspect(), review())
    document["_claims_report"] = inspect()
    text, provenance = illustrated(document, ["0:00 Intro"])
    assert "https://example.org/evidence" in text and units(text) <= 5000
    assert provenance["claims"]["claims"][0]["effective_status"] == "approved"
