"""One language's narration mixed over the music bed, to a loudness target (VM5).

Ported from the first demo's `story-video.mjs` (`ducked`, `musicGain`, `duckExpression`,
`musicTrim`, `voiceTrack`). Nothing here is the WordPress demo's: the duck, the bed (its file,
where it starts, the level it is trimmed to), the sounds that come with pieces of picture and the
loudness target are arguments, so the Viglet Shio long cut and each short cut bring their own.
The defaults are the levels the WordPress demo was tuned to (D291).

The render keeps ffmpeg's filters; whether MLT's replace them is VM24's question.
"""

from __future__ import annotations

import math
import os
import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field

from urdido import media
from urdido.declaration import DEFAULTS


def _num(x: float) -> str:
    """A number as JavaScript prints it in a template: 1 not 1.0, 0.4 as 0.4."""
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def _ms(seconds: float) -> int:
    """Math.round(seconds * 1000): halves go up."""
    return math.floor(seconds * 1000 + 0.5)


@dataclass(frozen=True)
class Duck:
    """The bed's level: `between` lines, `under` each, with a `ramp` either side (gains, s)."""

    between: float = DEFAULTS["music"]["between"]
    under: float = DEFAULTS["music"]["under"]  # an explainer's is lower (KIND_DEFAULTS)
    ramp: float = DEFAULTS["music"]["ramp"]


@dataclass(frozen=True)
class Bed:
    """The music under the voice: looped from `start` (where the opening's own sound ends) to the
    end, brought to `reference` LUFS before the duck, so a louder master sits no louder."""

    file: str
    start: float = 0.0
    reference: float = DEFAULTS["music"]["reference"]


@dataclass(frozen=True)
class Sound:
    """Sound that comes with a piece of picture: `length` s of `file` from `source_at`, at `at`."""

    file: str
    source_at: float
    at: float
    length: float
    gain_db: float = 0.0  # a clip's own level, e.g. a loud meme brought down (VM78)


@dataclass(frozen=True)
class Loudness:
    """The mix's target: YouTube's playback level with a true-peak ceiling."""

    target: float = DEFAULTS["audio"]["target"]
    peak: float = DEFAULTS["audio"]["peak"]
    tolerance: float = DEFAULTS["audio"]["tolerance"]
    # AAC overshoots the limiter's sample peaks (a limit at -2.5 dBFS encoded to -1.1 dBTP).
    margin: float = DEFAULTS["audio"]["margin"]


@dataclass(frozen=True)
class Take:
    file: str
    at: float
    length: float


def takes_of(placed: Sequence[Mapping]) -> list[Take]:
    """A plan's placed takes (`spoken[language]`) as Takes."""
    return [Take(p["file"], p["at"], p["length"]) for p in placed]


def ducked(placed: Sequence[Take], t: float, duck: Duck = Duck()) -> float:
    """How far the music is pulled down at a moment, 0 to 1: a take's span with its ramps."""
    return max(
        [0.0]
        + [
            min(
                1.0,
                max(
                    0.0,
                    min(
                        (t - p.at + duck.ramp) / duck.ramp,
                        (p.at + p.length + duck.ramp - t) / duck.ramp,
                    ),
                ),
            )
            for p in placed
        ]
    )


def music_gain(placed: Sequence[Take], t: float, duck: Duck = Duck()) -> float:
    """The music's gain at a moment, as `ducked()` sets it."""
    return duck.between - (duck.between - duck.under) * ducked(placed, t, duck)


def duck_expression(placed: Sequence[Take], duck: Duck = Duck()) -> str:
    """`music_gain()` as an ffmpeg expression in `t`, for the volume filter (single-quoted in the
    filtergraph, so its commas need no escaping)."""
    ramp = _num(duck.ramp)
    dips = [
        f"clip(min((t-{p.at - duck.ramp:.3f})/{ramp},({p.at + p.length + duck.ramp:.3f}-t)/{ramp}),0,1)"
        for p in placed
    ]
    dip = dips[0] if dips else "0"
    for d in dips[1:]:
        dip = f"max({dip},{d})"
    return f"{_num(duck.between)}-{duck.between - duck.under:.3f}*({dip})"


