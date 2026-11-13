"""Timestamp narration words for video callouts; PW703 tracks the missing sound.speech output."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from videomaker.narration import Takes


def transcribe(file: Path, language: str) -> str:
    import requests

    sha = hashlib.sha256(file.read_bytes()).hexdigest()
    record = file.with_suffix(".words.json")
    if record.exists() and json.loads(record.read_text(encoding="utf-8"))["sha256"] == sha:
        return f"current {file.stem}"
    with file.open("rb") as audio:
        response = requests.post(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            data={"model_id": "scribe_v1", "language_code": language, "timestamps_granularity": "word"},
            files={"file": audio}, timeout=120,
        )
    response.raise_for_status()
    answer = response.json()
    words = [{k: word[k] for k in ("text", "start", "end")}
             for word in answer.get("words", []) if word.get("type") == "word"]
    if not words:
        raise RuntimeError(f"{file}: transcription returned no timed words")
    record.write_text(json.dumps({"sha256": sha, "service": "ElevenLabs Scribe v1", "words": words},
                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"transcribed {file.stem}: {len(words)} words"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--language", default="pt-BR")
    parser.add_argument("--service-language", default="por")
    args = parser.parse_args()
    folder = args.root / "narration"
    takes = Takes(json.loads((folder / "script.json").read_text(encoding="utf-8")), str(folder))
    files = [Path(takes.take_file(args.language, name)) for name in takes.lines]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for message in pool.map(lambda file: transcribe(file, args.service_language), files):
            print(message, flush=True)


if __name__ == "__main__":
    main()
