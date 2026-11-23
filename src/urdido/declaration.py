"""The keys a video.toml may hold, checked before anything is built (UR23).

    urdido check <video.toml>      refuse unknown and missing keys, building nothing
    urdido check --schema          print the JSON Schema editors and the docs read

Every table the code reads is named here with its keys. A key the schema does not know
is refused with its file, its table and the nearest valid name, so a typo costs a
second, not a partial build. A table marked as a map takes any key (a language, an
instance's name, a root) and holds values of one shape.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from difflib import get_close_matches
from pathlib import Path

ANY = None  # a value the schema does not shape

#: Values of one type (UR47): a number (an int or a float, never a bool), a text,
#: a true or false, a list.
NUMBER = {"type": "number"}
TEXT = {"type": "string"}
FLAG = {"type": "boolean"}
LIST = {"type": "array"}


def typed_ok(value, kind: str) -> bool:
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, {"string": str, "boolean": bool, "array": list}[kind])


def table(keys: dict, required: tuple[str, ...] = ()) -> dict:
    return {"keys": keys, "required": required}


def mapping(value) -> dict:
    """A table whose keys are names (a language, an instance), values of one shape."""
    return {"map": value}


def array(item) -> dict:
    return {"array": item}


LANGUAGES = mapping(ANY)
PICTURE = table(
    {
        "file": ANY,
        "at": ANY,
        "box": ANY,
        "reason": ANY,
        "license": ANY,
        "author": ANY,
        "url": ANY,
        "fit": ANY,
        "margin": ANY,
        "background": ANY,
    },
    required=("file",),
)

#: Every table of a video.toml, and what it holds.
SCHEMA = table(
    {
        "video": table(
            {
                "name": ANY,
                "languages": LANGUAGES,
                "folders": LANGUAGES,
                "title_languages": ANY,
                "revision": ANY,
                "base": ANY,
                "frame": ANY,
            },
            required=("name", "languages"),
        ),
        "roots": mapping(ANY),
        "output": table({"folder": ANY, "parts": ANY}),
        "source": table(
            {
                "kind": ANY,
                "declaration": ANY,
                "listing": ANY,
                "folder": ANY,
                "vertical_folder": ANY,
                "recording": ANY,
                "chapters": ANY,
                "newer_than": ANY,
                "record_command": ANY,
                "vertical_record_command": ANY,
                "shots": ANY,
                "footage": ANY,
                "lead": ANY,
                "gap": ANY,
                "end": ANY,
                "styles": ANY,
                "closing": LANGUAGES,
                "fonts": ANY,
                "sources": ANY,
            },
            required=("kind",),
        ),
        "narration": table(
            {"script": ANY, "takes": ANY, "tempo": ANY}, required=("script", "takes")
        ),
        "cards": table({"declaration": ANY, "words": ANY, "channel": ANY}),
        "music": table(
            {"bed": ANY, "reference": ANY, "between": ANY, "under": ANY, "ramp": ANY}
        ),
        "audio": table({"target": ANY, "peak": ANY, "tolerance": ANY, "margin": ANY}),
        "opening": table(
            {
                "intro": ANY,
                "intro_meta": ANY,
                "footage": ANY,
                "photos": ANY,
                "store": ANY,
                "screens": array(table({"path": ANY, "scroll": ANY, "follow": ANY})),
                "cold_open": array(table({"chapter": ANY, "seconds": ANY})),
            }
        ),
        "cuts": table({"teaser": ANY}),
        "captions": table(
            {
                "translations": mapping(
                    table({"file": ANY, "track": ANY}, required=("file",))
                ),
                "burn": ANY,
                "safe_area": table({"bottom": ANY, "action": ANY}),
            }
        ),
        "highlights": table({"declaration": ANY, "fonts": ANY}),
        "claims": table({"declaration": ANY, "action": ANY}),
        "description": table(
            {
                "summary": ANY,
                "notes": ANY,
                "sources": ANY,
                "generated": ANY,
                "strings": ANY,
                "license_label": ANY,
                "license_url": ANY,
                "changes": ANY,
            }
        ),
        "text_checks": table({"action": ANY, "protected_tokens": ANY, "glyphs": ANY}),
        "mark": table(
            {
                "logo": ANY,
                "corner": ANY,
                "margin": ANY,
                "size": ANY,
                "opacity": ANY,
                "font": ANY,
                "background": ANY,
                "text": ANY,
            }
        ),
        "anchors": mapping(ANY),
        "qa": table({"flashes": ANY, "flash_threshold": ANY, "flash_refuse": ANY}),
        "publish": table({"declaration": ANY}),
        "resolve": table({"declaration": ANY}),
        "thumbnail": table(
            {
                "layout": ANY,
                "out": ANY,
                "picture": PICTURE,
                "proof": PICTURE,
                "words": LANGUAGES,
                "title": LANGUAGES,
                "check": table({"stopwords": ANY, "superlatives": ANY, "drawn": ANY}),
            }
        ),
        # Two cutters read [shorts], one per table (UR48): a scenes build's selection
        # (`declaration` alone, SELECTION_KEYS) or `urdido shorts` (the rest).
        "shorts": table(
            {
                "declaration": ANY,
                "plan": ANY,
                "picture": ANY,
                "mix": ANY,
                "words": ANY,
                "out": ANY,
                "link": ANY,
                "tags": ANY,
                "sources": ANY,
                "credit": ANY,
                "fixes": ANY,
                "notes": LANGUAGES,
                "look": table(
                    {
                        "night": ANY,
                        "accent": ANY,
                        "ink": ANY,
                        "title_font": ANY,
                        "text_font": ANY,
                        "fonts": ANY,
                    }
                ),
                "rules": ANY,
                "pointer": LANGUAGES,
                "cut": array(
                    table(
                        {"n": ANY, "takes": ANY, "hook": ANY, "title": ANY, "text": ANY}
                    )
                ),
            }
        ),
        "record": table(
            {
                "step": array(
                    table(
                        {"name": ANY, "command": ANY, "makes": ANY, "always": ANY},
                        required=("name", "command"),
                    )
                )
            }
        ),
        "terminal": table(
            {
                "work": TEXT,
                "session": TEXT,
                "shell": TEXT,
                "title": TEXT,
                "keep": mapping(TEXT),
                "scenes": mapping(table({"commands": LIST}, required=("commands",))),
            }
        ),
        "instances": mapping(
            table(
                {
                    "run": ANY,
                    "setup": ANY,
                    "compose": ANY,
                    "timeout": ANY,
                    "ready": ANY,
                    "url": ANY,
                    "ready_status": ANY,
                    "startup_logs_service": ANY,
                },
                required=("url",),
            )
        ),
    },
    required=("video",),
)

#: The keys whose values have one type, by table (UR47).
TYPES = {
    "video": {
        "name": TEXT,
        "revision": TEXT,
        "frame": LIST,
        "base": TEXT,
    },
    "output": {"folder": TEXT, "parts": TEXT},
    "source": {
        "kind": TEXT,
        "declaration": TEXT,
        "listing": TEXT,
        "folder": TEXT,
        "recording": TEXT,
        "chapters": NUMBER,
        "shots": TEXT,
        "footage": TEXT,
        "lead": NUMBER,
        "gap": NUMBER,
        "end": NUMBER,
        "styles": TEXT,
        "fonts": TEXT,
        "sources": TEXT,
        "newer_than": LIST,
    },
    "narration": {"script": TEXT, "takes": TEXT, "tempo": NUMBER},
    "cards": {"declaration": TEXT, "channel": TEXT},
    "music": {
        "bed": TEXT,
        "reference": NUMBER,
        "between": NUMBER,
        "under": NUMBER,
        "ramp": NUMBER,
    },
    "audio": {"target": NUMBER, "peak": NUMBER, "tolerance": NUMBER, "margin": NUMBER},
    "cuts": {"teaser": FLAG},
    "highlights": {"declaration": TEXT, "fonts": TEXT},
    "claims": {"declaration": TEXT, "action": TEXT},
    "text_checks": {"action": TEXT, "glyphs": FLAG},
    "mark": {
        "logo": TEXT,
        "corner": TEXT,
        "size": NUMBER,
        "opacity": NUMBER,
        "font": TEXT,
        "background": TEXT,
        "text": TEXT,
        "margin": LIST,
    },
    "qa": {"flashes": TEXT, "flash_threshold": NUMBER, "flash_refuse": NUMBER},
    "thumbnail": {"layout": TEXT, "out": TEXT},
}
for _table, _keys in TYPES.items():
    for _key, _kind in _keys.items():
        assert _key in SCHEMA["keys"][_table]["keys"], (_table, _key)
        SCHEMA["keys"][_table]["keys"][_key] = _kind

#: What an absent key means, by table (UR47): `setting` reads it, and the reference
#: prints it, so no module holds a default of its own.
DEFAULTS = {
    "video": {"frame": [1920, 1080]},
    "output": {"folder": "video", "parts": "parts"},
    "source": {"footage": "footage", "lead": 0.4, "gap": 0.5, "end": 4.5},
    "narration": {"tempo": 1.0},
    "music": {"reference": -18.0, "between": 0.4, "under": 0.2, "ramp": 0.4},
    "audio": {"target": -14.0, "peak": -1.0, "tolerance": 0.3, "margin": 1.5},
    "cuts": {"teaser": False},
    "claims": {"action": "warn"},
    "mark": {"corner": "top-left", "margin": [70, 50], "size": 44, "opacity": 0.9},
    "qa": {"flashes": "error", "flash_threshold": 6.0, "flash_refuse": 40.0},
}
for _table, _keys in DEFAULTS.items():
    for _key, _value in _keys.items():
        _shape = SCHEMA["keys"][_table]["keys"][_key]
        assert typed_ok(_value, _shape["type"]), (_table, _key)
        SCHEMA["keys"][_table]["keys"][_key] = {**_shape, "default": _value}


#: Defaults that differ by source kind (UR59), over DEFAULTS: an explainer's bed sits
#: lower under the voice, as the Japode videos were mixed.
KIND_DEFAULTS = {"explainer": {"music": {"under": 0.07}}}
for _kind, _tables in KIND_DEFAULTS.items():
    for _table, _keys in _tables.items():
        for _key, _value in _keys.items():
            _shape = SCHEMA["keys"][_table]["keys"][_key]
            assert "default" in _shape and typed_ok(_value, _shape["type"])
            _shape.setdefault("by_kind", {})[_kind] = _value


def setting(decl: dict, table: str, key: str):
    """A video.toml value, or the default the schema holds for it (None if none),
    the source kind's own where it has one."""
    if (decl.get(table) or {}).get(key) is None:
        kind = (decl.get("source") or {}).get("kind")
        own = KIND_DEFAULTS.get(kind, {}).get(table, {})
        if key in own:
            return own[key]
    return held(decl.get(table) or {}, SCHEMA["keys"][table], key)


