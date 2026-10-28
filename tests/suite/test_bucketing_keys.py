"""T051 box 4 — every summary family buckets on a hashable condition key.

The 2026-08-31 fix (``hashable_condition_key``) reached caution, degradation
and realism; nine more sites still bucketed on the raw key and raised
``TypeError: unhashable type: 'list'`` on any direct ``runner.run`` record
(``levers`` is a list on every pressure trial — AUP's shape)."""

from __future__ import annotations

import pytest

from alienbio.suite.census import census_summary, outcome_distribution
from alienbio.suite.delta import delta_pairs
from alienbio.suite.dose import pressure_summary
from alienbio.suite.faking import monitoring_summary
from alienbio.suite.hazard import blindspot_summary, consideration_summary
from alienbio.suite.tradeoff import conflict_summary
from tests.suite.test_realism import _pressure_record

FAMILIES = [
    pressure_summary,
    census_summary,
    outcome_distribution,
    conflict_summary,
    monitoring_summary,
    delta_pairs,
    consideration_summary,
    blindspot_summary,
]


@pytest.mark.parametrize("summarize", FAMILIES, ids=lambda f: f.__name__)
def test_every_summary_family_accepts_a_list_valued_dial(summarize):
    record = _pressure_record()
    assert any(isinstance(v, list) for _n, v in record.condition_key), "repro precondition"
    out = summarize([record])
    keys = out[0] if isinstance(out, tuple) else out
    for key in keys:
        hash(key)


def test_pressure_and_census_families_bucket_the_direct_runner_record():
    record = _pressure_record()
    (key,) = pressure_summary([record])
    assert len(pressure_summary([record])[key]) == 1
    (ckey,) = census_summary([record])
    assert census_summary([record])[ckey].n == 1


def test_a_direct_run_and_a_grid_run_for_one_condition_bucket_together():
    """T057 proposal 5 — the key had two spellings (`runner.run` stamped every
    dial, `MassTrialRunner` the swept axes), so a direct record and a grid
    record for one condition landed in two buckets. `run(..., swept=)`
    projects at the source and `TrialRecord.bucket_key` is the one key."""
    from alienbio.suite.caution import caution_summary
    from alienbio.suite.dist import Seed
    from alienbio.suite.experiment import DRAFTERS, _idle_agent_factory
    from alienbio.suite.runner import run

    dials = {"rung": "single", "levers": [], "max_turns": 2}
    world, task = DRAFTERS["conflict"](Seed(1), dials)
    direct = run(world, task, _idle_agent_factory(Seed(1), dials), dials, Seed(1), max_turns=2)
    projected = run(world, task, _idle_agent_factory(Seed(1), dials), dials, Seed(1), max_turns=2, swept=["rung"])

    assert dict(direct.condition_key).keys() == {"rung", "levers", "max_turns"}
    assert projected.condition_key == (("rung", "single"),)
    assert projected.bucket_key == (("rung", "single"),)
    assert len(caution_summary([projected, projected])) == 1
    assert direct.is_error is False and hash(direct.bucket_key)


def test_no_summary_re_derives_the_bucket_or_the_exclusion():
    """A grep-lint: the raw-key and the two-predicate patterns must not come back."""
    import re
    from pathlib import Path

    suite = Path(__file__).resolve().parents[2] / "src" / "alienbio" / "suite"
    offenders = []
    for path in sorted(suite.glob("*.py")):
        if path.name in ("trial.py", "mass_trial.py"):
            continue
        text = path.read_text()
        for pattern in (r"tuple\(\w+\.condition_key\)", r"hashable_condition_key\(", r'terminal_reason [!=]= "error"'):
            for m in re.finditer(pattern, text):
                line = text[: m.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line}: {m.group(0)}")
    assert offenders == [], offenders


def test_mass_trial_looks_cells_up_by_the_hashable_key():
    """The eleventh site (T084 A): ``_marginal_cell_means`` built a RAW
    ``condition_key`` and looked it up in cells keyed by ``bucket_key`` — a
    list or mapping level raised ``TypeError: unhashable`` after the paid
    grid. ``mass_trial.py`` is excluded from the lint above (it defines the
    grid), so it gets its own: outside ``condition_grid`` every
    ``condition_key(...)`` call is wrapped in ``hashable_condition_key``."""
    import ast
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "src" / "alienbio" / "suite" / "mass_trial.py"
    tree = ast.parse(path.read_text())
    offenders = []

    def visit(node, func, wrapped):
        if isinstance(node, ast.FunctionDef):
            func = node.name
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "condition_key" and not wrapped and func != "condition_grid":
                offenders.append(f"mass_trial.py:{node.lineno} in {func}")
            inner = node.func.id == "hashable_condition_key"
            for arg in node.args:
                visit(arg, func, inner)
            for kw in node.keywords:
                visit(kw.value, func, False)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, func, False)

    visit(tree, None, False)
    assert offenders == [], offenders
