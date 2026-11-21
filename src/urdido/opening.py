"""The opening gate, before any take is bought (VM29, in Python since UR30).

A narration whose opening wastes the first seconds is refused before the voice is paid
for: a preamble ("hoje eu quero", "today we will", "subscribe to our channel") in the
intro, or a first proof the viewer sees later than 20 s. The proof is the editor's
declared first visual (`opening.proof.<language>`: a take and a zero-based word), and
the time to it is estimated from the words before it at the narrator's declared pace
(`opening.words_per_minute.<language>`); voice directions in brackets are not words,
and a word the `pronounce` map spells out counts as what the voice says.

`js/narration/opening.mjs` is the same gate for the JavaScript buyer; this one is what
`urdido prepare` runs, so a build needs no node.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping

from urdido.narration import Takes
from urdido.sources.model import RecordingRefused

PREAMBLE = re.compile(
    r"\b(?:hoje\s+(?:eu\s+)?(?:quero|vou|vamos)|vem\s+comigo|inscreva-se|se\s+inscreva"
    r"|today\s+(?:I|we)\s+(?:want|will|are\s+going)|let['’]s\s+get\s+started"
    r"|subscribe\s+to\s+(?:my|our|the)\s+channel)\b",
    re.IGNORECASE,
)
DIRECTION = re.compile(r"\[[^\]]+\]\s*")
WORD = re.compile(r"[^\W_]+(?:['’/-][^\W_]+)*")
LIMIT = 20.0


def caption(text: str) -> str:
    """A line as written, its voice directions left out."""
    return DIRECTION.sub("", text).strip()


def words(text: str) -> list[str]:
    return WORD.findall(caption(text))


def check(script: Mapping, locale: str | None = None) -> list[dict]:
    """Each checked language's words and seconds before the first proof; refuses a
    preamble, a missing declaration or a proof later than 20 s."""
    takes = Takes(script, ".")
    languages = [locale] if locale else list(script["intro"])
    report = []
    for language in languages:
        intro = script["intro"].get(language)
        if not isinstance(intro, str):
            raise RecordingRefused(f"opening {language}: no intro text")
        found = PREAMBLE.search(caption(intro))
        if found:
            raise RecordingRefused(
                f'opening {language}: remove the preamble "{found[0]}" '
                "before buying narration"
            )
        opening = script.get("opening")
        if not opening:
            continue
        pace = (opening.get("words_per_minute") or {}).get(language)
        proof = (opening.get("proof") or {}).get(language)
        if (
            isinstance(pace, bool)
            or not isinstance(pace, (int, float))
            or not math.isfinite(pace)
            or pace <= 0
        ):
            raise RecordingRefused(
                f"opening {language}: declare a positive words_per_minute "
                "for the narrator"
            )
        before = (proof or {}).get("before_word")
        if (
            not proof
            or isinstance(before, bool)
            or not isinstance(before, int)
            or before < 0
        ):
            raise RecordingRefused(
                f"opening {language}: declare proof.take and a zero-based "
                "proof.before_word"
            )
        count, reached = 0, False
        for key, texts in takes.lines.items():
            text = (texts or {}).get(language)
            if not isinstance(text, str):
                raise RecordingRefused(f"opening {language}: missing text for {key}")
            length = len(words(takes.spoken(language, text)))
            if key == proof.get("take"):
                if before >= length:
                    raise RecordingRefused(
                        f"opening {language}: proof word is outside {key}"
                    )
                count += before
                reached = True
                break
            count += length
        if not reached:
            raise RecordingRefused(
                f"opening {language}: unknown proof take {proof.get('take')}"
            )
        seconds = count * 60 / pace
        if seconds > LIMIT:
            raise RecordingRefused(
                f"opening {language}: first proof estimated at {seconds:.1f} s; "
                f"move it within {LIMIT:g} s before buying narration"
            )
        report.append({"language": language, "words": count, "seconds": seconds})
    return report
