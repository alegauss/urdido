"""The words urdido writes into a published text, per language, and where it publishes.

A description's headings, licence labels and default credit line come from the table of
the build's language (UR27), never from the code that lays them out; a declaration can
replace any of them under `[description.strings]`. A language with no table falls back
to English, and says so by its words.

The licence prefixes are read, not written: a storyboard declares a licence in its own
words ("Gravação própria", "Own recording"), so every language's spellings are
recognised whatever language the video is in.

The target (YouTube today) owns what the platform imposes: the description's limit in
UTF-16 units, the characters it refuses and how its own links are shortened.
"""

from __future__ import annotations

from dataclasses import dataclass, field

STRINGS = {
    "pt": {
        "chapters": "Capítulos",
        "intro": "Introdução",
        "sources": "Fontes e demonstrações",
        "support": "Apoio",
        "own": "Capturas próprias",
        "images": "Imagens",
        "excerpt": "Trecho",
        "public_domain": "Domínio público",
        "reserved": "Direitos reservados; citação editorial",
        "demo": "Citação editorial; licença de reutilização não declarada",
        "court": "Documento judicial público",
        "video_changes": "Trechos sem áudio original; reenquadrados.",
        "photo_changes": "Fotografia integral, sem cortes.",
        "generated": "Narração e trilha geradas com ElevenLabs.",
    },
    "en": {
        "chapters": "Chapters",
        "intro": "Introduction",
        "sources": "Sources and demonstrations",
        "support": "Stock",
        "own": "Own captures",
        "images": "Images",
        "excerpt": "Excerpt",
        "public_domain": "Public domain",
        "reserved": "All rights reserved; editorial quotation",
        "demo": "Editorial quotation; reuse licence not declared",
        "court": "Public court document",
        "video_changes": "Excerpts without their original sound; reframed.",
        "photo_changes": "Whole photograph, uncropped.",
        "generated": "Narration and music generated with ElevenLabs.",
    },
}

#: How a storyboard's licence text is recognised, in any language it was declared in.
LICENCE_PREFIXES = {
    "own": ("Registro próprio", "Gravação própria", "Own recording", "Own capture"),
    "public_domain": ("Public domain", "Domínio público"),
    "reserved": ("Direitos reservados;", "All rights reserved;"),
    "demo": (
        "Breve recorte de demonstração oficial",
        "Short excerpt of an official demo",
    ),
    "court": ("Documento judicial público;", "Public court document;"),
}


def strings(language: str = "en", overrides: dict | None = None) -> dict[str, str]:
    """The published words for `language`, with the declaration's replacements."""
    base = language.split("-")[0].lower() if language else "en"
    table = dict(STRINGS.get(language, STRINGS.get(base, STRINGS["en"])))
    for key, value in (overrides or {}).items():
        if key not in table:
            raise ValueError(
                f"[description.strings] has no {key}; it takes "
                + ", ".join(sorted(table))
            )
        table[key] = value
    return table


def licence_kind(licence: str) -> str | None:
    """Which declared licence family a storyboard's licence text opens with."""
    for kind, prefixes in LICENCE_PREFIXES.items():
        if licence.startswith(prefixes):
            return kind
    return None


@dataclass(frozen=True)
class Target:
    """A platform a description is published to, and what it imposes."""

    name: str
    limit: int
    refused: tuple[str, ...] = ()
    short_hosts: frozenset[str] = field(default_factory=frozenset)


YOUTUBE = Target(
    "YouTube",
    5000,
    ("<", ">"),
    frozenset({"youtube.com", "www.youtube.com", "m.youtube.com"}),
)
TARGETS = {"youtube": YOUTUBE}
