"""mix.py builds the ducking the goldens record, and mixes to the loudness target (VM5)."""

import json
import shutil
from pathlib import Path

import pytest

from videomaker.audio import mix as m

VIDEO_MAKER = Path(__file__).parent.parent
GOLDEN = VIDEO_MAKER / "test" / "golden" / "expected"
WORDPRESS = VIDEO_MAKER.parent / "turing" / "wordpress"
PLANS = sorted(GOLDEN.glob("*/*.plan.json"))


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def duck_of(music) -> m.Duck:
    return m.Duck(music["duck"]["between"], music["volume"], music["duck"]["ramp"])


def local(path: str) -> str:
    return path.replace("<root>", str(WORDPRESS))


@pytest.mark.parametrize("plan_file", PLANS, ids=lambda p: p.parent.name)
def test_envelope_equals_the_plan(plan_file):
    plan = load(plan_file)
    music = plan["music"]
    bed = m.Bed(music["file"], music["from"])
    narrated = {language: placed for language, placed in plan["spoken"].items() if placed}
    assert sorted(music["envelope"]) == sorted(narrated)
    for language, placed in narrated.items():
        takes = m.on_bed(m.takes_of(placed), bed)
        assert m.duck_expression(takes, duck_of(music)) == music["envelope"][language], language


def test_gain_follows_the_duck():
    takes = [m.Take("a", 10.0, 5.0)]
    duck = m.Duck(0.4, 0.2, 0.4)
    assert m.music_gain(takes, 0.0, duck) == pytest.approx(0.4)
    assert m.music_gain(takes, 9.8, duck) == pytest.approx(0.3)
    assert m.music_gain(takes, 12.0, duck) == pytest.approx(0.2)
    assert m.music_gain(takes, 16.0, duck) == pytest.approx(0.4)
    assert m.duck_expression([], duck) == "0.4-0.200*(0)"


def test_filtergraph_of_the_chapter_clip():
    """The chapter-2 clip's graph, as voiceTrack in story-video.mjs writes it for its plan."""
    plan = load(GOLDEN / "chapter-2" / "story-chapter-2.pt-BR.plan.json")
    music = plan["music"]
    total = sum(piece["length"] for piece in plan["pieces"])
    built = m.mix_graph(
        m.takes_of(plan["spoken"]["pt-BR"]),
        total,
        bed=m.Bed("music.mp3", music["from"]),
        trim_db=music["trimDb"],
        duck=duck_of(music),
    )
    envelope = music["envelope"]["pt-BR"]
    first, second = plan["spoken"]["pt-BR"]
    assert built.inputs == [
        "-i", first["file"], "-i", second["file"], "-stream_loop", "-1", "-i", "music.mp3",
    ]
    assert built.filters == [
        f"[0:a]adelay={round(first['at'] * 1000)}:all=1[d0]",
        f"[1:a]adelay={round(second['at'] * 1000)}:all=1[d1]",
        f"[2:a]atrim=0:{total:.3f},volume=-5.28dB,volume='{envelope}':eval=frame,afade=t=in:d=2,"
        f"afade=t=out:st={total - 3:.3f}:d=3,adelay=0:all=1[m]",
        f"[d0][d1][m]amix=inputs=3:normalize=0,apad=whole_dur={total:.3f}[mix]",
    ]


def test_sounds_come_before_the_bed():
    built = m.mix_graph(
        [m.Take("take.mp3", 7.0, 3.0)],
        20.0,
        sounds=[m.Sound("intro.mp4", 3.45, 0.0, 6.566)],
        bed=m.Bed("bed.mp3", 6.566),
        trim_db=-5.28,
    )
    assert built.inputs[2:8] == ["-ss", "3.450", "-t", "6.566", "-i", "intro.mp4"]
    assert built.filters[1] == "[1:a]afade=t=out:st=5.966:d=0.6,adelay=0:all=1[s0]"
    assert "(t-0.034)" in built.filters[2]  # the take, in the bed's own time
    assert built.filters[2].endswith("adelay=6566:all=1[m]")
    assert built.filters[3].startswith("[d0][s0][m]amix=inputs=3")


CHAPTER = GOLDEN / "chapter-2" / "story-chapter-2.pt-BR.plan.json"


def _media_present() -> bool:
    if not (shutil.which("ffmpeg") and CHAPTER.exists()):
        return False
    plan = load(CHAPTER)
    files = [local(p["file"]) for p in plan["spoken"]["pt-BR"]] + [local(plan["music"]["file"])]
    return all(Path(f).exists() for f in files)


@pytest.mark.skipif(not _media_present(), reason="the narration takes and the bed are not on this machine")
def test_chapter_mix_lands_on_the_target(tmp_path):
    plan = load(CHAPTER)
    music = plan["music"]
    total = sum(piece["length"] for piece in plan["pieces"])
    takes = [m.Take(local(t.file), t.at, t.length) for t in m.takes_of(plan["spoken"]["pt-BR"])]
    bed = m.Bed(local(music["file"]), music["from"])
    loudness = m.Loudness(music["loudness"]["target"], music["loudness"]["peak"])

    assert m.bed_trim(bed) == pytest.approx(music["trimDb"], abs=0.01)
    measured = m.voice_track(
        takes, total, str(tmp_path / "voice.pt-BR.m4a"), str(tmp_path),
        bed=bed, trim_db=music["trimDb"], duck=duck_of(music), loudness=loudness,
    )
    assert abs(measured - loudness.target) <= 0.3