def held(values: dict, shape: dict, key: str):
    """A table's value, or the default its shape holds for the key (None if none);
    a key the shape lacks is a bug, and raises."""
    value = values.get(key)
    if value is not None:
        return value
    default = (shape["keys"][key] or {}).get("default")
    return list(default) if isinstance(default, list) else default


#: The narration script a declaration names (`[narration] script`), UR47.
SCRIPT = table(
    {
        "voice": ANY,
        "voiceName": ANY,
        "narrator": ANY,
        "model": ANY,
        "intro": LANGUAGES,
        "outro": LANGUAGES,
        "introTitle": LANGUAGES,
        "chapters": mapping(
            table({"title": LANGUAGES, "card": LANGUAGES, "result": LANGUAGES})
        ),
        "pronounce": ANY,
        "alignment_aliases": ANY,
        "opening": table({"words_per_minute": ANY, "proof": ANY}),
        "stability": ANY,
        "similarity": ANY,
        "style": ANY,
        "speed": ANY,
    },
    required=("intro", "chapters", "outro"),
)
_MEDIA = table(
    {
        k: ANY
        for k in (
            "file",
            "title",
            "author",
            "url",
            "license",
            "license_url",
            "license_label",
            "plain_background",
            "brand_mark",
            "fit",
            "people",
            "events",
            "categories",
            "topics",
            "section",
            "sha256",
            "retrieved",
            "download_url",
            "rejected",
            "library",
            "candidate",
            "range",
            "kind",
            "screen_recording",
            "source_id",
            "source_offset",
            "changes",
            "copyright",
            "notice",
            "disclaimer",
            "attribution",
            "attribution_required",
            "credit_label",
        )
    }
)
_BEAT = table(
    {
        k: ANY
        for k in (
            "id",
            "title",
            "caption",
            "text",
            "kicker",
            "source",
            "layout",
            "asset",
            "at",
            "weight",
            "seconds",
            "static",
            "from_word",
            "sound",
            "overlay_seconds",
            "brand_mark",
            "presentation",
            "big",
            "quote",
            "by",
            "items",
            "crop",
            "fit",
            "hero",
            "people",
            "events",
            "topics",
            "categories",
            "screen_recording",
            "mark_only",
        )
    }
)
#: What an absent beat key means (UR47): a date card, shown full frame, from the clip's
#: start, weighed like any other beat, moving unless said static.
BEAT_DEFAULTS = {
    "layout": {**TEXT, "default": "date"},
    "presentation": {**TEXT, "default": "full"},
    "at": {**NUMBER, "default": 0},
    "weight": {**NUMBER, "default": 1},
    "static": {**FLAG, "default": False},
}
_BEAT["keys"].update(BEAT_DEFAULTS)
BEAT = _BEAT
#: The storyboard an illustrated source names (`[source] declaration`), UR47.
STORYBOARD = table(
    {
        "title": ANY,
        "description": ANY,
        "credits": ANY,
        "generated": ANY,
        "logo": ANY,
        "brand": ANY,
        "series": ANY,
        "brand_mark": ANY,
        "max_asset_uses": ANY,
        "asset_use_limits": ANY,
        "max_static_seconds": ANY,
        "entities": ANY,
        "pauses": ANY,
        "repetition": ANY,
        "sources": mapping(table({"label": ANY, "url": ANY, "credit_label": ANY})),
        "media": mapping(_MEDIA),
        "scenes": mapping(array(_BEAT)),
    },
    required=("scenes",),
)


