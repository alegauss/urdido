"""VM43: temporal label conflicts; PW709 tracks a reusable check in the provider."""
from __future__ import annotations

import warnings

from urdido.keywords import fold
from urdido.sources.model import RecordingRefused


def check(document: dict, edit: dict, highlights: list[dict], opening: float = 0) -> list[str]:
    beats = {f"{take}-{i}": beat for take, items in document["scenes"].items()
             for i, beat in enumerate(items)}
    errors, notes = [], []
    for cue in highlights:
        touched = []
        for shot in edit["beats"]:
            start = opening + shot["at"]
            end = start + shot["seconds"]
            if cue["at"] >= end or cue["end"] <= start:
                continue
            touched.append(shot["beat"])
            beat = beats[shot["beat"]]
            caption = " ".join(str(t) for t in (beat.get("caption", beat["title"]), beat.get("text", ""))).strip()
            full = beat.get("layout") in {"footage", "picture"} and beat.get("presentation", "full") == "full"
            visible_end = min(end, start + beat["overlay_seconds"]) if full and beat.get("overlay_seconds") else end
            if caption and cue["at"] < visible_end:
                errors.append(f"{shot['beat']}: highlight {cue['show']!r} overlaps beat caption {caption!r} "
                              f"at {max(start, cue['at']):.3f}s")
            asset = document.get("media", {}).get(beat.get("asset"), {})
            for kind, plural in (("person", "people"), ("event", "events")):
                entity = cue.get(kind)
                if not entity and document.get("entities", {}).get(cue["show"]) == kind:
                    entity = cue["show"]
                if entity:
                    declared = beat.get(plural, asset.get(plural, []))
                    declared = [declared] if isinstance(declared, str) else declared
                    if fold(entity) not in {fold(name) for name in declared}:
                        notes.append(f"{shot['beat']}: {kind} {entity!r} is not verified by the asset's {plural}; review the source")
        if len(touched) > 1:
            notes.append(f"highlight {cue['show']!r} crosses beats {', '.join(touched)}; review its end time")
    for note in notes:
        warnings.warn(note, UserWarning, stacklevel=2)
    if errors:
        raise RecordingRefused("label conflicts:\n" + "\n".join(errors))
    return notes
