"""VM60: paid stages require explicit takes and a bounded, configured estimate."""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from videomaker import prepare, keywords
from videomaker.cache import file_hash
from videomaker.narration import Takes
from videomaker.sources.model import RecordingRefused
from test_preflight import cut


@pytest.fixture
def prepared(cut, monkeypatch):
    config = cut.folder / "polyweave.toml"
    config.write_text('''[service.elevenlabs]
prices={test={per="character",rate=0.001},scribe_v1={per="second",rate=0.01}}
[budget.elevenlabs]
amount=1.0
unit="USD"
''')
    calls = []
    def voice(root, lines_file, language, service, *, keys=None, spend=False):
        payload = json.loads(Path(lines_file).read_text("utf-8"))
        rows = [line for line in payload["lines"] if not keys or line["key"] in keys]
        takes = Takes(cut.script, str(cut.folder / "narration"))
        planned, current, voiced = [], [], []
        if spend:
            assert [line["key"] for line in payload["lines"]] == keys  # purchase file itself is scoped
        for row in rows:
            name = row["key"]
            audio = root / payload["out"].format(locale=language, key=name)
            record = {"key": name, "locale": language, "out": str(audio.relative_to(root))}
            if takes.current(str(audio), language, takes.lines[name][language]):
                current.append(record)
            else:
                planned.append({**record, "price": .01})
                if spend:
                    calls.append(("voice", name))
                    audio.write_bytes(b"generated " + name.encode())
                    Path(str(audio) + ".prov.json").write_text(json.dumps({"prompt": row["text"], "details": {"voice": payload["voice"]},
                        "engine": {"model": payload["model"]}, "artefact": {"sha256": file_hash(audio)}}))
                    voiced.append(record)
        return {"voice": planned, "current": current, "voiced": voiced, "unit": "USD", "price": sum(p["price"] for p in planned), "spent": spend}
    def transcribe(audio, language, **kwargs):
        calls.append(("transcribe", audio.stem))
        audio.with_suffix(".words.json").write_text(json.dumps({"sha256": file_hash(audio),
            "words": [{"text": "Uôrdpress", "start": .1, "end": .9}]}), encoding="utf-8")
        return f"transcribed {audio.stem}: 1 words"
    monkeypatch.setattr(prepare, "voice", voice)
    monkeypatch.setattr(prepare, "transcribe", transcribe)
    def options(**values):
        return SimpleNamespace(**{
            "declaration": cut.declaration, "language": "en", "root": None, "take": None, "authorize_take": None,
            "execute": False, "max_cost": None, "service": None, **values})
    return SimpleNamespace(cut=cut, config=config, calls=calls, options=options, voice=voice)


def changed(prepared):
    cut = prepared.cut
    cut.script["outro"]["en"] = "WordPress"
    cut.script["pronounce"] = {"en": {"WordPress": "Uôrdpress"}}
    cut.write("script.json", cut.script)
    cut.write("highlights.json", {"style": {"font": "Fixture", "color": "#00ff00"}, "lines": {"outro": [{"show": "WordPress"}]}})


def test_dry_plan_lists_changes_cost_and_impacts_without_paid_calls_or_overwriting_inputs(prepared):
    changed(prepared)
    audio = prepared.cut.folder / "narration/en/outro.mp3"
    original = audio.read_bytes()
    report = prepare.prepare(prepared.options())
    assert prepared.calls == [] and audio.read_bytes() == original
    assert report["voice_estimate"] == .01 and report["voice"] == "test" and report["model"] == "test"
    outro = next(r for r in report["takes"] if r["take"] == "outro")
    assert outro["voice_needed"] and outro["impacts"]["highlight_labels"] == ["WordPress"]
    assert report["pronounce"] == {"WordPress": "Uôrdpress"}
    assert not report["selected_takes_ready"]