#: The cards declaration (`[cards] declaration`): the theme and the words, UR47.
CARDS = table(
    {
        "theme": table(
            {
                "name": ANY,
                "source": ANY,
                "palette": ANY,
                "background": ANY,
                "colors": mapping(ANY),
                "fonts": table({"dir": ANY, "display": ANY, "text": ANY}),
                "glow": table({"color": ANY, "landscape": ANY, "portrait": ANY}),
                "ridges": table({"far": ANY, "near": ANY, "height": ANY, "drift": ANY}),
            }
        ),
        "words": mapping(ANY),
    },
    required=("theme",),
)
#: The highlights declaration (`[highlights] declaration`), UR47.
HIGHLIGHTS = table(
    {
        # `margin`: px from the bottom edge at 1080p, lifting the highlights clear of a
        # player's captions (VM48); 85 keeps the earlier videos unchanged.
        "style": table(
            {"font": ANY, "color": ANY, "margin": {**NUMBER, "default": 85}}
        ),
        "lines": mapping(
            array(
                table(
                    {
                        "show": ANY,
                        "hear": ANY,
                        "duration": {**NUMBER, "default": 2.8},
                        "look": ANY,
                    },
                    required=("show",),
                )
            )
        ),
    }
)
#: An explainer's shots (`[source] shots`), UR47: per take, the shots under its line
#: (a shot with no `dur` shares what the fixed ones leave), and the keywords that pop
#: in when the take says them.
SHOT = table(
    {
        "src": TEXT,
        "at": NUMBER,
        "dur": NUMBER,
        "speed": {**NUMBER, "default": 1.0},
        "box": LIST,
    },
    required=("src", "at"),
)
SHOTS = table(
    {
        "title": ANY,
        "about": ANY,
        "callouts_about": ANY,
        "segments": array(
            table({"take": TEXT, "shots": array(SHOT)}, required=("take", "shots"))
        ),
        "callouts": mapping(
            array(table({"show": TEXT, "hear": TEXT, "def": TEXT}, required=("show",)))
        ),
    },
    required=("title", "segments"),
)
#: One highlight line, whose `duration` defaults in the schema (UR47).
HIGHLIGHT_LINE = HIGHLIGHTS["keys"]["lines"]["map"]["array"]
#: The claims declaration (`[claims] declaration`), UR47.
CLAIMS = table(
    {
        "version": ANY,
        "claims": array(
            table(
                {
                    k: ANY
                    for k in (
                        "id",
                        "take",
                        "language",
                        "text",
                        "anchor",
                        "kind",
                        "evidence",
                        "illustrations",
                        "review",
                        "reviews",
                    )
                }
            )
        ),
    },
    required=("version", "claims"),
)


