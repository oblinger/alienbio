"""T092 — the round-4 leftovers the T091 verifiers recorded: a name bound
with ``!x <draw>`` judged by its support, ``make_intervention_objective``
requiring ``world=``, a math call over an undrawn distribution refused by
name, and the conflict scorer reading one compartment."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from alienbio.expr import Env, ExprError
from alienbio.suite.dist import Seed
from alienbio.suite.verify import SimConfig, simulate


def _doc(rate: str, pre: str = "") -> str:
    return f"""
{pre}
sk: !skeleton
  root: !block
    children:
      r: !reaction
        reactants: [A, B]
        products: [C]
        rate: {rate}
w: !world {{skeleton: !x sk, initial: {{A: 2.0, B: 3.0}}}}
"""


def _load(rate: str, pre: str = "", seed: int = 1):
    return Env.standard(seed=seed).load("<rate>", text=_doc(rate, pre)).force_all()["w"]


def _verdicts(rate: str, pre: str, seeds=range(40)) -> set[str]:
    out = set()
    for seed in seeds:
        try:
            _load(rate, pre, seed)
            out.add("loads")
        except ExprError as exc:
            out.add(exc.message)
    return out


# ---- (1) a bound draw is judged by its support, on every seed ----------------


@pytest.mark.parametrize("pre", ["k: !x normal(0.3, 0.3)", "k: !x 'normal(0.3, 0.3)'", "k: !q normal(0.3, 0.3)"])
def test_a_name_bound_to_a_mixed_sign_draw_refuses_identically_on_every_seed(pre):
    verdicts = _verdicts("!q k * A", pre)
    assert len(verdicts) == 1, verdicts  # was 7 of 40 refusing with !x, the rest loading
    (message,) = verdicts
    assert "negative rate constant possible" in message and "normal(0.3, 0.3)" in message


def test_a_bound_draw_through_a_chain_of_names_and_a_mapping_is_folded():
    assert _verdicts("!q k2 * A", "k: !x normal(0.3, 0.3)\nk2: !x k * 2") != {"loads"}
    assert len(_verdicts("!q cfg.k * A", "cfg: {k: !x normal(0.3, 0.3)}")) == 1
    assert "loads" not in _verdicts("!q cfg.k * A", "cfg: {k: !x normal(0.3, 0.3)}")


@pytest.mark.parametrize(
    "pre",
    ["k: !x lognormal(0, 1)", "k: !x uniform(0.1, 0.5)", "k: 0.5", "k: !x max(normal(0.3, 0.3), 0.05)", "k: !x abs(normal(0, 1))", "k: !x discrete([1, 2])"],
)
def test_a_name_bound_to_a_non_negative_draw_loads_on_every_seed(pre):
    assert _verdicts("!q k * A", pre) == {"loads"}


def test_a_bound_draw_keeps_its_drawn_value():
    """Folding the form judges the sign; the law still runs on the value the
    binding drew (the world is unchanged for a law that loads)."""
    env = Env.standard(seed=3).load("<rate>", text=_doc("!q k * A", "k: !x lognormal(0, 1)"))
    drawn = env.lookup("k")
    world = env.force_all()["w"]
    dt = 1e-4
    state = simulate(world, SimConfig(dt=dt, steps=1, sample_every=1)).states[-1]
    c = next(m for m in state.molecule_ids if m.endswith("C"))
    assert state.get(0, list(state.molecule_ids).index(c)) / dt == pytest.approx(drawn * 2.0, rel=1e-6)  # the law over a reactant is the whole rate: k·[A]


def test_a_bound_modulation_parameter_draw_is_judged_by_its_support():
    verdicts = _verdicts("!q 0.2 * A * inhibitor(D, k)", "k: !x normal(0.5, 0.5)")
    assert len(verdicts) == 1 and "inhibitor.Ki can be negative" in next(iter(verdicts))


# ---- (3) a math call over an undrawn distribution refuses by name -----------


@pytest.mark.parametrize("law", ["!q max(k, 0.05) * A", "!q max(k, 0.05) * A + 0.0", "!q max([k, 0.05]) * A", "!q abs(k) * A"])
def test_a_math_call_over_a_quoted_draw_refuses_by_name(law):
    verdicts = _verdicts(law, "k: !q normal(0.3, 0.3)", seeds=range(5))
    assert len(verdicts) == 1, verdicts
    (message,) = verdicts
    assert "QuotedForm" not in message
    assert "a distribution still to be drawn" in message and "bind the name with !x" in message


def test_the_spellings_the_refusal_names_load():
    assert _verdicts("!q max(normal(0.3, 0.3), 0.05) * A", "", seeds=range(10)) == {"loads"}
    assert _verdicts("!q max(k, 0.05) * A", "k: !x normal(0.3, 0.3)", seeds=range(10)) == {"loads"}


# ---- (2) make_intervention_objective requires the world ---------------------


def test_make_intervention_objective_requires_world():
    from alienbio.suite.arch_intervene import draft_intervention_world, make_intervention_objective

    world, _skeleton, (target_id, target_value) = draft_intervention_world(Seed(2))
    with pytest.raises(TypeError, match="world"):
        make_intervention_objective(target_id, target_value)  # type: ignore[call-arg]
    assert make_intervention_objective(target_id, target_value, world=world).target == target_value


# ---- (5) the conflict scorer reads one compartment --------------------------


@pytest.mark.parametrize("rung", ["single", "latent"])
def test_a_multi_compartment_conflict_world_refuses_at_draft(monkeypatch, rung):
    """Every rung builds one compartment today; a world with two refuses at
    draft by the intervene rule instead of scoring a sum over compartments."""
    from alienbio.bio.world import Compartment
    from alienbio.suite import conflict_gen
    from alienbio.suite.skeleton import Skeleton

    world, _, objective = conflict_gen.draft_conflict_world(Seed(1), rung=rung)
    timeline = simulate(world, SimConfig())
    assert 0.0 < objective.scorer(timeline) <= 1.0  # one compartment: scores as before

    real = Skeleton.materialize

    def two_compartments(self, seed):
        w = real(self, seed)
        return SimpleNamespace(
            chemistry=w.chemistry,
            compartments=(Compartment("root", None, "organism", 1.0), Compartment("cell", "root", "cell", 0.1)),
        )

    monkeypatch.setattr(Skeleton, "materialize", two_compartments)
    with pytest.raises(ValueError, match=r"conflict: target .* can be held in \['root', 'cell'\]"):
        conflict_gen.draft_conflict_world(Seed(1), rung=rung)