def on_bed(placed: Sequence[Take], bed: Bed) -> list[Take]:
    """The takes in the bed's own time, which starts at `bed.start`."""
    return [Take(p.file, p.at - bed.start, p.length) for p in placed]


_SILENCE = re.compile(r"silence_(start|end): (-?[\d.]+)")


def audible_end(log: str, duration: float, tail: float = 0.25) -> float:
    """Where a track's music stops: the start of a silence that runs to the file's end (a fade
    and the empty seconds a licensed track ends on), else the file's whole length (VM49)."""
    start = None
    for kind, value in _SILENCE.findall(log):
        if kind == "start":
            start = float(value)
        elif start is not None and float(value) < duration - tail:
            start = None
    return start if start is not None and start > 0 else duration


def seamless_bed(bed: Bed, total: float, work_dir: str, crossfade: float = 3.0) -> Bed:
    """The bed as one gapless track at least the video's length: its trailing silence cut and its
    repeats joined by a crossfade, so looping never drops the music out (VM49)."""
    duration = media.seconds(bed.file)
    log = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            bed.file,
            "-af",
            "silencedetect=noise=-40dB:d=0.5",
            "-f",
            "null",
            "-",
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stderr
    end = audible_end(log, duration)
    need = total - bed.start
    if end >= duration - 0.25 and duration >= need:
        return bed  # plays once, with no silent tail to skip
    usable = max(end - crossfade, 1.0)
    copies = max(2, math.ceil((need - crossfade) / usable) + 1)
    inputs = [
        arg for _ in range(copies) for arg in ("-t", f"{end:.3f}", "-i", bed.file)
    ]
    chain, last = [], "[0:a]"
    for n in range(1, copies):
        out = f"[x{n}]"
        chain.append(f"{last}[{n}:a]acrossfade=d={_num(crossfade)}:c1=tri:c2=tri{out}")
        last = out
    out_file = os.path.join(work_dir, "bed.seamless.wav")
    media.ffmpeg([*inputs, "-filter_complex", ";".join(chain), "-map", last, out_file])
    return Bed(out_file, bed.start, bed.reference)


def bed_trim(bed: Bed) -> float:
    """The gain, in dB, that brings the bed to its reference level; 0 when it cannot be read."""
    measured = media.measure_loudness(
        ["-i", bed.file, "-af", "loudnorm=print_format=json"]
    )
    try:
        value = float(measured["input_i"])
    except (KeyError, ValueError):
        return 0.0
    return round(bed.reference - value, 2) if math.isfinite(value) else 0.0


@dataclass(frozen=True)
class Graph:
    """ffmpeg's inputs and filtergraph for a mix, its output labelled `[mix]`."""

    inputs: list[str]
    filters: list[str] = field(default_factory=list)

    @property
    def filter_complex(self) -> str:
        return ";".join(self.filters)


def mix_graph(
    placed: Sequence[Take],
    total: float,
    sounds: Sequence[Sound] = (),
    bed: Bed | None = None,
    trim_db: float = 0.0,
    duck: Duck = Duck(),
) -> Graph:
    """The takes delayed to where they play, the sounds, and the ducked, faded, looped bed,
    mixed without normalising and padded to the video's length."""
    inputs = [arg for p in placed for arg in ("-i", p.file)]
    graph = [f"[{i}:a]adelay={_ms(p.at)}:all=1[d{i}]" for i, p in enumerate(placed)]
    labels = "".join(f"[d{i}]" for i in range(len(placed)))
    count = len(placed)
    for n, sound in enumerate(sounds):
        inputs += [
            "-ss",
            f"{sound.source_at:.3f}",
            "-t",
            f"{sound.length:.3f}",
            "-i",
            sound.file,
        ]
        level = f"volume={_num(sound.gain_db)}dB," if sound.gain_db else ""
        graph.append(
            f"[{count}:a]{level}afade=t=out:st={max(0, sound.length - 0.6):.3f}:d=0.6,"
            f"adelay={_ms(sound.at)}:all=1[s{n}]"
        )
        labels += f"[s{n}]"
        count += 1
    if bed is not None:
        length = total - bed.start
        fade_out = max(0, length - 3)
        inputs += ["-stream_loop", "-1", "-i", bed.file]
        graph.append(
            f"[{count}:a]atrim=0:{length:.3f},"
            f"volume={_num(trim_db)}dB,"
            f"volume='{duck_expression(on_bed(placed, bed), duck)}':eval=frame,afade=t=in:d=2,"
            f"afade=t=out:st={fade_out:.3f}:d=3,"
            f"adelay={_ms(bed.start)}:all=1[m]"
        )
        labels += "[m]"
        count += 1
    graph.append(
        f"{labels}amix=inputs={count}:normalize=0,apad=whole_dur={total:.3f}[mix]"
    )
    return Graph(inputs, graph)