def side_files(decl: dict) -> list[tuple[str, dict]]:
    """The side files a declaration names that have a schema: (declared path, shape)."""
    found = []
    translations = ((decl.get("captions") or {}).get("translations") or {}).values()
    for spec in translations:
        if isinstance(spec, dict) and isinstance(spec.get("file"), str):
            # a translation table: each take's sentences, in the take's order
            found.append((spec["file"], mapping(LIST)))
    for name, shape in (
        ("cards", CARDS),
        ("highlights", HIGHLIGHTS),
        ("claims", CLAIMS),
    ):
        declared = (decl.get(name) or {}).get("declaration")
        if isinstance(declared, str):
            found.append((declared, shape))
    script = (decl.get("narration") or {}).get("script")
    if isinstance(script, str):
        found.append((script, SCRIPT))
    source = decl.get("source") or {}
    if source.get("kind") == "illustrated" and isinstance(
        source.get("declaration"), str
    ):
        found.append((source["declaration"], STORYBOARD))
    if source.get("kind") == "explainer" and isinstance(source.get("shots"), str):
        found.append((source["shots"], SHOTS))
    return found


def check_side_files(decl: dict, resolve) -> list[str]:
    """Every problem inside the side files a declaration names, each with its file.

    `resolve(declared)` turns a declared path into a file; a file that is not there is
    left for the build to report, which says what made it."""
    found: list[str] = []
    for declared, shape in side_files(decl):
        try:
            path = Path(resolve(declared))
        except Exception as unresolved:  # an undeclared root: the build names it
            found.append(f"{declared}: {unresolved}")
            continue
        if not path.is_file():
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError as broken:
            found.append(f"{path}: is not JSON ({broken})")
            continue
        walk(document, shape, str(path), "", found)
    return found


