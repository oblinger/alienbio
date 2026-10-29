"""T091 verifier M's follow-ups on rounds H and J: modulation parameters
under the sign rule, ``choice`` supports and unsupported dist heads, the
folded negative constant, ``log`` / ``min`` / ``max`` / ``pow`` intervals,
a torn ``records.retried.jsonl`` refused before a resume moves anything,
count flows in ``target_holders``, and ``predict`` reading one compartment.
The exhausted-pool boundary (M1) is an ``@example`` on the conformance
property (``tests/capabilities/test_simulator_conformance.py``)."""

from __future__ import annotations

import json

import pytest

from alienbio.expr import Env, ExprError, X, evaluate
from alienbio.suite.experiment import ExperimentSpec, run_experiment
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


def _rate(rate: str, pre: str = "", seed: int = 1) -> float:
    dt = 1e-4
    state = simulate(_load(rate, pre, seed), SimConfig(dt=dt, steps=1, sample_every=1)).states[-1]
    mols = list(state.molecule_ids or ())
    return state.get(0, mols.index(next(m for m in mols if m.endswith("C")))) / dt


# ---- M2: modulation parameters carry the sign rule --------------------------


@pytest.mark.parametrize(
    "rate, param",
    [
        ("!q inhibitor(B, k) * A", "inhibitor.Ki"),
        ("!q michaelis(B, k) * A", "michaelis.K"),
        ("!q michaelis(B, 0.5, Vmax=k) * A", "michaelis.Vmax"),
        ("!q activator(B, k) * A", "activator.a"),
        ("!q hill(B, k) * A", "hill.K"),
        ("!q hill(B, 0.5, Vmax=k) * A", "hill.Vmax"),
        ("!q 2 * michaelis(B, k) + A", "michaelis.K"),  # inside a sum too
    ],
)
def test_a_drawn_modulation_parameter_below_zero_refuses_on_every_seed(rate, param):
    for seed in range(6):
        with pytest.raises(ExprError, match=rf"{param} can be negative — k \(bound to .*\) has support \[-4, 1\]"):
            _load(rate, "k: !q uniform(-4, 1)", seed)


def test_a_hill_k_that_can_be_zero_needs_a_point_integer_n():
    with pytest.raises(ExprError, match=r"hill\.K can be 0 .* non-negative integer n"):
        _load("!q hill(B, k, n=1.5) * A", "k: !q uniform(0, 1)")
    with pytest.raises(ExprError, match=r"hill\.K can be 0"):
        _load("!q hill(B, k, n=m) * A", "k: !q uniform(0, 1)\nm: !q uniform(1, 3)")
    assert _rate("!q hill(B, k) * A", "k: !q uniform(0, 1)") > 0.0  # default n = 2
    assert _rate("!q hill(B, 0.5, n=m) * A", "m: !q uniform(-3, 1)") > 0.0  # K > 0: any n


def test_non_negative_modulation_supports_load():
    pre = "k: !q uniform(0.1, 1)"
    for rate in ("!q inhibitor(B, k) * A", "!q michaelis(B, k, Vmax=k) * A", "!q activator(B, k) * A"):
        assert _rate(rate, pre) > 0.0


# ---- M3: choice, and unsupported dist heads ---------------------------------


def test_an_all_positive_choice_loads_and_a_mixed_sign_choice_refuses():
    for seed in range(4):
        assert _rate("!q choice([0.1, 0.2]) * A", seed=seed) > 0.0
        assert _rate("!q k * A", "k: !q choice([0.1, 0.2])", seed) > 0.0
    with pytest.raises(ExprError, match=r"support \[-0\.1, 0\.2\]"):
        _load("!q choice([-0.1, 0.2]) * A")


def test_a_dist_head_with_no_support_rule_refuses_as_unsupported():
    from alienbio.suite.rate_law import SUPPORTED_DIST_HEADS, _dist_head_support

    assert "choice" in SUPPORTED_DIST_HEADS
    with pytest.raises(ExprError, match=r"coin\(\.\.\.\) is unsupported for a support check"):
        _dist_head_support("coin", [], {}, Env.standard(seed=1))


# ---- lows: the folded constant, and log / min / max / pow intervals ---------


def test_the_negative_constant_message_divides_by_a_divisor():
    with pytest.raises(ExprError, match=r"negative rate constant -0\.05 "):
        _load("!q 0.2 / -4 * A")


@pytest.mark.parametrize(
    "rate, pre",
    [
        ("!q log(k) * A", "k: !q uniform(2, 3)"),
        ("!q k ** 2 * A", "k: !q uniform(-1, 1)"),
        ("!q k ** 3 * A", "k: !q uniform(0.1, 1)"),
        ("!q max(0.2, 0.05) * A", ""),
        ("!q min(0.2, 1) * A", ""),
    ],
)
def test_positive_by_construction_constants_load(rate, pre):
    assert _rate(rate, pre) >= 0.0


