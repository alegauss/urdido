"""UR7: a take whose text is unchanged can be bought again, with the reason kept."""

import json

import pytest

from test_preflight import cut  # noqa: F401  (the preflight fixture)
from test_prepare import prepared  # noqa: F401  (the prepare fixture)
from urdido import prepare
from urdido.sources.model import RecordingRefused

REASON = "accent: European Portuguese between 0:28 and 0:35"


def outro(prepared):  # noqa: F811
    return prepared.cut.folder / "narration/en/outro.mp3"


def test_a_dry_retake_prices_the_take_and_leaves_it_in_place(prepared):  # noqa: F811
    audio = outro(prepared)
    before = {p: p.read_bytes() for p in audio.parent.iterdir() if p.is_file()}
    report = prepare.retaken(prepared.options(retake=["outro"], retake_reason=REASON))
    assert prepared.calls == []
    assert report["voice_estimate"] == 0.01
    assert next(r for r in report["takes"] if r["take"] == "outro")["voice_needed"]
    assert report["retakes"] == [
        {"take": "outro", "reason": REASON, "status": "planned"}
    ]
    assert {p: p.read_bytes() for p in audio.parent.iterdir() if p.is_file()} == before
    assert not (prepared.cut.folder / "narration/retakes.json").exists()


def test_an_authorized_retake_buys_it_and_keeps_the_old_take_with_its_reason(
    prepared,  # noqa: F811
):
    audio = outro(prepared)
    old = audio.read_bytes()
    report = prepare.retaken(
        prepared.options(
            retake=["outro"],
            retake_reason=REASON,
            execute=True,
            authorize_take=["outro"],
            max_cost=0.1,
        )
    )
    assert ("voice", "outro") in prepared.calls
    assert audio.read_bytes() == b"generated outro"
    assert report["retakes"][0]["status"] == "bought"
    aside = sorted((audio.parent / "retakes").iterdir())
    assert [p.read_bytes() for p in aside if p.suffix == ".mp3"] == [old]
    assert any(p.name.endswith(".mp3.prov.json") for p in aside)
    ledger = json.loads((prepared.cut.folder / "narration/retakes.json").read_text())
    assert ledger[0]["take"] == "outro" and ledger[0]["reason"] == REASON
    assert ledger[0]["voice"] == "test" and ledger[0]["model"] == "test"
    assert all(path.startswith("en/retakes/") for path in ledger[0]["set_aside"])


def test_a_retake_the_ceiling_stops_puts_the_old_take_back(prepared):  # noqa: F811
    audio = outro(prepared)
    before = {p: p.read_bytes() for p in audio.parent.iterdir() if p.is_file()}
    with pytest.raises(RecordingRefused):
        prepare.retaken(
            prepared.options(
                retake=["outro"],
                retake_reason=REASON,
                execute=True,
                authorize_take=["outro"],
                max_cost=0.001,
            )
        )
    assert {p: p.read_bytes() for p in audio.parent.iterdir() if p.is_file()} == before


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"retake": ["outro"]}, "--retake-reason"),
        (
            {"retake": ["outro"], "retake_reason": REASON, "execute": True},
            "--authorize-take",
        ),
        (
            {"retake": ["outro"], "retake_reason": REASON, "take": ["intro"]},
            "selection",
        ),
        ({"retake": ["nowhere"], "retake_reason": REASON}, "known"),
    ],
)
def test_a_retake_is_refused_before_anything_moves(prepared, options, message):  # noqa: F811
    audio = outro(prepared)
    before = {p: p.read_bytes() for p in audio.parent.iterdir() if p.is_file()}
    with pytest.raises(ValueError, match=message):
        prepare.retaken(prepared.options(**options))
    assert {p: p.read_bytes() for p in audio.parent.iterdir() if p.is_file()} == before


def test_without_a_retake_it_is_prepare_unchanged(prepared):  # noqa: F811
    report = prepare.retaken(prepared.options())
    assert "retakes" not in report
