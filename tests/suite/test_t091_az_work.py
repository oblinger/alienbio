"""T091 round BA — verifier AZ's findings on simulation work and the verify
loop.

AZ1/AZ3: ``verify.step_work`` is a weighted sum (population laws charged per
molecule once any law moves content, flows by their real cost), so a head at
the cap costs about 3 s of CPU on the slowest shape. AZ2: ``!verify`` ticks
the evaluation clock between attempts. AZ7: the work refusal names the
factors of the world that carries the most, and they add up.
"""

from __future__ import annotations

import hashlib
import importlib
import re
import time
from pathlib import Path

import pytest

from alienbio.expr import Env, ExprError
from alienbio.expr.env import Limits

V = importlib.import_module("alienbio.suite.verify")

REPO = Path(__file__).resolve().parents[2]

_POP_SHORT = """
M: 1000
P: 1000
names: !x "[f'm{i}' for i in range(M)]"
mols: !x "dict([[x, {}] for x in names])"
conc: !x "dict([[x, 1.0] for x in names])"
laws: !x "[DeathLaw(compartment='c0', rate=0.0001,
  release_compartment='c0', release_resource='m0',
  release_stoich=0.1) for i in range(P)]"
chem: !Chemistry
  molecules: !x mols
  reactions: {r1: {reactants: [m0], products: [m1], rate: 0.1}}
w: !World
  chemistry: !x chem
  compartments:
    - !Compartment {id: c0, volume: 1.0, multiplicity: 1000.0,
        concentrations: !x conc}
  population_laws: !x laws
q: !predict_q
  world: !x w
  reaction_id: r1
  target_id: m1
  compartment: c0
  sim: !sim {dt: 0.01, steps: 50, sample_every: 50}
"""

_FLOWS_SHORT = """
N: 2000
chem: !Chemistry
  molecules: {x: {}, y: {}}
  reactions: {r1: {reactants: [x], products: [y], rate: 0.01}}
fl: !x "[Transport(origin='a', dest='b', molecule='x',
  rate=0.00001, rate_law='first_order') for i in range(N)]"
w: !World
  chemistry: !x chem
  compartments:
    - !Compartment {id: a, volume: 1.0, concentrations: {x: 5.0}}
    - !Compartment {id: b, parent: a, volume: 1.0}
  flows: !x fl
q: !predict_q
  world: !x w
  reaction_id: r1
  target_id: y
  compartment: a
  sim: !sim {dt: 0.01, steps: 995, sample_every: 995}
"""

_NEAR_MISS = """
names: !x "[f'm{i}' for i in range(50)]"
rxns: !x "dict([[f'r{i}', {'reactants': [names[i]], 'products': [names[(i + 1) % 50]], 'rate_law': ['mul', ['const', 0.5], ['div', ['species', names[i]], ['add', ['const', 1.0], ['species', names[i]]]]]}] for i in range(50)])"
chem: !Chemistry {molecules: !x "dict([[x, {}] for x in names])", reactions: !x rxns}
comps: !x "[Compartment(id='c0', volume=1.0, concentrations={'m0': 5.0})] + [Compartment(id=f'c{i}', parent='c0', volume=1.0, concentrations={'m0': 5.0}) for i in range(1, 5)]"
w: !World {chemistry: !x chem, compartments: !x comps}
q: !predict_q {world: !x w, reaction_id: r0, target_id: m1, factor: 3.0, compartment: c0, sim: !sim {dt: 0.01, steps: 1000, sample_every: 100}}
"""

_RC = """
mols: {{m0: {{}}, m1: {{}}}}
rxns: !x "dict([[f'r{{i}}', {{'reactants': ['m0'], 'products': ['m1'], 'rate': 0.001}}] for i in range({R})])"
chem: !Chemistry {{molecules: !x mols, reactions: !x rxns}}
comps: !x "[Compartment(id='c0', volume=1.0, concentrations={{'m0': 5.0}})] + [Compartment(id=f'c{{i}}', parent='c0', volume=1.0, concentrations={{'m0': 5.0}}) for i in range(1, {C})]"
w0: !World {{chemistry: !x chem, compartments: !x comps}}
"""


def _load(text: str, **kw):
    return Env.standard(seed=0, trusted=False, **kw).load("t.yaml", text=text).force_all()


@pytest.mark.parametrize("text", [_POP_SHORT, _FLOWS_SHORT], ids=["pop_short", "flows_short"])
def test_az1_az3_the_population_and_flow_repros_refuse_in_under_a_second(text):
    """AZ's population-law (27 s of CPU before) and flow (10 s) repros refuse on MAX_EXPR_SIM_WORK in under 1 s of CPU."""
    t = time.process_time()
    with pytest.raises(ExprError, match=f"MAX_EXPR_SIM_WORK={V.MAX_EXPR_SIM_WORK}"):
        _load(text)
    assert time.process_time() - t < 1.0


