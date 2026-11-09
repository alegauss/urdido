"""`python -m videomaker build <video.toml> ...`: see videomaker.build."""

import sys

from videomaker.build import main

if len(sys.argv) < 2 or sys.argv[1] != "build":
    sys.exit("usage: python -m videomaker build <video.toml> --language <l> [--cut full|chapter:N|short:C] ...")
sys.exit(main(sys.argv[2:]))