def test_execute_generates_only_authorized_take_transcribes_it_once_and_reuses_current_transcript(prepared):
    changed(prepared)
    intro = prepared.cut.folder / "narration/en/intro.mp3"
    intro_bytes = intro.read_bytes()
    before_highlights = (prepared.cut.folder / "highlights.json").read_bytes()
    args = prepared.options(execute=True, authorize_take=["outro"], max_cost=.1)
    report = prepare.prepare(args)
    assert prepared.calls == [("voice", "outro"), ("transcribe", "outro")]
    assert report["selected_takes_ready"] and report["estimated_spent"] == pytest.approx(.04)
    assert intro.read_bytes() == intro_bytes
    assert (prepared.cut.folder / "highlights.json").read_bytes() == before_highlights
    report = prepare.prepare(prepared.options(execute=True, authorize_take=["outro"]))
    assert prepared.calls == [("voice", "outro"), ("transcribe", "outro")]
    assert report["estimated_spent"] == 0


def test_missing_authorization_rate_or_budget_refuses_before_generation(prepared):
    changed(prepared)
    for values, message in [({"execute": True}, "no changed takes authorized"),
                             ({"execute": True, "authorize_take": ["outro"]}, "max-cost"),
                             ({"execute": True, "authorize_take": ["outro"], "max_cost": .001}, "voice estimate exceeds")]:
        with pytest.raises(RecordingRefused, match=message):
            prepare.prepare(prepared.options(**values))
    prepared.config.write_text('[service.elevenlabs]\nprices={test={per="character",rate=0.001}}\n')
    with pytest.raises(RecordingRefused, match="prices.scribe_v1"):
        prepare.prepare(prepared.options(execute=True, authorize_take=["outro"], max_cost=.1))
    assert prepared.calls == []
    assert not (prepared.cut.folder / ".polyweave/prepare/EXECUTING.lock").exists()


def test_transcription_budget_stop_keeps_generated_take_and_resume_does_not_buy_it_again(prepared):
    changed(prepared)
    with pytest.raises(RecordingRefused, match="remaining project/--max-cost"):
        prepare.prepare(prepared.options(execute=True, authorize_take=["outro"], max_cost=.02))
    assert prepared.calls == [("voice", "outro")]
    report = prepare.prepare(prepared.options(execute=True, authorize_take=["outro"], max_cost=.1))
    assert prepared.calls == [("voice", "outro"), ("transcribe", "outro")]
    assert report["estimated_spent"] == pytest.approx(.03)
    assert len(list((prepared.cut.folder / ".polyweave/prepare").rglob("attempt-*.json"))) == 2


def test_changed_inputs_after_quote_stop_before_any_paid_stage(prepared, monkeypatch):
    changed(prepared)
    def drift(*args, **kwargs):
        result = prepared.voice(*args, **kwargs)
        if not kwargs.get("spend"):
            prepared.config.write_text(prepared.config.read_text() + "\n# changed after quote\n")
        return result
    monkeypatch.setattr(prepare, "voice", drift)
    with pytest.raises(RecordingRefused, match="inputs changed"):
        prepare.prepare(prepared.options(execute=True, authorize_take=["outro"], max_cost=.1))
    assert prepared.calls == []


def test_declared_aliases_use_real_times_but_uncertain_asr_spelling_is_only_a_suggestion(tmp_path):
    audio = tmp_path / "intro.mp3"
    audio.write_bytes(b"fixture")
    audio.with_suffix(".words.json").write_text(json.dumps({"sha256": file_hash(audio), "words": [
        {"text": "Uôrdpress", "start": .1, "end": .4}, {"text": "Relodol", "start": .8, "end": 1.2}]}), encoding="utf-8")
    aliases = keywords.aliases({"pronounce": {"en": {"WordPress": "Uôrdpress", "Hello Dolly": "Rélou Dóli"}}}, "en")
    assert keywords.anchor(audio, "WordPress", aliases=aliases) == .1
    assessment = prepare.assessments("intro", audio, {"intro": [{"show": "WordPress"}, {"show": "Hello Dolly"}]}, [], aliases)
    assert assessment[0]["status"] == "matched" and assessment[1]["status"] == "needs_review"
    assert assessment[1]["candidates"][0]["requires_review"]
    assert assessment[1]["candidates"][0]["heard"] == "Relodol"
    assert "at" not in assessment[1]
    declared = keywords.aliases({"alignment_aliases": {"en": {"Hello Dolly": ["Relodol"]}}}, "en")
    assert keywords.anchor(audio, "Hello Dolly", aliases=declared) == .8


