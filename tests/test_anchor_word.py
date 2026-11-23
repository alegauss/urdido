"""UR67: an [anchors] word in the narration's language."""

import pytest

from urdido.assemble.scenes import anchor_word
from urdido.sources.model import RecordingRefused


def test_a_plain_word_serves_every_language():
    assert anchor_word("console", "en") == "console"
    one = {"text": "there", "occurrence": 2}
    assert anchor_word(one, "en") == one


def test_a_table_keyed_by_language_picks_the_narration_language():
    spec = {"pt-BR": "Aí", "en": {"text": "there", "occurrence": 2}}
    assert anchor_word(spec, "pt-BR") == "Aí"
    assert anchor_word(spec, "en") == {"text": "there", "occurrence": 2}


def test_a_language_the_table_lacks_is_refused_by_name():
    with pytest.raises(RecordingRefused, match="chapter-1: .*no en entry .*pt-BR"):
        anchor_word({"pt-BR": "Aí"}, "en", "chapter-1")
