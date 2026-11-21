# Extras and the tools they need

The base install needs only `opentimelineio`. Everything heavier is an extra, and code
that needs a missing one stops with the `pip install` that fixes it.

| Extra | Install | Needed for | Also needs |
| --- | --- | --- | --- |
| `cards` | `pip install urdido[cards]` | Cards, the brand mark, site screens and thumbnail layouts, drawn with Playwright; font coverage checks | Playwright's Chromium: `python -m playwright install chromium`, or `[cards] channel = "msedge"` for an installed Edge |
| `narration` | `pip install urdido[narration]` | Buying takes and transcribing their word times | An ElevenLabs key in `ELEVENLABS_API_KEY` |
| `polyweave` | `pip install urdido[polyweave]` | Voice takes, stock footage, web capture, Shorts safe areas and measured bounds | A `polyweave.toml` in the project, with its services and prices |
| `shorts` | `pip install urdido[shorts]` | The background of `urdido shorts` | |

Every build also needs **ffmpeg** and **ffprobe** on the PATH. Some steps need a
program rather than a package, and say so by name when it is missing:

- **Node.js** for the JavaScript recording helpers (`urdido-record`), which record and
  replay sessions; the build itself does not need it.
- **Docker** for `urdido instance`, which starts the product instance a recording runs
  against.
- **DaVinci Resolve** to open the project `urdido build --project` exports.
