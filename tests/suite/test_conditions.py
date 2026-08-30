"""Acceptance tests for the M34.1 orthogonal dial-composition harness (F023).

No LLM, no network. Exercises ``DialAxis``/``ConditionSpec``/``sample``/
``condition_key_of``/``apply`` in isolation, plus a real ``ScenarioRunner``
end-to-end round-trip with a jointly-sampled condition.
"""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Commit, ScriptedAgent
from alienbio.suite.archetypes import identify_pathway
from alienbio.suite.conditions import (
    NON_ORTHOGONAL_PAIRS,
    ConditionSpec,
    DialAxis,
    apply,
    condition_key_of,
    sample,
)
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.pipeline import build_suite
from alienbio.suite.reliability_grid import aggregate_cells
from alienbio.suite.runner import run
from alienbio.suite.trial import condition_key
from alienbio.suite.types import Answer, AnswerObjective, SuiteSpec


def _suite(seed_val: int = 1):
    arch = identify_pathway(pathway_length=3)
    spec = SuiteSpec(archetype_mix=Constant(arch))
    return build_suite(spec, Seed(seed_val), n_tasks=1, distractor_count=1)


# ═══════════════════════════════════════════════════════════════════════════
# DialAxis — exactly one shape (discrete XOR continuous+quantized)
# ═══════════════════════════════════════════════════════════════════════════


def test_dial_axis_requires_one_shape_not_neither():
    with pytest.raises(ValueError, match="must set either"):
        DialAxis()


def test_dial_axis_requires_one_shape_not_both():
    with pytest.raises(ValueError, match="not both"):
        DialAxis(levels=(1, 2), lo=0.0, hi=1.0, bin_edges=(0.0, 1.0))


def test_dial_axis_discrete_levels_must_be_nonempty():
    with pytest.raises(ValueError, match="non-empty"):
        DialAxis(levels=())


def test_dial_axis_continuous_requires_bin_edges():
    with pytest.raises(ValueError, match="bin_edges"):
        DialAxis(lo=0.0, hi=1.0)


def test_dial_axis_factory_helpers():
    d = DialAxis.discrete("low", "high")
    assert d.levels == ("low", "high")
    c = DialAxis.continuous(0.0, 1.0, [0.0, 0.5, 1.0])
    assert c.lo == 0.0 and c.hi == 1.0 and c.bin_edges == (0.0, 0.5, 1.0)


# ═══════════════════════════════════════════════════════════════════════════
# ConditionSpec — the declared non-orthogonal pairs list (Q2 = C)
# ═══════════════════════════════════════════════════════════════════════════


def test_condition_spec_rejects_declared_non_orthogonal_pair():
    assert ("observability", "observation_noise") in NON_ORTHOGONAL_PAIRS
    with pytest.raises(ValueError, match="non-orthogonal"):
        ConditionSpec(
            axes={
                "observability": DialAxis.discrete(0.5, 1.0),
                "observation_noise": DialAxis.discrete(0.0, 0.1),
            }
        )


def test_condition_spec_allows_pair_with_explicit_opt_out():
    spec = ConditionSpec(
        axes={
            "observability": DialAxis.discrete(0.5, 1.0),
            "observation_noise": DialAxis.discrete(0.0, 0.1),
        },
        non_orthogonal=(),
    )
    assert spec.axes["observability"].levels == (0.5, 1.0)


def test_condition_spec_single_dial_from_pair_is_fine():
    # Only one member of the declared pair present -> no conflict.
    spec = ConditionSpec(axes={"observability": DialAxis.discrete(0.5, 1.0)})
    assert set(spec.axes) == {"observability"}


# ═══════════════════════════════════════════════════════════════════════════
# sample — seed-deterministic, per-dial independent (no cross-talk)
# ═══════════════════════════════════════════════════════════════════════════

_STAKES = DialAxis.discrete("low", "moderate", "high")
_REVERSIBILITY = DialAxis.discrete("reversible", "irreversible")
_BUDGET = DialAxis.discrete("unlimited", "20", "12", "8", "4")


def test_sample_is_seed_deterministic():
    spec = ConditionSpec(axes={"stakes": _STAKES, "reversibility": _REVERSIBILITY})
    d1 = sample(spec, Seed(42))
    d2 = sample(spec, Seed(42))
    assert d1 == d2


def test_sample_varies_across_seeds():
    spec = ConditionSpec(axes={"stakes": _STAKES, "reversibility": _REVERSIBILITY})
    draws = {tuple(sample(spec, Seed(i)).items()) for i in range(20)}
    assert len(draws) > 1


def test_sample_only_draws_named_axes_omit_absent():
    spec = ConditionSpec(axes={"stakes": _STAKES})
    dials = sample(spec, Seed(1))
    assert set(dials) == {"stakes"}


def test_sample_per_dial_independent_no_cross_talk():
    """Varying dial A's declared axis leaves dial B's realized level
    unchanged, for a fixed seed (Q2 = C: per-dial child seeds, no shared
    RNG stream)."""
    seed = Seed(99)
    spec_a = ConditionSpec(
        axes={"stakes": DialAxis.discrete("low", "moderate", "high"), "reversibility": _REVERSIBILITY}
    )
    spec_b = ConditionSpec(
        axes={"stakes": DialAxis.discrete("low"), "reversibility": _REVERSIBILITY}
    )
    d_a = sample(spec_a, seed)
    d_b = sample(spec_b, seed)
    assert d_a["reversibility"] == d_b["reversibility"]


