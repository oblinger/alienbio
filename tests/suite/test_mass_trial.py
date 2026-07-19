"""Acceptance tests for the M34 mass-trial runner + reliability map (F024).

A thin, SEQUENTIAL orchestrator over shipped, already-tested parts —
these tests exercise real ``draft_conflict_world`` (F022) worlds run through
the real ``ScenarioRunner``/``ScriptedAgent`` seam (F020/F021), reduced
through the shipped ``reliability_grid``/``stats_summary``/``effect_size``
primitives. No LLM, no network.
"""

from __future__ import annotations

import csv
import io
import json

from alienbio.suite.agent import Commit, ScriptedAgent
from alienbio.suite.conflict_gen import draft_conflict_world
from alienbio.suite.dist import Seed, Uniform
from alienbio.suite.mass_trial import (
    CellSummary,
    ContrastResult,
    MassTrialRunner,
    ReliabilityMap,
    condition_grid,
)
from alienbio.suite.types import Answer, CarveResult, Motif, Question, TaskInstance

# ═══════════════════════════════════════════════════════════════════════════
# condition_grid — pure orthogonal-product shape (no simulator involved)
# ═══════════════════════════════════════════════════════════════════════════


def test_condition_grid_orthogonal_product():
    axes = [("a", [1, 2]), ("b", ["x", "y"])]
    grid = condition_grid(axes)

    assert grid == [
        (("a", 1), ("b", "x")),
        (("a", 1), ("b", "y")),
        (("a", 2), ("b", "x")),
        (("a", 2), ("b", "y")),
    ]
    # Every cell key is already the sorted (dial, level) shape condition_key
    # normalises to — the exact shape aggregate_cells bins on, no adapter.
    for key in grid:
        assert key == tuple(sorted(key, key=lambda kv: kv[0]))


def test_condition_grid_three_axes_full_cardinality():
    axes = [("a", [1, 2]), ("b", ["x", "y"]), ("c", [True, False])]
    grid = condition_grid(axes)

    assert len(grid) == 2 * 2 * 2
    assert len(set(grid)) == len(grid)  # every cell distinct


# ═══════════════════════════════════════════════════════════════════════════
# Shared drafter / agent_factory — real conflict-ladder worlds, no LLM
# ═══════════════════════════════════════════════════════════════════════════

RUNG_LEVELS = ("compatible", "forced")
SPLIT_LEVELS = ("balanced", "skewed")

#: Two named (kA, kB) split distributions per the F022 "latent" story: an
#: unbalanced split reveals hidden tension between the two conflict routes.
#: Kept as ``Dist``s (not ``Constant``) so each trial's per-seed draw of the
#: split gives real trial-to-trial variance within one condition-cell — the
#: whole point of a *reliability* map.
_SPLITS = {
    "balanced": (Uniform(0.8, 1.2), Uniform(0.8, 1.2)),
    "skewed": (Uniform(1.8, 2.2), Uniform(0.1, 0.3)),
}


def _drafter(seed: Seed, dials):
    kA, kB = _SPLITS[dials["split"]]
    world, _skeleton, objective = draft_conflict_world(seed, rung=dials["rung"], kA=kA, kB=kB)
    task = TaskInstance(
        archetype=f"conflict_{dials['rung']}_{dials['split']}",
        world="world0",
        skeleton=CarveResult(motif=Motif(roles=(), edges=()), binding={}),
        objective=objective,
        question=Question(structured=set(), kind="node_set"),
        setup={},
    )
    return world, task


def _agent_factory(seed: Seed, dials):
    del dials
    # An OutcomeObjective task is graded off the final timeline regardless of
    # whether a Commit fired, so an immediate Commit is sufficient — no
    # per-world molecule/probe name needed (agent_factory never sees `world`).
    policy = (Commit(answer=Answer(value=0.0, kind="scalar")),)
    return ScriptedAgent(policy, seed=seed)


_AXES = [("rung", RUNG_LEVELS), ("split", SPLIT_LEVELS)]


# ═══════════════════════════════════════════════════════════════════════════
# End-to-end: real conflict worlds through ScenarioRunner -> ReliabilityMap
# ═══════════════════════════════════════════════════════════════════════════


def test_mass_trial_end_to_end_reliability_map():
    rmap = MassTrialRunner().run(
        _AXES, _drafter, _agent_factory, trials_per_condition=8, base_seed=Seed(100)
    )

    assert isinstance(rmap, ReliabilityMap)
    assert len(rmap.cells) == 4  # 2 rungs x 2 splits
    expected_keys = set(condition_grid(_AXES))
    assert set(rmap.cells.keys()) == expected_keys

    for summary in rmap.cells.values():
        assert isinstance(summary, CellSummary)
        assert summary.stats.n == 8
        assert 0.0 <= summary.stats.mean <= 1.0
        assert summary.ci[0] <= summary.stats.mean <= summary.ci[1]

    assert ("rung", "split") in rmap.interactions
    assert isinstance(rmap.interactions[("rung", "split")], float)

    assert ("rung", "split") in rmap.contrasts
    contrast = rmap.contrasts[("rung", "split")]
    assert isinstance(contrast, ContrastResult)
    assert isinstance(contrast.cohens_d, float)
    assert isinstance(contrast.welch_t, float)

    assert rmap.provenance.axes == (
        ("rung", RUNG_LEVELS),
        ("split", SPLIT_LEVELS),
    )
    assert rmap.provenance.base_seed == Seed(100)
    assert rmap.provenance.trials_per_condition == 8


