"""Timestamp narration words for video callouts; PW703 tracks the missing sound.speech output."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from urdido.narration import Takes


def transcribe(file: Path, language: str, *, base_url="https://api.elevenlabs.io", key_env="ELEVENLABS_API_KEY") -> str:
    import requests

    from urdido.keywords import word_record, validate_words
    from urdido.sources.model import RecordingRefused

    body = file.read_bytes()
    sha = hashlib.sha256(body).hexdigest()
    record = file.with_suffix(".words.json")
    try:
        word_record(file)
        return f"current {file.stem}"
    except (RecordingRefused, ValueError, KeyError):
        pass
    response = requests.post(
        base_url.rstrip("/") + "/v1/speech-to-text",
        headers={"xi-api-key": os.environ[key_env]},
        data={"model_id": "scribe_v1", "language_code": language, "timestamps_granularity": "word"},
        files={"file": (file.name, body, "audio/mpeg")}, timeout=120,
    )
    response.raise_for_status()
    answer = response.json()
    words = [{k: word[k] for k in ("text", "start", "end")}
             for word in answer.get("words", []) if word.get("type") == "word"]
    if not words:
        raise RuntimeError(f"{file}: transcription returned no timed words")
    validate_words(words, file.stem)
    if hashlib.sha256(file.read_bytes()).hexdigest() != sha:
        raise RuntimeError(f"{file}: audio changed during transcription; result was not saved")
    descriptor, path = tempfile.mkstemp(prefix=record.name + ".", suffix=".tmp", dir=record.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            json.dump({"sha256": sha, "service": "ElevenLabs Scribe v1", "words": words}, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path, record)
    finally:
        Path(path).unlink(missing_ok=True)
    return f"transcribed {file.stem}: {len(words)} words"


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(prog="urdido words", description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--language", default="pt-BR")
    parser.add_argument("--service-language", default="por")
    args = parser.parse_args(argv)
    folder = args.root / "narration"
    takes = Takes(json.loads((folder / "script.json").read_text(encoding="utf-8")), str(folder))
    files = [Path(takes.take_file(args.language, name)) for name in takes.lines]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for message in pool.map(lambda file: transcribe(file, args.service_language), files):
            print(message, flush=True)


if __name__ == "__main__":
    main()
