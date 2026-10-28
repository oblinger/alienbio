"""Module-doc findings on ``ReactionImpl``: ``rate`` is a number, checked at
construction and by ``set_rate``.

Repro (before the fix): ``ReactionImpl("r", rate="abc")`` was accepted and
failed only when a simulator was built from it.
"""

from __future__ import annotations

import pytest

from alienbio.bio.reaction import ReactionImpl
from alienbio.infra.entity import MockDat


@pytest.mark.parametrize("bad", ["abc", None, True, lambda state: 0.5, [1.0]])
def test_a_non_numeric_rate_refuses_at_construction(bad) -> None:
    with pytest.raises(ValueError, match="rate must be a number"):
        ReactionImpl("r", rate=bad, dat=MockDat("rxn/r"))  # type: ignore[arg-type]


def test_set_rate_refuses_a_non_numeric_rate() -> None:
    rxn = ReactionImpl("r", rate=0.5, dat=MockDat("rxn/r"))
    with pytest.raises(ValueError, match="rate must be a number"):
        rxn.set_rate("abc")  # type: ignore[arg-type]
    assert rxn.rate == 0.5


def test_numeric_rates_of_every_kind_are_accepted() -> None:
    np = pytest.importorskip("numpy")
    for ok in (1, 0.25, np.float64(0.5), np.int64(2)):
        assert ReactionImpl("r", rate=ok, dat=MockDat("rxn/r")).rate == ok
