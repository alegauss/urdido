"""The assembly of the Viglet product videos, in Python (VM23).

Recording stays JavaScript (the narration reader, the driver and pointer, the terminal
replay); the assembly reads what a recording leaves (`chapters.json` and a WebM, or
`cenas.json` and one clip per take) and builds the video from it. Modules arrive one port
at a time, each proved against the golden files in `../test/golden/expected/`.
"""