def _terms(world) -> dict[str, int]:
    return {what: count * weight for what, count, weight in V.work_terms(world)}


def test_az1_a_population_law_walks_every_molecule_once_any_law_moves_content():
    """A death law is charged one law unit alone, and law x molecules carries once any law releases content."""
    base = _POP_SHORT.split("q: !predict_q")[0].replace("P: 1000", "P: 3").replace("M: 1000", "M: 7")
    quiet = base.replace(
        "release_compartment='c0', release_resource='m0',\n  release_stoich=0.1", "release_stoich=0.0"
    )
    moving = _terms(_load(base)["w"])
    still = _terms(_load(quiet)["w"])
    assert still["population laws"] == 3 * V.W_POPULATION_LAW
    assert still["population carries (laws x molecules)"] == 0
    assert moving["population carries (laws x molecules)"] == 3 * 7 * V.W_POPULATION_CARRY


def test_az1_the_near_miss_rate_law_world_loads():
    """A 50-molecule, 5-compartment world of 50 rate-law reactions at 1 000 steps through ``predict_q`` (1.5 s of CPU) loads."""
    out = _load(_NEAR_MISS)
    w = out["w"]
    assert 2 * V.sim_work(w, V.SimConfig(dt=0.01, steps=1000)) <= V.MAX_EXPR_SIM_WORK
    assert "q" in out


def test_az7_the_refusal_names_the_heaviest_worlds_factors_and_they_add_up():
    """The work refusal names the world that carries the most, its listed terms sum to its per-step work, and the per-simulation products sum to the total."""
    small = _load(_RC.format(R=1, C=1))["w0"]
    big = _load(_RC.format(R=1, C=2000))["w0"]
    steps = V.MAX_EXPR_SIM_WORK // V.step_work(big) + 1
    with pytest.raises(ValueError) as info:
        V.check_sim_work("verify", (small, big), V.SimConfig(steps=steps))
    message = str(info.value)
    total = int(re.search(r"would cost (\d+) units", message).group(1))
    sims = re.search(r"units \((.+?) steps x work per step\)", message).group(1)
    products = [tuple(map(int, part.split(" x "))) for part in sims.split(" + ")]
    assert sum(a * b for a, b in products) == total == V.sim_work(small, V.SimConfig(steps=steps)) + V.sim_work(
        big, V.SimConfig(steps=steps)
    )
    which, per_step, detail = re.search(r"simulation (\d+)'s world does (\d+) per step = (.+?) — ", message).groups()
    assert int(which) == 2 and int(per_step) == V.step_work(big)
    terms = [re.fullmatch(r"(\d+) .+ x (\d+)", term).groups() for term in detail.split(" + ")]
    assert sum(int(count) * int(weight) for count, weight in terms) == V.step_work(big)


@pytest.fixture
def _redraw_heads():
    from alienbio.expr import fn

    @fn(name="t091az_same")
    def _same(w):  # type: ignore[no-untyped-def]
        return w

    @fn(name="t091az_never")
    def _never(a, b):  # type: ignore[no-untyped-def]
        return False


def test_az2_verify_ticks_the_evaluation_clock_between_attempts(_redraw_heads):
    """A bound-name world redrawn 400 times under a 1 s clock refuses on the clock, not after every attempt has run."""
    text = _RC.format(R=2, C=100) + (
        "v: !verify {world: !x w0, perturb: t091az_same, valid: t091az_never, max_redraws: 400, "
        "sim: !sim {dt: 0.1, steps: 300, sample_every: 300}}\n"
    )
    t = time.process_time()
    with pytest.raises(ExprError, match="evaluation exceeded limits.seconds=1"):
        _load(text, limits=Limits(seconds=1.0))
    assert time.process_time() - t < 5.0


def test_az2_pathway_puzzles_drafts_as_before_on_seeds_0_to_49():
    """The catalog's ``pathway_puzzles`` (``max_redraws: 16``) drafts the same hosts and keys on seeds 0-49 as before the clock tick."""
    path = REPO / "catalog/examples/pathway_puzzles/puzzles.yaml"
    digest = hashlib.sha256()
    for seed in range(50):
        out = Env.standard(seed=seed, trusted=True).load(str(path)).force_all()
        host, chem = out["host"], out["host"].chemistry
        reactions = sorted(
            (
                name,
                sorted((m.name, s) for m, s in r.reactants.items()),
                sorted((m.name, s) for m, s in r.products.items()),
                r.rate,
            )
            for name, r in chem.reactions.items()
        )
        parts = [
            seed, sorted(chem.molecules), reactions,
            [(c.id, sorted(c.concentrations.items())) for c in host.compartments],
            repr(out["puzzle"]["question"]), repr(out["puzzle"]["objective"]), repr(out["full_credit"]),
        ]
        digest.update(repr(parts).encode())
    assert digest.hexdigest() == "570faae50bf5bf2e488aeaaabac33eb3a3abcdc89601b03e5944efbbc61ec64e"