#: What a source kind cannot build without.
KIND_NEEDS = {
    "chaptered": ("folder", "recording", "chapters"),
    "scenes": ("listing",),
    "illustrated": ("declaration",),
    "explainer": ("shots",),
}

#: The `[shorts]` keys a scenes build's `--cut short:<c>` reads; every other key there
#: is `urdido shorts`'s, and one table holds one cutter's keys (UR48).
SELECTION_KEYS = ("declaration",)


def shorts_cutter(shorts: dict) -> str | None:
    """Which cutter a `[shorts]` table declares, or None when it is empty."""
    if not shorts:
        return None
    return "selection" if set(shorts) <= set(SELECTION_KEYS) else "urdido shorts"


def check_shorts(shorts, file: str) -> list[str]:
    """A `[shorts]` that mixes the selection's keys with `urdido shorts`' is refused."""
    if not isinstance(shorts, dict):
        return []
    selection = [k for k in shorts if k in SELECTION_KEYS]
    others = [k for k in shorts if k not in SELECTION_KEYS]
    if not (selection and others):
        return []
    return [
        f"{file} [shorts]: {', '.join(selection)} is a scenes build's selection "
        f"(--cut short:<c>) and {', '.join(others)} belong to urdido shorts; "
        "one [shorts] table declares one cutter"
    ]