def test_sample_per_dial_independent_across_many_seeds():
    for i in range(30):
        seed = Seed(i)
        spec_a = ConditionSpec(
            axes={"stakes": _STAKES, "reversibility": _REVERSIBILITY, "budget": _BUDGET}
        )
        spec_b = ConditionSpec(axes={"stakes": _STAKES, "reversibility": _REVERSIBILITY})
        d_a = sample(spec_a, seed)
        d_b = sample(spec_b, seed)
        assert d_a["stakes"] == d_b["stakes"]
        assert d_a["reversibility"] == d_b["reversibility"]


# ═══════════════════════════════════════════════════════════════════════════
# sample — continuous dials quantize to declared bin edges (Q3 = C)
# ═══════════════════════════════════════════════════════════════════════════


def test_continuous_dial_quantizes_to_declared_bin_edges():
    bin_edges = (0.0, 0.25, 0.5, 0.75, 1.0)
    spec = ConditionSpec(axes={"observability": DialAxis.continuous(0.0, 1.0, bin_edges)})
    for i in range(50):
        dials = sample(spec, Seed(i))
        assert dials["observability"] in bin_edges


def test_continuous_dial_equal_conditions_collapse_to_one_key():
    # A narrow range around one bin edge: every draw quantizes to the SAME
    # edge, so every resulting condition_key is identical across seeds.
    bin_edges = (0.0, 0.5, 1.0)
    spec = ConditionSpec(axes={"observability": DialAxis.continuous(0.55, 0.6, bin_edges)})
    keys = {condition_key_of(sample(spec, Seed(i))) for i in range(20)}
    assert keys == {(("observability", 0.5),)}


# ═══════════════════════════════════════════════════════════════════════════
# condition_key_of — canonical, reused from trial.condition_key, omit-absent
# ═══════════════════════════════════════════════════════════════════════════


def test_condition_key_of_matches_trial_condition_key():
    dials = {"stakes": "high", "reversibility": "irreversible"}
    assert condition_key_of(dials) == condition_key(dials)


def test_condition_key_of_omits_unset_dials_forward_compatible():
    old_spec = ConditionSpec(axes={"stakes": _STAKES})
    new_spec = ConditionSpec(axes={"stakes": _STAKES, "reversibility": _REVERSIBILITY})

    old_dials = sample(old_spec, Seed(5))
    new_dials = sample(new_spec, Seed(5))

    old_key = condition_key_of(old_dials)
    # The old key (built before "reversibility" existed) is a strict subset
    # of the new key's dial names — adding an axis never re-keys it.
    new_key_names = {name for name, _ in condition_key_of(new_dials)}
    old_key_names = {name for name, _ in old_key}
    assert old_key_names < new_key_names
    assert old_key_names == {"stakes"}


# ═══════════════════════════════════════════════════════════════════════════
# apply — pin overrides on top of a sampled condition
# ═══════════════════════════════════════════════════════════════════════════


def test_apply_overrides_pin_a_dial():
    dials = {"stakes": "high", "reversibility": "irreversible"}
    merged = apply(dials, {"reversibility": "reversible", "budget": "8"})
    assert merged == {"stakes": "high", "reversibility": "reversible", "budget": "8"}
    # `dials` itself is untouched.
    assert dials == {"stakes": "high", "reversibility": "irreversible"}


def test_apply_with_no_overrides_is_identity_copy():
    dials = {"stakes": "high"}
    merged = apply(dials)
    assert merged == dials
    assert merged is not dials


# ═══════════════════════════════════════════════════════════════════════════
# Round-trip into a reliability-grid cell
# ═══════════════════════════════════════════════════════════════════════════


def test_jointly_sampled_condition_round_trips_into_reliability_grid_cell():
    spec = ConditionSpec(axes={"stakes": _STAKES, "reversibility": _REVERSIBILITY, "budget": _BUDGET})
    dials = sample(spec, Seed(3))
    key = condition_key_of(dials)

    observations = [(key, 0.5), (key, 0.9)]
    cells = aggregate_cells(observations)

    assert key in cells
    assert cells[key].n == 2
    assert cells[key].mean == pytest.approx(0.7)


# ═══════════════════════════════════════════════════════════════════════════
# End-to-end: a jointly-sampled condition (budget x observability) through
# the real ScenarioRunner -> a correctly-keyed TrialRecord. No LLM.
# ═══════════════════════════════════════════════════════════════════════════


def test_jointly_sampled_condition_runs_end_to_end_correctly_keyed():
    suite = _suite()
    world, task = suite.worlds[0], suite.tasks[0]
    assert isinstance(task.objective, AnswerObjective)

    spec = ConditionSpec(
        axes={
            "budget": DialAxis.discrete("8"),
            "observability": DialAxis.discrete(1.0),
        }
    )
    dials = sample(spec, Seed(17))

    policy = (Commit(answer=Answer(value=list(task.objective.key.value), kind="ordered_path")),)
    agent = ScriptedAgent(policy, seed=Seed(0))
    record = run(world, task, agent, dials, Seed(23))

    assert record.condition_key == condition_key_of(dials)
    assert record.terminal_reason == "committed"
    assert record.objective_score == pytest.approx(1.0)
    assert record.budget == 8.0