# ═══════════════════════════════════════════════════════════════════════════
# Reproducibility: identical inputs -> byte-identical map
# ═══════════════════════════════════════════════════════════════════════════


def test_mass_trial_reproducible_same_inputs_same_map():
    r1 = MassTrialRunner().run(
        _AXES, _drafter, _agent_factory, trials_per_condition=6, base_seed=Seed(7)
    )
    r2 = MassTrialRunner().run(
        _AXES, _drafter, _agent_factory, trials_per_condition=6, base_seed=Seed(7)
    )

    assert r1.cells.keys() == r2.cells.keys()
    for key in r1.cells:
        assert r1.cells[key].stats.n == r2.cells[key].stats.n
        assert r1.cells[key].stats.mean == r2.cells[key].stats.mean
        assert r1.cells[key].stats.std == r2.cells[key].stats.std
        assert r1.cells[key].ci == r2.cells[key].ci
    assert r1.interactions == r2.interactions
    assert {k: (c.cohens_d, c.welch_t) for k, c in r1.contrasts.items()} == {
        k: (c.cohens_d, c.welch_t) for k, c in r2.contrasts.items()
    }


# ═══════════════════════════════════════════════════════════════════════════
# Widening: adding a level to an axis only ADDS cells, never perturbs existing ones
# ═══════════════════════════════════════════════════════════════════════════


def test_mass_trial_widening_axis_preserves_prior_cells():
    small_axes = [("rung", ("compatible",)), ("split", SPLIT_LEVELS)]
    wide_axes = [("rung", ("compatible", "forced")), ("split", SPLIT_LEVELS)]

    r_small = MassTrialRunner().run(
        small_axes, _drafter, _agent_factory, trials_per_condition=6, base_seed=Seed(42)
    )
    r_wide = MassTrialRunner().run(
        wide_axes, _drafter, _agent_factory, trials_per_condition=6, base_seed=Seed(42)
    )

    assert set(r_small.cells) <= set(r_wide.cells)
    assert len(r_wide.cells) == len(r_small.cells) + len(SPLIT_LEVELS)
    for key in r_small.cells:
        assert r_small.cells[key].stats.n == r_wide.cells[key].stats.n
        assert r_small.cells[key].stats.mean == r_wide.cells[key].stats.mean
        assert r_small.cells[key].stats.std == r_wide.cells[key].stats.std
        assert r_small.cells[key].ci == r_wide.cells[key].ci


# ═══════════════════════════════════════════════════════════════════════════
# to_json / to_csv — parseable, offline-analysis-ready artifacts
# ═══════════════════════════════════════════════════════════════════════════


def test_to_json_round_trip():
    rmap = MassTrialRunner().run(
        _AXES, _drafter, _agent_factory, trials_per_condition=5, base_seed=Seed(55)
    )

    payload = json.loads(rmap.to_json())
    assert payload["provenance"]["trials_per_condition"] == 5
    assert payload["provenance"]["base_seed"] == 55
    assert payload["provenance"]["axes"] == [
        ["rung", list(RUNG_LEVELS)],
        ["split", list(SPLIT_LEVELS)],
    ]
    assert len(payload["cells"]) == len(rmap.cells)
    for cell in payload["cells"]:
        assert set(cell) == {"condition_key", "n", "mean", "std", "ci_low", "ci_high"}
    assert len(payload["interactions"]) == len(rmap.interactions)
    assert len(payload["contrasts"]) == len(rmap.contrasts)


def test_to_csv_round_trip():
    rmap = MassTrialRunner().run(
        _AXES, _drafter, _agent_factory, trials_per_condition=5, base_seed=Seed(66)
    )

    rows = list(csv.reader(io.StringIO(rmap.to_csv())))
    header, *data_rows = rows
    assert header == ["rung", "split", "n", "mean", "std", "ci_low", "ci_high"]
    assert len(data_rows) == len(rmap.cells)

    seen_conditions = set()
    for row in data_rows:
        rung, split, n, mean, std, ci_low, ci_high = row
        assert rung in RUNG_LEVELS
        assert split in SPLIT_LEVELS
        assert int(n) == 5
        assert 0.0 <= float(mean) <= 1.0
        assert float(ci_low) <= float(mean) <= float(ci_high)
        seen_conditions.add((rung, split))
    assert len(seen_conditions) == len(rmap.cells)
