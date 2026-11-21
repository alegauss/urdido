"""A bought take heard back against its line (UR13)."""

from urdido.heard import compare, message, plain, tokens


def timed(*texts):
    return [{"text": t, "start": float(i), "end": i + 0.8} for i, t in enumerate(texts)]


LINE = "[calm] Agentes de IA publicam 2.500 páginas."
PRONOUNCE = {"IA": "iá"}


def test_a_mapped_word_heard_as_its_sound_passes():
    found = compare(
        LINE, timed("Agentes", "de", "iá", "publicam", "2500", "páginas."), PRONOUNCE
    )
    assert found == {"refused": [], "missing": [], "added": []}


def test_a_mapped_word_heard_wrong_refuses_the_take_with_its_second():
    found = compare(
        LINE, timed("Agentes", "de", "Ída", "publicam", "2500", "páginas"), PRONOUNCE
    )
    assert found["refused"] == [{"word": "IA", "at": 2.0, "heard": "Ída"}]
    assert message("intro", found) == "intro: 'IA' heard as 'Ída' at 2 s"


def test_a_dropped_mapped_word_is_refused_too():
    found = compare(
        LINE, timed("Agentes", "de", "publicam", "2500", "páginas"), PRONOUNCE
    )
    assert found["refused"] == [{"word": "IA", "at": 2.0, "heard": "nothing"}]


def test_other_differences_are_reported_not_refused():
    found = compare(
        LINE, timed("Agentes", "de", "IA", "já", "publicam", "páginas"), PRONOUNCE
    )
    assert found["refused"] == []
    assert found["missing"] == [{"word": "2.500", "at": 5.0}]
    assert found["added"] == [{"word": "já", "at": 3.0}]


def test_a_mapped_word_heard_as_its_own_parts_passes_ur62():
    # japode/wordpress2's chapter 1: the voice says "B2 CafeLog" for b2/cafelog.
    line = "O programa era o b2/cafelog, criado pelo Michel."
    pronounce = {"b2/cafelog": "bê dois café log"}
    words = timed(
        "O", "programa", "era", "o", "B2", "CafeLog,", "criado", "pelo", "Michel."
    )
    assert compare(line, words, pronounce) == {
        "refused": [],
        "missing": [],
        "added": [],
    }
    # Said wrong, it is still refused, and named with what was heard in its place.
    wrong = timed(
        "O", "programa", "era", "o", "B2", "Catalog", "criado", "pelo", "Michel."
    )
    refused = compare(line, wrong, pronounce)["refused"]
    assert refused == [{"word": "b2/cafelog,", "at": 4.0, "heard": "B2 Catalog"}]


def test_words_compare_without_case_accents_punctuation_or_separators():
    assert plain("Páginas.") == "paginas"
    assert plain("2.500") == plain("2500") == "2500"
    assert tokens("[excited] Olá, mundo!") == ["Olá,", "mundo!"]