def test_pronunciation_keys_are_literal_and_changed_bytes_are_not_current(cut):
    script = {**cut.script, "pronounce": {"en": {"WordPress.com": "site"}}}
    takes = Takes(script, str(cut.folder / "narration"))
    assert takes.spoken("en", "WordPressXcom WordPress.com") == "WordPressXcom site"
    audio = cut.folder / "narration/en/intro.mp3"
    record = json.loads(Path(str(audio) + ".prov.json").read_text())
    record["artefact"] = {"sha256": file_hash(audio)}
    Path(str(audio) + ".prov.json").write_text(json.dumps(record))
    audio.write_bytes(b"changed bytes")
    assert not takes.current(str(audio), "en", script["intro"]["en"])


def test_current_bom_transcript_is_reused_without_network(tmp_path, monkeypatch):
    import requests
    from videomaker.narration_words import transcribe

    audio = tmp_path / "take.mp3"
    audio.write_bytes(b"fixture")
    record = audio.with_suffix(".words.json")
    record.write_text(json.dumps({"sha256": file_hash(audio), "words": [{"text": "Hello", "start": 0, "end": 1}]}), encoding="utf-8-sig")
    original = record.read_bytes()
    monkeypatch.setattr(requests, "post", lambda *a, **k: pytest.fail("unchanged transcript made a paid request"))
    assert transcribe(audio, "eng").startswith("current")
    assert record.read_bytes() == original


def test_voice_project_remaining_is_respected_even_with_a_larger_command_ceiling(prepared, monkeypatch):
    changed(prepared)
    def limited(*args, **kwargs):
        return {**prepared.voice(*args, **kwargs), "left": .005}
    monkeypatch.setattr(prepare, "voice", limited)
    with pytest.raises(RecordingRefused, match="voice estimate exceeds"):
        prepare.prepare(prepared.options(execute=True, authorize_take=["outro"], max_cost=.1))
    assert prepared.calls == []


def test_transcription_uploads_hash_bound_bytes_and_rejects_concurrent_audio_changes(tmp_path, monkeypatch):
    import requests
    from videomaker.narration_words import transcribe

    audio = tmp_path / "take.mp3"
    audio.write_bytes(b"original upload")
    record = audio.with_suffix(".words.json")
    record.write_text('{"sha256":"stale","words":[]}')
    before = record.read_bytes()
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-fixture-key")
    def post(*args, **kwargs):
        assert kwargs["files"]["file"][1] == b"original upload"
        audio.write_bytes(b"changed during request")
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"words": [{"type": "word", "text": "Hello", "start": 0, "end": 1}]})
    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(RuntimeError, match="audio changed"):
        transcribe(audio, "eng")
    assert record.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


def test_literal_pronunciation_mapping_agrees_with_the_existing_node_reader(cut):
    module = Path(__file__).resolve().parents[1] / "narration/takes.mjs"
    code = "const {pathToFileURL}=await import('node:url');const {takes}=await import(pathToFileURL(process.argv[1]));console.log(takes({script:JSON.parse(process.argv[2]),dir:'.'}).spoken('en','WordPressXcom WordPress.com'));"
    script = {**cut.script, "pronounce": {"en": {"WordPress.com": "site"}}}
    run = subprocess.run(["node", "--input-type=module", "-e", code, str(module), json.dumps(script)], capture_output=True, text=True, check=True)
    assert run.stdout.strip() == Takes(script, ".").spoken("en", "WordPressXcom WordPress.com") == "WordPressXcom site"


def test_provider_speech_failures_stay_for_review_even_when_the_anchors_match(prepared, monkeypatch):
    changed(prepared)
    def flagged(*args, **kwargs):
        result = prepared.voice(*args, **kwargs)
        if kwargs.get("spend"):
            result["voiced"][0]["failed"] = ["service speech check needs review"]
        return result
    monkeypatch.setattr(prepare, "voice", flagged)
    report = prepare.prepare(prepared.options(execute=True, authorize_take=["outro"], max_cost=.1))
    assert report["status"] == "needs_review" and not report["selected_takes_ready"]
    assert report["needs_review"][0]["kind"] == "voice_check"
