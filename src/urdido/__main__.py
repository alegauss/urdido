"""`python -m videomaker build <video.toml> ...` (videomaker.build) and
`python -m videomaker thumbnail <video.toml> --language <l>` (videomaker.thumbnail)."""

import sys

if len(sys.argv) >= 2 and sys.argv[1] == "storyboard":
    from videomaker.storyboard import main as storyboard

    sys.exit(storyboard(sys.argv[2:]))

if len(sys.argv) >= 2 and sys.argv[1] == "instance":
    from videomaker.instances import main as instance

    sys.exit(instance(sys.argv[2:]))

if len(sys.argv) >= 2 and sys.argv[1] == "thumbnail":
    from videomaker.thumbnail import main as thumbnail

    sys.exit(thumbnail(sys.argv[2:]))
if len(sys.argv) < 2 or sys.argv[1] != "build":
    sys.exit("usage: python -m videomaker build <video.toml> --language <l> [--cut full|chapter:N|short:C] ...\n"
             "       python -m videomaker thumbnail <video.toml> --language <l>")

from videomaker.build import main  # noqa: E402

sys.exit(main(sys.argv[2:]))
