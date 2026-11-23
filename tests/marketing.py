"""Where the marketing checkout is, for the tests that still read its videos.

The suite came from marketing's `video-maker/` and some tests read the videos beside it
(`turing/wordpress`, `shio/promo`, `japode/*`) or the golden files that stay there
(`turing/wordpress/test/golden`). They skip by name where the checkout is absent,
until UR39's remainder moves them into marketing beside those videos.

`URDIDO_MARKETING` names the checkout; the default is the sibling layout on the
owner's desk (`<git>/viglet/marketing` beside `<git>/alegauss/urdido`).
"""

import os
from pathlib import Path

import pytest

MARKETING = Path(
    os.environ.get("URDIDO_MARKETING")
    or Path(__file__).resolve().parents[3] / "viglet" / "marketing"
)

#: The golden files, beside the video they prove (UR39).
GOLDEN = MARKETING / "turing" / "wordpress" / "test" / "golden"

needs_marketing = pytest.mark.skipif(
    not MARKETING.is_dir(),
    reason=f"needs the marketing checkout (URDIDO_MARKETING, now {MARKETING})",
)


def module_needs_marketing() -> None:
    """Skip the calling test module whole, where it reads marketing while importing."""
    if not MARKETING.is_dir():
        pytest.skip(
            f"reads the marketing checkout at import (URDIDO_MARKETING: {MARKETING})",
            allow_module_level=True,
        )
