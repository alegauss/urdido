"""ElevenLabs Scribe as a transcriber (UR26), in the `narration` extra.

A transcriber is any callable `(name, audio, language) -> words` that returns the
take's words as `[{"text", "start", "end"}, ...]`, in order. This one posts the audio
to Scribe's speech-to-text with word timestamps. The language is the one the caller
passes, from the declaration; there is no default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Scribe:
    """ElevenLabs Scribe v1 at `base_url`, its key in the environment's `key_env`."""

    base_url: str = "https://api.elevenlabs.io"
    key_env: str = "ELEVENLABS_API_KEY"
    service: str = "ElevenLabs Scribe v1"

    def __call__(self, name: str, audio: bytes, language: str) -> list[dict]:
        from urdido import extras

        requests = extras.require("narration", "requests")
        if not language:
            raise ValueError("transcription needs the take's language, as declared")
        key = os.environ.get(self.key_env)
        if not key:
            raise RuntimeError(f"{self.key_env} is not set; Scribe needs its key")
        response = requests.post(
            self.base_url.rstrip("/") + "/v1/speech-to-text",
            headers={"xi-api-key": key},
            data={
                "model_id": "scribe_v1",
                "language_code": language,
                "timestamps_granularity": "word",
            },
            files={"file": (name, audio, "audio/mpeg")},
            timeout=120,
        )
        response.raise_for_status()
        answer = response.json()
        return [
            {k: word[k] for k in ("text", "start", "end")}
            for word in answer.get("words", [])
            if word.get("type") == "word"
        ]
