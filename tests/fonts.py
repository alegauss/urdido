"""A font made at test time, so no test needs a font from another repository (UR31).

It covers Basic Latin, Latin-1 and Latin Extended-A and the punctuation narration uses
(dashes, curly quotes, the ellipsis), each glyph a plain box, which is what a coverage
check reads and what a browser can still lay out. It covers no CJK, so a test can still
ask for a glyph the font lacks.
"""

from __future__ import annotations

from pathlib import Path

COVERED = [
    *range(0x20, 0x7F),
    *range(0xA0, 0x180),
    0x2013,
    0x2014,
    0x2018,
    0x2019,
    0x201C,
    0x201D,
    0x2026,
    0x20AC,
]


def synthetic_font(path: Path, family: str = "Urdido Test") -> Path:
    """Write a TrueType font covering `COVERED` to `path` and return it."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    def box(width: int):
        pen = TTGlyphPen(None)
        pen.moveTo((50, 0))
        pen.lineTo((50, 700))
        pen.lineTo((width - 50, 700))
        pen.lineTo((width - 50, 0))
        pen.closePath()
        return pen.glyph()

    names = [".notdef", *(f"uni{cp:04X}" for cp in COVERED)]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap({cp: f"uni{cp:04X}" for cp in COVERED})
    empty = TTGlyphPen(None).glyph()
    glyphs = {".notdef": box(500)}
    for cp in COVERED:
        glyphs[f"uni{cp:04X}"] = empty if cp in (0x20, 0xA0) else box(600)
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (600, 0) for name in names})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": family, "styleName": "Regular"})
    builder.setupOS2(
        sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200
    )
    builder.setupPost()
    path.parent.mkdir(parents=True, exist_ok=True)
    builder.save(str(path))
    return path
