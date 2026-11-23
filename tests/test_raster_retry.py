"""A card layer whose screenshot the browser could not capture is drawn again once
(UR63)."""

import pytest

from urdido.cards.render import UNCAPTURED, retried
from urdido.errors import UrdidoError

FAILED = Exception(
    f"Page.screenshot: Protocol error (Page.captureScreenshot): {UNCAPTURED}"
)


def flaky(failures: int):
    calls = {"draw": 0, "fresh": 0}

    def draw():
        calls["draw"] += 1
        if calls["draw"] <= failures:
            raise FAILED
        return "drawn"

    def fresh():
        calls["fresh"] += 1

    return draw, fresh, calls


def test_a_layer_that_fails_once_is_drawn_on_the_retry_in_a_fresh_page():
    draw, fresh, calls = flaky(1)
    assert retried(draw, fresh, "outro-0.png", None) == "drawn"
    assert calls == {"draw": 2, "fresh": 1}


def test_a_second_failure_is_refused_by_the_layer_and_the_browser():
    draw, fresh, calls = flaky(2)
    with pytest.raises(UrdidoError, match="msedge could not capture card-3.png twice"):
        retried(draw, fresh, "card-3.png", "msedge")
    assert calls == {"draw": 2, "fresh": 1}


def test_any_other_error_is_not_retried():
    def draw():
        raise ValueError("a page error")

    with pytest.raises(ValueError, match="a page error"):
        retried(draw, lambda: pytest.fail("no fresh page for another error"), "x", None)
