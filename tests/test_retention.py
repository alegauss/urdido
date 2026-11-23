"""UR69: where a published video's viewers leave, read off Studio's curve."""

import pytest

from urdido import retention
from urdido.retention import RetentionRefused

SRT = """1
00:00:00,400 --> 00:00:05,000
Em setembro, a Anthropic juntava trinta mil mudanças por dia.

2
00:00:05,000 --> 00:00:20,000
Hoje eu quero te contar, com calma.

3
00:00:50,000 --> 00:00:58,000
O Scion guarda cada mudança.
"""


def write(tmp_path, name, text):
    file = tmp_path / name
    file.write_text(text, encoding="utf-8")
    return file


def test_a_studio_export_is_read_in_portuguese_and_by_audience(tmp_path):
    plain = write(
        tmp_path,
        "Todos.csv",
        "Posição no vídeo (%),Retenção absoluta de público (%)\n"
        "0,100\n1,82.35\n2,59.31\n",
    )
    assert retention.curve(plain) == [(0.0, 100.0), (1.0, 82.35), (2.0, 59.31)]
    split = write(
        tmp_path,
        "Tráfego.csv",
        "Posição no vídeo (%),Tipo de público,Retenção absoluta de público (%)\n"
        "0,Orgânicos,82.61\n0,Pago,102.48\n1,Orgânicos,39.13\n1,Pago,96.04\n",
    )
    assert retention.curve(split, "Orgânicos") == [(0.0, 82.61), (1.0, 39.13)]
    with pytest.raises(
        RetentionRefused, match="--audience with one of Orgânicos, Pago"
    ):
        retention.curve(split)
    with pytest.raises(RetentionRefused, match="no curve"):
        retention.curve(
            write(
                tmp_path, "Atividade.csv", "Posição no vídeo (%),Começaram a assistir\n"
            )
        )


def test_the_report_names_the_hook_the_cliffs_and_what_was_said(tmp_path):
    cues = retention.captions(write(tmp_path, "cut.srt", SRT))
    assert (
        cues[1].text == "Hoje eu quero te contar, com calma." and cues[0].start == 0.4
    )
    # 100 s, one sample a percent: a steep opening, then a cliff at 54 s, then flat.
    points = [(p, max(10.0, 100 - p * 3)) if p < 30 else (p, 10.0) for p in range(101)]
    points = [(p, r - (5 if p >= 54 else 0)) for p, r in points]
    report = retention.read(
        points, 100.0, cues, [{"src": "post", "start": 50.0, "dur": 10.0}]
    )
    assert report["hook"] == {"window": 30.0, "points": 90.0, "grade": "severe"}
    assert report["first_5s"] == 15.0
    big = max(report["cliffs"], key=lambda c: c["points"])
    assert (
        big["at"] == 53.5 and big["shot"] == "post" and "O Scion guarda" in big["said"]
    )
    assert len(report["cliffs"]) == 5
    assert "opening loses them" in report["verdict"]
    assert "hook: 90.0 points lost in the first 30 s, severe" in retention.text(report)


def test_a_short_reads_its_first_three_seconds_and_a_flat_curve_blames_the_title():
    flat = [(p, 100 - p * 0.05) for p in range(101)]
    report = retention.read(flat, 40.0, [])
    assert (
        report["short"]
        and report["hook"]["window"] == 3.0
        and report["hook"]["grade"] == "healthy"
    )
    assert report["cliffs"] == [] and "title and thumbnail" in report["verdict"]
