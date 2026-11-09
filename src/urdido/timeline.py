"""The timeline as OpenTimelineIO (VM7), in place of story-video.mjs's module globals.

One video's cut is an OTIO `Timeline`. Its video tracks follow the JS assembly's lanes: V1 the
recording and its held frames, V2 the cards, V3 the opening and the shots. A piece plays where the
pieces before it end, on its own lane, with gaps on the others; its encoded file, whether it is a
still, the chapter it cuts and its dissolves ride in the clip's `videomaker` metadata. Audio
tracks hold each language's takes (`A1 <language>`), the sounds that come with the picture (`A3`)
and the music bed (`A2`, its trim, duck and loudness in metadata). Chapters are markers.

`plan(timeline)` derives VM1's plan JSON from it, so the golden plans stay the oracle. Times are
seconds at 30 fps; `plan()` rounds them to the millisecond as `writePlan` does.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import opentimelineio as otio

# Times are kept in seconds at the video's frame rate, so editors read a timecode; plan() rounds
# them back to the millisecond.
RATE = 30.0
LANES = ("V1", "V2", "V3")
KEY = "videomaker"


def _time(seconds: float) -> otio.opentime.RationalTime:
    return otio.opentime.RationalTime(seconds * RATE, RATE)


def _range(start: float, length: float) -> otio.opentime.TimeRange:
    return otio.opentime.TimeRange(_time(start), _time(length))


def _js_fixed3(x: float) -> float:
    """Number(x.toFixed(3)), as writePlan rounds every non-integer."""
    return float(f"{x:.3f}") if not float(x).is_integer() else x


def _rounded(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        r = _js_fixed3(value)
        return int(r) if float(r).is_integer() else r
    if isinstance(value, Mapping):
        return {k: _rounded(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_rounded(v) for v in value]
    return value


class Builder:
    """Composes a timeline piece by piece, each one after the last, as the JS `place()` did."""

    def __init__(self, video: str, language: str, width: int, height: int, **extra: Any):
        self.timeline = otio.schema.Timeline(name=video)
        self.timeline.metadata[KEY] = {
            "video": video, "language": language, "size": {"width": width, "height": height}, "extra": dict(extra),
        }
        self.lanes = {}
        for lane in LANES:
            track = otio.schema.Track(name=lane, kind=otio.schema.TrackKind.Video)
            self.timeline.tracks.append(track)
            self.lanes[lane] = track
        self.clock = 0.0
        self._ends = {lane: 0.0 for lane in LANES}
        self._audio: dict[str, otio.schema.Track] = {}
        self._audio_ends: dict[str, float] = {}

    # -- picture -------------------------------------------------------------------------------

    def _piece(self, lane: str | None, source: str | None, at: float | None, file: str, length: float,
               **meta: Any) -> otio.schema.Clip:
        """One piece of picture, from `at` in `source`, played next on `lane`."""
        track = self.lanes[lane or "V1"]
        gap = self.clock - self._ends[lane or "V1"]
        if gap > 0:
            track.append(otio.schema.Gap(source_range=_range(0, gap)))
        clip = otio.schema.Clip(
            name=file.rsplit("/", 1)[-1],
            media_reference=otio.schema.ExternalReference(target_url=source or file),
            source_range=_range(at or 0, length),
        )
        clip.metadata[KEY] = {
            "file": file, "lane": lane, "source": source, "at": at,
            **{k: v for k, v in meta.items() if v is not None},
        }
        track.append(clip)
        self.clock += length
        self._ends[lane or "V1"] = self.clock
        return clip

    def card(self, still: str, file: str, length: float) -> otio.schema.Clip:
        """A card, its still held (or moving in parallax) for `length` s, on V2."""
        return self._piece("V2", still, 0, file, length, still=True)

    def held(self, still: str, file: str, length: float) -> otio.schema.Clip:
        """A frame of the recording held still, on V1."""
        return self._piece("V1", still, 0, file, length, still=True)

    def chapter(self, recording: str, at: float, chapter: int, in_chapter: float, file: str,
                length: float) -> otio.schema.Clip:
        """A stretch of a chapter's recording: `at` s into the recording, `in_chapter` s into the
        chapter (where its push-ins and time maps are read), on V1."""
        return self._piece("V1", recording, at, file, length, chapter=chapter, inChapter=in_chapter)

    def shots(self, files: Sequence[tuple[str, float]]) -> list[otio.schema.Clip]:
        """Shots played as they are (the opening, b-roll), on V3."""
        return [self._piece("V3", file, 0, file, length) for file, length in files]

    def scene(self, clip: str, file: str, length: float, clip_seconds: float, speed: float,
              hold: float) -> otio.schema.Clip:
        """A scene clip fitted to its lines (VM10), on V1: the whole clip at `speed` (an OTIO
        time warp), then its last frame held `hold` s."""
        # The source range stays the span on the timeline (OTIO times a track by it, not by its
        # effects); the clip's own length rides in the metadata beside the warp.
        piece = self._piece("V1", clip, 0, file, length,
                            fit={"speed": speed, "hold": hold, "clip": clip_seconds})
        piece.effects.append(otio.schema.LinearTimeWarp(name="fit", time_scalar=speed))
        if hold > 0:
            piece.effects.append(otio.schema.FreezeFrame(name="hold"))
        return piece

    def part(self, file: str, length: float) -> otio.schema.Clip:
        """A piece a chapter clip joins as it is, with no lane of its own."""
        return self._piece(None, None, None, file, length)

    def effect(self, clip: otio.schema.Clip, name: str, parameters: Mapping[str, Any]) -> None:
        """An effect a piece carries with its parameters (a push-in's windows, a time map's
        stretches), for an export or a renderer to read; the plan does not record it."""
        effect = otio.schema.Effect(name=name, effect_name=f"videomaker.{name}")
        effect.metadata[KEY] = dict(parameters)
        clip.effects.append(effect)

    def dissolve(self, clip: otio.schema.Clip, into: str | None = None, out_of: str | None = None) -> None:
        """What a piece dissolves from (`out_of`, the still it fades out of) and into."""
        clip.metadata[KEY]["dissolve"] = {"out": out_of, "in": into}

    # -- sound ---------------------------------------------------------------------------------

    def _audio_track(self, name: str) -> otio.schema.Track:
        if name not in self._audio:
            track = otio.schema.Track(name=name, kind=otio.schema.TrackKind.Audio)
            self.timeline.tracks.append(track)
            self._audio[name] = track
            self._audio_ends[name] = 0.0
        return self._audio[name]

    def _sound_at(self, track_name: str, at: float, source: str, source_at: float, length: float,
                  **meta: Any) -> otio.schema.Clip:
        track = self._audio_track(track_name)
        gap = at - self._audio_ends[track_name]
        if gap > 0:
            track.append(otio.schema.Gap(source_range=_range(0, gap)))
        clip = otio.schema.Clip(
            name=source.rsplit("/", 1)[-1],
            media_reference=otio.schema.ExternalReference(target_url=source),
            source_range=_range(source_at, length),
        )
        clip.metadata[KEY] = {"at": at, **meta}
        track.append(clip)
        self._audio_ends[track_name] = at + length
        return clip

    def say(self, language: str, at: float, take: str, length: float, text: str) -> otio.schema.Clip:
        """A narration take, heard from `at` s into the video."""
        self._audio_track(f"A1 {language}")
        return self._sound_at(f"A1 {language}", at, take, 0, length, text=text)

    def speaks(self, language: str) -> None:
        """A language the video is narrated in, even with no take placed yet."""
        self._audio_track(f"A1 {language}")

    def sound(self, file: str, source_at: float, at: float, length: float) -> otio.schema.Clip:
        """Sound that comes with a piece of picture (the opening's own), on A3."""
        return self._sound_at("A3", at, file, source_at, length, sound=True)

    def bed(self, music: Mapping[str, Any] | None) -> None:
        """The music bed, its trim, duck, loudness and each language's envelope (VM5)."""
        self.timeline.metadata[KEY]["music"] = dict(music) if music is not None else None

    def finish(self) -> otio.schema.Timeline:
        """Every track padded to where the video ends, as an editor expects."""
        end = max(track.duration() for track in self.timeline.tracks)
        for track in self.timeline.tracks:
            # In OTIO's own time arithmetic, so every track ends on exactly the same time.
            rest = end - track.duration()
            if rest.value > 0:
                track.append(otio.schema.Gap(source_range=otio.opentime.TimeRange(_time(0), rest)))
        return self.timeline

    def cue(self, start: float, end: float, chapter: int) -> None:
        """A chapter as it shows: a marker over its span."""
        marker = otio.schema.Marker(name=f"chapter {chapter + 1}", marked_range=_range(start, end - start))
        marker.metadata[KEY] = {"chapter": chapter}
        self.timeline.tracks.markers.append(marker)


# -- the plan ----------------------------------------------------------------------------------


def _placed(track: otio.schema.Track):
    """Each clip of a track with where it starts in the timeline."""
    clock = 0.0
    for item in track:
        length = item.source_range.duration.to_seconds()
        if isinstance(item, otio.schema.Clip):
            yield clock, item
        clock += length


def pieces(timeline: otio.schema.Timeline) -> list[str]:
    """The encoded files of every piece of picture, in the order they play: across the lanes,
    by where each starts, never one lane after another."""
    placed = [(start, clip) for track in timeline.video_tracks() for start, clip in _placed(track)]
    return [clip.metadata[KEY]["file"] for _, clip in sorted(placed, key=lambda p: p[0])]


def plan(timeline: otio.schema.Timeline) -> dict:
    """VM1's plan JSON, derived from the timeline (keys in writePlan's order)."""
    meta = timeline.metadata[KEY]
    pieces = []
    for track in timeline.video_tracks():
        for start, clip in _placed(track):
            pieces.append((start, clip))
    pieces.sort(key=lambda p: p[0])
    # OTIO's metadata keeps a dictionary's keys in an order of its own: writePlan's is restored here.
    out: dict[str, Any] = {"video": meta["video"], "language": meta["language"],
                           "size": {"width": meta["size"]["width"], "height": meta["size"]["height"]}}
    extra = dict(meta.get("extra", {}))
    if "chapter" in extra:
        out["chapter"] = extra.pop("chapter")
        out["speed"] = extra.pop("speed", 1)
    rows, dissolves = [], []
    for _, clip in pieces:
        m = clip.metadata[KEY]
        length = clip.source_range.duration.to_seconds()
        if m.get("lane") is None:
            rows.append({"file": m["file"], "length": length})
        else:
            row = {"track": m["lane"], "source": m["source"], "at": m["at"]}
            if m.get("still"):
                row["still"] = True
            if "chapter" in m:
                row["chapter"] = m["chapter"]
                row["inChapter"] = m["inChapter"]
            row["file"] = m["file"]
            row["length"] = length
            rows.append(row)
        if "dissolve" in m:
            dissolves.append({"out": m["dissolve"]["out"], "in": m["dissolve"]["in"]})
    out["pieces"] = rows
    if "chapter" not in out:
        out["dissolves"] = dissolves
        out["total"] = sum(r["length"] for r in rows)
    spoken: dict[str, list] = {}
    sounds: list = []
    for track in timeline.audio_tracks():
        if track.name.startswith("A1 "):
            spoken[track.name[3:]] = [
                {"at": c.metadata[KEY]["at"], "file": c.media_reference.target_url,
                 "length": c.source_range.duration.to_seconds(), "text": c.metadata[KEY]["text"]}
                for _, c in _placed(track)
            ]
        elif track.name == "A3":
            sounds = [
                {"file": c.media_reference.target_url, "from": c.source_range.start_time.to_seconds(),
                 "at": c.metadata[KEY]["at"], "length": c.source_range.duration.to_seconds()}
                for _, c in _placed(track)
            ]
    out["spoken"] = spoken
    out["cues"] = [
        {"from": mk.marked_range.start_time.to_seconds(),
         "to": mk.marked_range.start_time.to_seconds() + mk.marked_range.duration.to_seconds(),
         "chapter": mk.metadata[KEY]["chapter"]}
        for mk in timeline.tracks.markers
    ]
    if "chapter" not in out:
        out["sounds"] = sounds
    out["music"] = _music(meta.get("music"))
    return _rounded(out)


def _music(music: Mapping | None) -> dict | None:
    """The bed as story-video.mjs's musicPlan orders it."""
    if music is None:
        return None
    order = ("file", "from", "trimDb", "volume", "duck", "loudness", "envelope")
    out = {k: music[k] for k in order if k in music}
    if "duck" in out:
        out["duck"] = {k: out["duck"][k] for k in ("between", "ramp") if k in out["duck"]}
    if "loudness" in out:
        out["loudness"] = {k: out["loudness"][k] for k in ("target", "peak") if k in out["loudness"]}
    if "envelope" in out:
        out["envelope"] = dict(out["envelope"])
    out.update({k: v for k, v in music.items() if k not in out})
    return out


def from_plan(data: Mapping[str, Any]) -> otio.schema.Timeline:
    """A plan read back into a timeline through the builder: the round trip that proves the
    timeline carries everything the plan says."""
    extra = {k: data[k] for k in ("chapter", "speed") if k in data}
    b = Builder(data["video"], data["language"], data["size"]["width"], data["size"]["height"], **extra)
    dissolves = data.get("dissolves")
    for n, piece in enumerate(data["pieces"]):
        lane = piece.get("track")
        if lane is None:
            clip = b.part(piece["file"], piece["length"])
        elif "chapter" in piece:
            clip = b.chapter(piece["source"], piece["at"], piece["chapter"], piece["inChapter"],
                             piece["file"], piece["length"])
        elif piece.get("still"):
            if lane not in ("V1", "V2"):
                raise ValueError(f"a still on {lane}")
            make = b.card if lane == "V2" else b.held
            clip = make(piece["source"], piece["file"], piece["length"])
        else:
            (clip,) = b.shots([(piece["file"], piece["length"])])
            if piece["source"] != piece["file"] or piece["at"] != 0 or lane != "V3":
                raise ValueError(f"a shot that is not played as it is: {piece}")
        if dissolves is not None:
            b.dissolve(clip, into=dissolves[n]["in"], out_of=dissolves[n]["out"])
    for language, placed in data["spoken"].items():
        b.speaks(language)
        for take in placed:
            b.say(language, take["at"], take["file"], take["length"], take["text"])
    for sound in data.get("sounds") or []:
        b.sound(sound["file"], sound["from"], sound["at"], sound["length"])
    for cue in data["cues"]:
        b.cue(cue["from"], cue["to"], cue["chapter"])
    b.bed(data.get("music"))
    return b.finish()


def write(timeline: otio.schema.Timeline, path: str) -> None:
    otio.adapters.write_to_file(timeline, path)


def read(path: str) -> otio.schema.Timeline:
    return otio.adapters.read_from_file(path)