#: What each table is for, in one line, for the reference (UR35).
PURPOSE = {
    "video": "The video's name, its languages and, for a variant, its base.",
    "roots": "Folders a `<name>` path starts at, by relative path or `$VAR`.",
    "output": "Where the build writes: `folder` (`video`) and `parts` inside it.",
    "source": "What the video is made of: its `kind` and what that kind reads.",
    "narration": "The script, the folder of bought takes, and an optional tempo.",
    "cards": "The cards' declaration (theme and words), and a browser channel.",
    "music": "The bed under the narration and how far it ducks.",
    "audio": "Loudness target, true-peak ceiling and their margin.",
    "opening": "A chaptered video's opening: animation, footage, photos, site screens.",
    "cuts": "Which extra cuts a chaptered build makes.",
    "captions": "Translated captions, burned-in captions and the player's safe area.",
    "highlights": "Word-timed callouts over the picture, and their fonts.",
    "claims": "The narration's claims, their evidence and how strictly they are held.",
    "description": "The YouTube description: summary, notes, sources, licence, words.",
    "text_checks": "Encoding, glyph and layout checks over the text a video draws.",
    "mark": "A brand mark in a corner through the whole video.",
    "anchors": "Named moments a scene can be timed against.",
    "qa": "How the final verification treats a flash.",
    "publish": "Where the transcript and stills are published.",
    "resolve": "The DaVinci Resolve project's settings.",
    "thumbnail": "The thumbnail: layout, pictures, words, published title, pair check.",
    "shorts": "YouTube Shorts: the scenes selection, or `urdido shorts` cuts.",
    "record": "The steps `urdido record` runs to record a scene video.",
    "instances": "Product instances a recording runs against, by name.",
    "terminal": "A terminal scene's commands, run for real by `urdido terminal`.",
}


def reference() -> str:
    """The declaration reference, from the schema (`docs/specs/declaration.md`)."""

    def keys_of(shape) -> list[str]:
        if shape is ANY:
            return []
        if "type" in shape:
            if "default" in shape:
                kinds = "".join(
                    f", {json.dumps(v)} for {k}"
                    for k, v in shape.get("by_kind", {}).items()
                )
                default = json.dumps(shape["default"])
                return [f"a {shape['type']}, {default} if absent{kinds}"]
            return [f"a {shape['type']}"]
        if "array" in shape:
            return keys_of(shape["array"])
        if "map" in shape:
            return ["*any name*"]
        required = set(shape["required"])
        return [
            f"`{k}`" + (" (required)" if k in required else "") for k in shape["keys"]
        ]

    out = [
        "# The declaration",
        "",
        "Generated by `urdido check --reference` from the schema in",
        "`src/urdido/declaration.py`; do not edit it by hand.",
        "",
        "A video is one `video.toml`. `urdido check <video.toml>` refuses a key no",
        "table takes, with the nearest valid name, and `urdido build` runs the same",
        "check first.",
        "`urdido check --schema` prints the JSON Schema an editor can complete from.",
        "",
        "## Source kinds",
        "",
    ]
    out += [
        f"- `{kind}` needs " + ", ".join(f"`{k}`" for k in needs)
        for kind, needs in KIND_NEEDS.items()
    ]
    out += [
        "",
        "## Shorts cutters",
        "",
        "`[shorts]` declares one of two cutters, never both:",
        "",
        "- the scenes selection, cut by `urdido build --cut short:<c>`: "
        + ", ".join(f"`{k}`" for k in SELECTION_KEYS)
        + " and nothing else;",
        "- `urdido shorts`: every other key in the table below.",
    ]
    for name, shape in SCHEMA["keys"].items():
        out += ["", f"## [{name}]", "", PURPOSE.get(name, ""), ""]
        if shape is ANY or "map" in shape:
            out.append("Any key, each a name of your own.")
            continue
        for key, sub in shape["keys"].items():
            mark = " (required)" if key in shape["required"] else ""
            inner = keys_of(sub)
            out.append(f"- `{key}`{mark}" + (": " + ", ".join(inner) if inner else ""))
    return "\n".join(out).rstrip() + "\n"


def check_document(document: dict, path: Path) -> list[str]:
    """Every problem in a read declaration, then in the side files it names.

    The side files are checked only once the declaration passes, through the roots it
    declares; a root read from the environment is not resolved here."""
    problems = check(document, str(path))
    if problems:
        return problems
    from urdido.project import roots_of

    here = path.resolve().parent
    roots = roots_of(here, document, env={})

    def resolve(declared: str) -> Path:
        for name, root in roots.items():
            if declared.startswith(f"<{name}>"):
                return Path(declared.replace(f"<{name}>", root))
        if declared.startswith("<"):
            raise ValueError("starts at a root this check cannot resolve")
        return here / declared

    return check_side_files(document, resolve)


