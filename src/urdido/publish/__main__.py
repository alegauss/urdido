"""`python -m videomaker.publish transcript --declaration <publish.json> [--check]`: the narration's
transcript written where the video's declaration says (VM15)."""

import argparse
import json
import os
import sys

from videomaker.publish import transcript_outputs, write_outputs

p = argparse.ArgumentParser(prog="python -m videomaker.publish")
p.add_argument("what", choices=["transcript"])
p.add_argument("--declaration", required=True, help="the video's publish.json")
p.add_argument("--root", action="append", default=[], help="name=folder, for the declaration's <name> paths")
p.add_argument("--check", action="store_true", help="write nothing; exit 1 when a target is out of date")
a = p.parse_args()

roots = dict(r.split("=", 1) for r in a.root)
with open(a.declaration, encoding="utf-8") as f:
    declared = json.load(f)
base = os.path.dirname(os.path.abspath(a.declaration))
script_file = os.path.join(os.path.dirname(base), declared["transcript"]["script"])
with open(script_file, encoding="utf-8") as f:
    script = json.load(f)
stale = write_outputs(transcript_outputs(declared["transcript"], script, roots), check=a.check)
for path in stale:
    print(f"{path} is out of date: run npm run transcript" if a.check else f"wrote {path}",
          file=sys.stderr if a.check else sys.stdout)
sys.exit(1 if (a.check and stale) else 0)