def _integrated(file: str, loudness: Loudness) -> float:
    target = f"I={_num(loudness.target)}:TP={_num(loudness.peak)}:LRA=11"
    return float(
        media.measure_loudness(
            ["-i", file, "-af", f"loudnorm={target}:print_format=json"]
        )["input_i"]
    )


def _voice_track(
    placed: Sequence[Take],
    total: float,
    out_file: str,
    work_dir: str,
    sounds: Sequence[Sound] = (),
    bed: Bed | None = None,
    trim_db: float | None = None,
    duck: Duck = Duck(),
    loudness: Loudness = Loudness(),
    name: str = "mix",
) -> float:
    """Mix one language to `out_file` (AAC) at the loudness target, and return what it measures.

    loudnorm alone stopped short of the target, its linear mode refusing a gain that crosses the
    ceiling, so the gain is applied by hand under a limiter and corrected by what the limiter
    took, a few times at most.
    """
    if bed is not None and trim_db is None:
        trim_db = bed_trim(bed)
    if bed is not None:
        bed = seamless_bed(bed, total, work_dir)
    built = mix_graph(placed, total, sounds, bed, trim_db or 0.0, duck)
    mixed = os.path.join(work_dir, f"{name}.wav")
    media.ffmpeg(
        [
            *built.inputs,
            "-filter_complex",
            built.filter_complex,
            "-map",
            "[mix]",
            "-t",
            f"{total:.3f}",
            mixed,
        ]
    )
    ceiling = 10 ** ((loudness.peak - loudness.margin) / 20)

    def render(gain: float) -> None:
        media.ffmpeg(
            [
                "-i",
                mixed,
                "-af",
                f"volume={gain:.2f}dB,alimiter=limit={ceiling:.3f}:level=false:attack=5:release=80,"
                "aresample=48000",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                out_file,
            ]
        )

    gain = loudness.target - _integrated(mixed, loudness)
    render(gain)
    measured = _integrated(out_file, loudness)
    for _ in range(4):
        if abs(loudness.target - measured) <= loudness.tolerance:
            break
        gain += loudness.target - measured
        render(gain)
        measured = _integrated(out_file, loudness)
    return measured


def voice_track(
    placed: Sequence[Take],
    total: float,
    out_file: str,
    work_dir: str,
    sounds: Sequence[Sound] = (),
    bed: Bed | None = None,
    trim_db: float | None = None,
    duck: Duck = Duck(),
    loudness: Loudness = Loudness(),
    name: str = "mix",
) -> float:
    """VM55: reuse only the independently verified mix for these audio/timing inputs."""
    from urdido import cache

    settings = [
        [asdict(t) for t in placed],
        total,
        [asdict(s) for s in sounds],
        asdict(bed) if bed else None,
        trim_db,
        asdict(duck),
        asdict(loudness),
        name,
    ]
    inputs = [
        __file__,
        media.__file__,
        *[t.file for t in placed],
        *[s.file for s in sounds],
    ]
    if bed:
        inputs.append(bed.file)
    return cache.run(
        "audio mix",
        [out_file],
        settings,
        lambda: _voice_track(
            placed,
            total,
            out_file,
            work_dir,
            sounds,
            bed,
            trim_db,
            duck,
            loudness,
            name,
        ),
        inputs=inputs,
        tools=["ffmpeg"],
    )