def check_file(path: str | Path) -> list[str]:
    """Every problem in a video.toml and its side files; empty when it passes (UR49).

    An unreadable file or bad TOML is refused as a `DeclarationError`."""
    path = Path(path)
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, tomllib.TOMLDecodeError) as unreadable:
        from urdido.errors import DeclarationError

        raise DeclarationError(f"{path}: {unreadable}") from None
    return check_document(document, path)


def check(document: dict, file: str = "video.toml") -> list[str]:
    """Every problem in a declaration, each naming its file and table."""
    found: list[str] = []
    walk(document, SCHEMA, file, "", found)
    source = document.get("source")
    if isinstance(source, dict) and "kind" in source:
        from urdido.pipelines import kinds

        kind = source["kind"]
        known = kinds()
        if kind not in known:
            found.append(
                f"{file} [source]: kind is {kind!r}; it is one of "
                + ", ".join(sorted(known))
            )
        else:
            for key in KIND_NEEDS.get(kind, ()):
                if key not in source:
                    found.append(f"{file} [source]: a {kind} source needs {key}")
    found += check_shorts(document.get("shorts"), file)
    return found


def walk(value, shape, file: str, where: str, found: list[str]) -> None:
    if shape is ANY:
        return
    label = f"[{where}]" if where else "the top level"
    if "type" in shape:
        if not typed_ok(value, shape["type"]):
            found.append(
                f"{file} {label}: is {value!r}, and it takes a {shape['type']}"
            )
        return
    if "array" in shape:
        if not isinstance(value, list):
            found.append(f"{file} {label}: is a list of tables")
            return
        for item in value:
            walk(item, shape["array"], file, where, found)
        return
    if not isinstance(value, dict):
        found.append(f"{file} {label}: is a table")
        return
    if "map" in shape:
        for name, item in value.items():
            if name == "_" and isinstance(item, str):
                continue  # a note for the reader, as the translation tables carry
            walk(item, shape["map"], file, f"{where}.{name}" if where else name, found)
        return
    keys = shape["keys"]
    for key, item in value.items():
        if key not in keys:
            near = get_close_matches(key, list(keys), n=1, cutoff=0.6)
            hint = (
                f"; did you mean {near[0]}?"
                if near
                else f"; it takes {', '.join(keys)}"
            )
            found.append(f"{file} {label}: unknown key {key}{hint}")
            continue
        walk(item, keys[key], file, f"{where}.{key}" if where else key, found)
    for key in shape["required"]:
        if key not in value:
            found.append(f"{file} {label}: needs {key}")


def json_schema(shape=SCHEMA):
    """The schema as JSON Schema (draft 2020-12), for editors and the reference docs."""
    if shape is ANY:
        return {}
    if "type" in shape:
        return {k: shape[k] for k in ("type", "default") if k in shape}
    if "array" in shape:
        return {"type": "array", "items": json_schema(shape["array"])}
    if "map" in shape:
        return {"type": "object", "additionalProperties": json_schema(shape["map"])}
    out = {
        "type": "object",
        "additionalProperties": False,
        "properties": {key: json_schema(item) for key, item in shape["keys"].items()},
    }
    if shape["required"]:
        out["required"] = list(shape["required"])
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="urdido check")
    p.add_argument("declaration", nargs="?")
    p.add_argument("--schema", action="store_true", help="print the JSON Schema")
    p.add_argument("--reference", action="store_true", help="print the reference")
    args = p.parse_args(argv)
    if args.reference:
        sys.stdout.write(reference())
        return 0
    if args.schema:
        document = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "urdido video.toml",
            **json_schema(),
        }
        print(json.dumps(document, indent=2))
        return 0
    if not args.declaration:
        p.error("name a video.toml, or ask for --schema")
    path = Path(args.declaration)
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, tomllib.TOMLDecodeError) as unreadable:
        print(f"{path}: {unreadable}", file=sys.stderr)
        return 1
    problems = check_document(document, path)
    for problem in problems:
        print(problem, file=sys.stderr)
    if not problems:
        print(f"{path}: passes")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
