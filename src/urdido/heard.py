"""What a bought take says, heard back against its line (UR13).

`pronounce` changes what is sent to the voice; this listens to what came back. A take's
transcript (`<take>.words.json`, written on purchase) is aligned with the line's words:

- each word the pronounce map names must be heard where the line has it, spelled as
  written or as the map sounds it (`IA` or `iá`); a take where it is missing or heard as
  something else (`Ída`) is refused, with the second it should have been said;
- words missing from the take or added to it are reported with their seconds, for a
  person to judge, since a transcript writes numbers and names its own way.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

TAG = re.compile(r"\[[^\]]*\]")


def plain(word: str) -> str:
    """A word as two spellings of it compare: casefolded, unaccented, no punctuation,
    and a number without its thousands separators."""
    folded = unicodedata.normalize("NFKD", word.casefold())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    if re.fullmatch(r"[\d.,]+", folded):
        return re.sub(r"[.,](?=\d{3}\b)", "", folded).rstrip(".,")
    return re.sub(r"[^\w]", "", folded)


def tokens(text: str) -> list[str]:
    """The line's words, its audio tags (`[excited]`) left out."""
    return [w for w in TAG.sub(" ", text).split() if plain(w)]


def compare(line: str, words: list[dict], pronounce: dict | None = None) -> dict:
    """Align a take's transcript with its line.

    Returns `{"refused": [...], "missing": [...], "added": [...]}`: refusals are
    mapped words not heard; missing and added are the other differences, each with
    its second."""
    pronounce = pronounce or {}
    said = tokens(line)
    expected = [plain(w) for w in said]
    heard = [plain(w["text"]) for w in words]
    accepted = {
        plain(word): {plain(word), *map(plain, sound.split())}
        for word, sound in pronounce.items()
    }
    # A mapped word heard as its own parts ("b2/cafelog" as "B2 CafeLog") is one word:
    # consecutive heard words that join into it are merged, keeping the first's index.
    merged: list[tuple[str, int]] = []
    i = 0
    while i < len(heard):
        for n in (3, 2):
            joined = "".join(heard[i : i + n])
            if i + n <= len(heard) and joined in accepted:
                merged.append((joined, i))
                i += n
                break
        else:
            merged.append((heard[i], i))
            i += 1
    # A mapped word heard as its sound counts as the word itself for the alignment.
    sound_of = {s: word for word, sounds in accepted.items() for s in sounds}
    aligned = [sound_of.get(w, w) for w, _ in merged]
    found = {"refused": [], "missing": [], "added": []}

    def at(index: int) -> int:
        """The transcript index of the merged word `index` (its end, past the last)."""
        return merged[index][1] if index < len(merged) else len(words)

    def second(index: int) -> float:
        if not words:
            return 0.0
        return round(words[min(at(index), len(words) - 1)]["start"], 2)

    matcher = SequenceMatcher(a=expected, b=aligned, autojunk=False)
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op == "equal":
            continue
        for i in range(a0, a1):
            row = {"word": said[i], "at": second(b0)}
            if expected[i] in accepted:
                instead = " ".join(w["text"] for w in words[at(b0) : at(b1)])
                found["refused"].append({**row, "heard": instead or "nothing"})
            else:
                found["missing"].append(row)
        for j in range(b0, b1):
            text = " ".join(w["text"] for w in words[at(j) : at(j + 1)])
            found["added"].append({"word": text, "at": second(j)})
    return found


def message(take: str, found: dict) -> str:
    rows = [
        f"{take}: {r['word']!r} heard as {r['heard']!r} at {r['at']:g} s"
        for r in found["refused"]
    ]
    return "; ".join(rows)
