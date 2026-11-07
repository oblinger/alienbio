"""T099 — ``DRAFTERS`` re-adapts when the registry's head under a name changes.

Two copies of one example's ``helpers.py`` loaded in one process register
the same drafter twice (a same-definition re-registration); the cached
adapter used to outlive the first head, so both copies drafted from the
first copy's yaml. Found by T091 round BF, whose fixture evicted the cache.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from alienbio.expr.registry import registry
from alienbio.suite.drafters import DRAFTERS
from alienbio.suite.dist import Seed
from alienbio.suite.expr_experiment import load_experiment, read_spec_text

REPO = Path(__file__).resolve().parents[2]
MICROCOSM = REPO / "catalog/examples/microcosm"


def _copy(into: Path, drain_rate: str) -> Path:
    into.mkdir()
    shutil.copy(MICROCOSM / "helpers.py", into / "helpers.py")
    text = (MICROCOSM / "microcosm.yaml").read_text().replace("drain_rate: 0.02 ", f"drain_rate: {drain_rate} ")
    assert f"drain_rate: {drain_rate} " in text
    (into / "microcosm.yaml").write_text(text)
    return into / "microcosm.yaml"


def _load(yml: Path) -> None:
    load_experiment(yml.resolve(), text=read_spec_text(yml.resolve()), trusted=True)


def _drain_rate() -> float:
    world, _task = DRAFTERS["microcosm"](Seed(5), {})
    return float(world.chemistry.reactions["drain"].rate)


def test_a_second_copy_of_one_helper_drafts_from_its_own_yaml(tmp_path):
    before = dict.get(DRAFTERS, "microcosm")
    try:
        _load(_copy(tmp_path / "a", "0.02"))
        head_a = registry.get("microcosm")
        assert _drain_rate() == 0.02
        _load(_copy(tmp_path / "b", "0.08"))
        assert registry.get("microcosm") is not head_a, "the second copy re-registered the head"
        assert _drain_rate() == 0.08  # re-adapted: the first copy's adapter is gone
        assert _drain_rate() == 0.08  # and stays
    finally:
        DRAFTERS.pop("microcosm", None)
        if before is not None:
            DRAFTERS["microcosm"] = before


def test_an_entry_set_from_outside_is_left_alone(tmp_path, monkeypatch):
    """A ``monkeypatch.setitem`` spy has no remembered head, so a lookup never
    replaces it, whatever the registry holds."""
    calls: list[str] = []

    def spy(seed, dials, **kw):
        calls.append("spy")
        raise RuntimeError("spy")

    monkeypatch.setitem(DRAFTERS, "conflict", spy)
    assert DRAFTERS["conflict"] is spy
    assert dict.get(DRAFTERS, "conflict") is spy
