"""A take's word times, written beside it and bound to its hash (UR26).

    urdido words <video.toml> --language pt-BR

Every take of the script is transcribed once: `<take>.words.json` holds the words with
their times, the take's SHA-256 and the service that heard them, and is rewritten only
when the take changes. Callers read that record, never a transcriber. The transcriber is
a seam: anything `(name, audio, language) -> words` (ElevenLabs Scribe today,
`urdido.providers.scribe`; PW703 tracks a provider one). The language is the
declaration's, never a default.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from urdido.narration import Takes


def transcribe(file: Path, language: str, *, transcriber=None, base_url="https://api.elevenlabs.io",
               key_env="ELEVENLABS_API_KEY") -> str:
    """Write `file`'s word record, unless a current one is there already."""
    from urdido.keywords import validate_words, word_record
    from urdido.sources.model import RecordingRefused

    if not language:
        raise ValueError(f"{file.stem}: transcription needs the take's declared language")
    body = file.read_bytes()
    sha = hashlib.sha256(body).hexdigest()
    record = file.with_suffix(".words.json")
    try:
        word_record(file)
        return f"current {file.stem}"
    except (RecordingRefused, ValueError, KeyError):
        pass
    if transcriber is None:
        from urdido.providers.scribe import Scribe

        transcriber = Scribe(base_url=base_url, key_env=key_env)
    words = transcriber(file.name, body, language)
    if not words:
        raise RuntimeError(f"{file}: transcription returned no timed words")
    validate_words(words, file.stem)
    if hashlib.sha256(file.read_bytes()).hexdigest() != sha:
        raise RuntimeError(f"{file}: audio changed during transcription; result was not saved")
    service = getattr(transcriber, "service", type(transcriber).__name__)
    descriptor, path = tempfile.mkstemp(prefix=record.name + ".", suffix=".tmp", dir=record.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            json.dump({"sha256": sha, "service": service, "words": words}, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, record)
    finally:
        Path(path).unlink(missing_ok=True)
    return f"transcribed {file.stem}: {len(words)} words"


def main(argv: list[str] | None = None, transcriber=None) -> int:
    parser = argparse.ArgumentParser(prog="urdido words", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("declaration", type=Path, help="the video's .toml")
    parser.add_argument("--language", required=True, help="the narration's language, as the declaration names it")
    args = parser.parse_args(argv)
    from types import SimpleNamespace

    from urdido.build import Build

    build = Build(args.declaration, SimpleNamespace(language=args.language, plan=True, cards=False))
    service_language = build.decl["video"]["languages"][args.language]
    takes = Takes(build.load(build.decl["narration"]["script"]), build.path(build.decl["narration"]["takes"]))
    files = [Path(takes.take_file(args.language, name)) for name in takes.lines]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for message in pool.map(lambda file: transcribe(file, service_language, transcriber=transcriber), files):
            print(message, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