@pytest.mark.parametrize(
    "rate, pre",
    [
        ("!q log(k) * A", "k: !q uniform(0.5, 3)"),  # log crosses zero at 1
        ("!q k ** 3 * A", "k: !q uniform(-1, 1)"),  # an odd power keeps the sign
        ("!q min(k, 1) * A", "k: !q uniform(-0.5, 0.2)"),
    ],
)
def test_the_interval_rules_still_refuse_a_straddling_constant(rate, pre):
    with pytest.raises(ExprError, match="negative rate constant possible"):
        _load(rate, pre)


# ---- M4: a torn records.retried.jsonl refuses before a resume moves anything --


def test_a_torn_retried_tail_refuses_a_no_ceiling_resume_and_rewrites_nothing(tmp_path):
    spec = ExperimentSpec(
        name="torn-retried",
        axes=(("rung", ("single",)),),
        drafter="conflict",
        agent="idle",
        trials_per_condition=2,
        base_seed=1,
        fixed_dials={"levers": []},
    )
    assert spec.cost_ceiling_usd is None
    out = tmp_path / "run"
    run_experiment(spec, out_dir=str(out))
    records = out / "records.jsonl"
    lines = records.read_text().splitlines()
    first = json.loads(lines[0])
    first["error"] = "RuntimeError: boom"
    lines[0] = json.dumps(first, sort_keys=True)
    records.write_text("\n".join(lines) + "\n")
    retried = out / "records.retried.jsonl"
    retried.write_text('{"label": "torn", "ind')  # a torn last line, no newline
    before = (records.read_bytes(), retried.read_bytes())

    with pytest.raises(ValueError, match=r"records\.retried\.jsonl: line 1 is not valid JSON"):
        run_experiment(spec, out_dir=str(out), resume=True)
    assert (records.read_bytes(), retried.read_bytes()) == before


def test_the_store_refuses_to_append_onto_a_torn_retried_tail(tmp_path):
    from alienbio.suite.store import StoreError, _append_retried

    path = tmp_path / "records.retried.jsonl"
    path.write_text('{"a": 1}\n{"b"')
    with pytest.raises(StoreError, match="no trailing newline"):
        _append_retried(path, ['{"c": 3}'])
    assert path.read_text() == '{"a": 1}\n{"b"'


# ---- M7: a count flow carries its origin's contents to its dest -------------

_COUNT_FLOW = """
chem: !Chemistry
  molecules: [P, food]
  reactions:
    drain: {reactants: [food], products: [], rate: 0.01}
world: !World
  chemistry: !x chem
  compartments:
    - !Compartment {id: pond, kind: environment, volume: 10.0, concentrations: {food: 4.0}}
    - !Compartment {id: juveniles, parent: pond, kind: population, volume: 0.1, multiplicity: 20.0, concentrations: {P: 5.0}}
    - !Compartment {id: adults, parent: pond, kind: population, volume: 0.2, multiplicity: 5.0}
  population_laws:
    - !CountFlow {origin: juveniles, dest: adults, rate: 0.1}
"""


def test_a_target_carried_by_a_count_flow_is_held_at_its_dest():
    from alienbio.suite.arch_intervene import target_compartment, target_holders

    world = evaluate(X.name("world"), Env.standard(seed=1).load("<cf>", text=_COUNT_FLOW))
    assert target_holders(world, "P") == ["juveniles", "adults"]
    with pytest.raises(ValueError, match=r"can be held in \['juveniles', 'adults'\]"):
        target_compartment(world, "P")
    assert target_compartment(world, "P", "adults") == "adults"


# ---- M11: predict reads one compartment, by the intervene rule --------------


def test_predict_refuses_an_ambiguous_world_and_reads_the_named_compartment():
    from alienbio.suite.arch_predict import predicted_response

    text = (
        "chem: !Chemistry\n"
        "  molecules: [S, P]\n"
        "  reactions:\n"
        "    conv: {reactants: [S], products: [P], rate: 0.5}\n"
        "world: !World\n"
        "  chemistry: !x chem\n"
        "  compartments:\n"
        "    - !Compartment {id: a, volume: 1.0, concentrations: {S: 4.0}}\n"
        "    - !Compartment {id: b, parent: a, volume: 1.0, concentrations: {S: 2.0}}\n"
    )
    world = evaluate(X.name("world"), Env.standard(seed=1).load("<p>", text=text))
    cfg = SimConfig(dt=0.1, steps=10)
    with pytest.raises(ValueError, match=r"predict: target 'P' can be held in \['a', 'b'\].*compartment=<id>"):
        predicted_response(world, "P", "conv", 3.0, cfg)
    assert predicted_response(world, "P", "conv", 3.0, cfg, compartment="b") == "up"


def test_the_organism_example_names_its_compartment_and_keeps_its_answer():
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "catalog/examples/organism/organism.yaml"
    task = evaluate(X.name("task"), Env.standard(seed=1, trusted=True).load(path))
    assert task.objective.key.value == "down"  # compartments[0] = organism read "down" before the rule too
