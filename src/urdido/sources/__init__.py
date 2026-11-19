"""Where a video's picture comes from, as one chapter model the timeline consumes (VM8).

A source is read into `Chapter`s: its number and title, the clip it plays (a file, from where
to where), and the marks the recording left in it. Two shapes feed this model: one long
recording with chapter marks (`chaptered_recording`, the WordPress story's `chapters.json`), and
one clip per narration take (Viglet Shio's `cenas.json`, VM10).
"""

from urdido.sources.model import Box, Chapter, Clip, Focus, Line, Marks, Recording, RecordingRefused, Span
from urdido.sources.recording import chaptered_recording

__all__ = [
    "Box", "Chapter", "Clip", "Focus", "Line", "Marks", "Recording", "RecordingRefused", "Span",
    "chaptered_recording",
]
