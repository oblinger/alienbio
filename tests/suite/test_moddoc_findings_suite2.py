"""Second suite fix round: defects reproduced with the source open.

Each section pins one finding: it failed before its fix and passes after.

A. With no ``levers`` dial the default control surface offered every
   reaction and every visible molecule — including reactions carrying a
   compiled ``rate_law`` (a rate ``Intervene`` there is always rejected) and
   the question's own readout molecule, so on a neutral world setting the
   readout to the goal every turn was accepted (``agent_loop``: 0.85 vs the
   intended 0.25). The 4c readout guard ran on guarded worlds only. Now the
   brief excludes both from the default surface and refuses both declared,
   on every world, and the runner rejects an ``Intervene`` off the brief's
   surface naming the brief's reason.
B. A reloaded map (``experiment.aggregate`` -> ``aggregate_records``) folded
   error records into its cells — one good and one error trial reloaded to
   n = 2 and half the mean — while the live ``MassTrialRunner.run`` map
   excluded them; the reducer now skips ``is_error`` records itself and
   derives ``failed_trials`` from them, so both paths agree.
C. ``estimate_cost`` priced one call per turn: an arm with ``probes`` (a
   forked call per probe per turn, or once ``at_commit``) or ``compact_at``
   (one summarizer call over the displaced history) read low — a two-probe
   arm ~3x. Both are priced now, read high, and the formula names them.
D. A ``TrialError`` partial record carried no ``oracle`` though the oracle
   is known before turn 0, so an error line could not be read against its
   world's ground truth; it carries the oracle and the partial audit's
   ``taint_hits`` now (the answer stays unknown).
E. The preflight ``draft`` check built each condition's brief through a
   copy of ``runner.run``'s pre-turn-0 setup (budget, clock, turn-0
   observation, hidden-pool projection, seeds); both now call
   ``runner.trial_preamble``, so the check can only pass the brief the run
   builds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from alienbio.suite.agent import Intervene, ScriptedAgent, Wait
from alienbio.suite.archetypes import identify_pathway
from alienbio.suite.brief import task_readouts
from alienbio.suite.dist import Constant, Seed
from alienbio.suite.experiment import DRAFTERS, load_spec
from alienbio.suite.pipeline import build_suite
from alienbio.suite.runner import run
from alienbio.suite.types import SuiteSpec

EXAMPLES = Path(__file__).resolve().parents[2] / "catalog" / "examples"


def _example(name: str, spec_file: str):
    spec = load_spec(EXAMPLES / name / spec_file)
    dials = {**spec.fixed_dials, **{k: levels[0] for k, levels in spec.axes if k != "agent"}}
    world, task = DRAFTERS[spec.drafter](Seed(1).child("draft"), dict(dials))
    return world, task, dials


def _pathway_world():
    spec = SuiteSpec(archetype_mix=Constant(identify_pathway(pathway_length=3)))
    suite = build_suite(spec, Seed(1), n_tasks=1, distractor_count=1)
    return suite.worlds[0], suite.tasks[0]


def _with_law(world, reaction_id):
    from alienbio.bio.chemistry import ChemistryImpl
    from alienbio.bio.rate_expr import const, to_json
    from alienbio.bio.reaction import ReactionImpl
    from alienbio.bio.world import WorldImpl
    from alienbio.infra.entity import MockDat

    chem = world.chemistry
    old = chem.reactions[reaction_id]
    reactions = dict(chem.reactions)
    reactions[reaction_id] = ReactionImpl(
        reaction_id, reactants=old.reactants, products=old.products,
        modifiers=old.modifiers, rate=old.rate, rate_law=to_json(const(2.0)),
        dat=MockDat(f"rxn/{reaction_id}"),
    )
    new_chem = ChemistryImpl(
        chem.local_name, atoms=chem.atoms, molecules=chem.molecules,
        reactions=reactions, dat=MockDat(f"chem/{chem.local_name}"),
    )
    return WorldImpl(new_chem, world.compartments, flows=world.flows, population_laws=world.population_laws)


def _wait_agent():
    return ScriptedAgent(lambda obs, sd: (Wait(duration=1.0), ()), Seed(0))


def _setter(lever: str, value: float):
    return ScriptedAgent(lambda obs, sd: (Intervene(lever=lever, value=value), ()), Seed(0))


# A ---------------------------------------------------------------------------


NEUTRAL_READOUTS = [
    ("agent_loop", "agent_loop.yaml", "root/C"),
    ("ecosystem", "ecosystem.yaml", "root/vash.energy.ME2"),
    ("microcosm", "microcosm.yaml", "food"),
    ("organism", "organism.yaml", "lactate"),
    ("kinetics", "kinetics.yaml", "root/Q1"),
]


@pytest.mark.parametrize("name,spec_file,readout", NEUTRAL_READOUTS)
def test_the_default_surface_omits_the_readout_on_a_neutral_world(name, spec_file, readout):
    world, task, dials = _example(name, spec_file)
    assert readout in task_readouts(task, world.chemistry)
    record = run(world, task, _setter(readout, 3.0), dials, Seed(1).child("run"), max_turns=2)
    assert readout not in record.brief.affordances.levers
    # Still measurable: it is the readout, not a hidden pool.
    assert readout in record.brief.affordances.probes
    acts = [a for a in record.action_log if a.kind == "intervene"]
    assert acts and all(not a.accepted for a in acts)
    # T091 K2 — at runtime the agent gets the typo text; the readout reason
    # is for a DECLARED lever (refused at build_brief), which it never sees.
    assert all(a.reason == f"unknown lever {readout!r}" for a in acts)


@pytest.mark.parametrize("name,spec_file,readout", NEUTRAL_READOUTS)
def test_a_declared_readout_lever_is_refused_on_a_neutral_world(name, spec_file, readout):
    world, task, dials = _example(name, spec_file)
    with pytest.raises(ValueError, match="readout"):
        run(world, task, _wait_agent(), {**dials, "levers": [readout]}, Seed(1).child("run"), max_turns=1)


def test_a_diagnose_task_has_no_readout():
    # The answer is a node: the question's named molecules are candidates,
    # not a measurement, so the default surface keeps them.
    world, task, _dials = _example("cascade", "cascade.yaml")
    assert task_readouts(task, world.chemistry) == frozenset()


def test_the_default_surface_omits_a_rate_law_reaction():
    world, task = _pathway_world()
    rxn = sorted(world.chemistry.reactions)[0]
    world = _with_law(world, rxn)
    record = run(world, task, _setter(rxn, 9.0), {}, Seed(5), max_turns=1)
    assert rxn not in record.brief.affordances.levers
    assert set(world.chemistry.reactions) - {rxn} <= set(record.brief.affordances.levers)
    act = record.action_log[0]
    assert not act.accepted and "rate law" in act.reason


def test_the_kinetics_example_offers_no_rate_law_lever():
    world, task, dials = _example("kinetics", "kinetics.yaml")
    laws = {r for r, x in world.chemistry.reactions.items() if x.rate_law is not None}
    assert laws
    brief = run(world, task, _wait_agent(), dials, Seed(1).child("run"), max_turns=1).brief
    assert not laws & set(brief.affordances.levers)


def test_an_unlisted_lever_is_still_unknown():
    world, task = _pathway_world()
    record = run(world, task, _setter("no/such/lever", 1.0), {}, Seed(5), max_turns=1)
    assert "unknown lever" in record.action_log[0].reason


# B ---------------------------------------------------------------------------


def _tiny_world(seed, dials):
    from tests.suite.test_experiment import _tiny_drafter

    return _tiny_drafter(seed, dials)


def test_a_reloaded_map_excludes_error_records_like_the_live_one():
    from alienbio.suite.mass_trial import MassTrialRunner, aggregate_records
    from alienbio.suite.store import record_from_json, record_to_json
    from tests.suite.test_experiment import _tiny_agent_factory

    calls: list[int] = []

    def drafter(seed, dials):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("boom")
        return _tiny_world(seed, dials)

    axes = [("level", ("a",))]
    live = MassTrialRunner().run(axes, drafter, _tiny_agent_factory, trials_per_condition=2, base_seed=Seed(1))
    assert [r.is_error for r in live.records] == [False, True]
    (live_cell,) = live.cells.values()
    assert live_cell.stats.n == 1
    assert live.provenance.failed_trials == 1

    stored = [record_from_json(record_to_json(r, "level=a", i)) for i, r in enumerate(live.records)]
    reloaded = aggregate_records(stored, tuple((n, tuple(v)) for n, v in axes), Seed(1), 2)
    (cell,) = reloaded.cells.values()
    assert cell.stats.n == 1
    assert cell.stats.mean == live_cell.stats.mean
    assert reloaded.provenance.failed_trials == 1
    assert len(reloaded.records) == 2  # the census still sees the error line


# C ---------------------------------------------------------------------------


def _llm_spec(**over):
    import dataclasses

    from alienbio.suite.spec import ExperimentSpec

    base = ExperimentSpec(
        name="est", axes=(), drafter="phase1_pressure", agent="llm",
        trials_per_condition=2, base_seed=1, model="claude-sonnet-5",
        price_usd_per_mtok=(1.0, 2.0), memory="none", expected_turns=4,
        expected_prompt_tokens=100, expected_output_tokens=10,
    )
    return dataclasses.replace(base, **over)


PROBE = {"text": "What do you expect next?", "timing": "every_turn"}


def test_two_every_turn_probes_triple_the_calls_and_the_spend():
    from alienbio.suite.spec import estimate_cost

    plain = estimate_cost(_llm_spec())
    probed = estimate_cost(_llm_spec(fixed_dials={"probes": [PROBE, dict(PROBE, text="And then?")]}))
    assert plain.calls_per_trial == 4
    assert probed.calls_per_trial == 12
    assert probed.input_tokens == 3 * plain.input_tokens
    assert probed.output_tokens == 3 * plain.output_tokens
    assert probed.usd == pytest.approx(3 * plain.usd)
    assert "probe call" in probed.formula and "probe call" not in plain.formula


def test_an_at_commit_probe_adds_one_last_turn_call():
    from alienbio.suite.spec import estimate_cost

    plain = estimate_cost(_llm_spec(memory="full"))
    probed = estimate_cost(_llm_spec(memory="full", fixed_dials={"probes": [dict(PROBE, timing="at_commit")]}))
    assert probed.calls_per_trial == plain.calls_per_trial + 1
    # Read high: the last turn's full-history prompt, 100 * (1 + 3/2).
    assert probed.input_tokens - plain.input_tokens == 2 * 250


def test_a_swept_probe_axis_is_priced_at_its_largest_level():
    from alienbio.suite.spec import estimate_cost

    est = estimate_cost(_llm_spec(axes=(("probes", ((), (PROBE,))),)))
    assert est.calls_per_trial == 8


def test_compaction_adds_one_summarizer_call():
    from alienbio.suite.spec import estimate_cost

    plain = estimate_cost(_llm_spec())
    compact = estimate_cost(_llm_spec(compact_at=2, compact_budget=50))
    assert compact.calls_per_trial == plain.calls_per_trial + 1
    # Prompt = the history up to turn 2 (100 * (1 + 2/2)), reply <= 50.
    assert compact.input_tokens - plain.input_tokens == 2 * 200
    assert compact.output_tokens - plain.output_tokens == 2 * 50
    assert "summarizer call" in compact.formula
    uncapped = estimate_cost(_llm_spec(compact_at=2))
    assert uncapped.output_tokens - plain.output_tokens == 2 * 10


# D ---------------------------------------------------------------------------


class _DiesOnTurn:
    def __init__(self, turn: int) -> None:
        self.turn = turn
        self.calls = 0

    def act(self, observation):
        self.calls += 1
        if self.calls > self.turn:
            raise RuntimeError("provider 500")
        return Wait(duration=1.0), ()


def test_a_crashed_trial_partial_record_carries_the_oracle():
    from alienbio.suite.runner import TrialError

    world, task = DRAFTERS["phase1_pressure"](
        Seed(5).child("d"), {"variant": "coupling_told", "levers": ["root/uptake_route_in", "root/uptake_neutral_in"]}
    )
    dials = {"variant": "coupling_told", "levers": ["root/uptake_route_in", "root/uptake_neutral_in"]}
    with pytest.raises(TrialError) as info:
        run(world, task, _DiesOnTurn(2), dials, Seed(5), max_turns=5)
    partial = info.value.record
    assert partial.is_error
    assert partial.turns == 2
    assert partial.oracle and partial.oracle["phase1"] == task.setup["oracle"]["phase1"]
    assert partial.taint_hits == ()
    assert partial.answer is None


def test_the_terminal_reason_docstring_lists_every_value_the_runner_emits():
    import re

    from alienbio.suite import runner as runner_mod
    from alienbio.suite.trial import TrialRecord

    source = Path(runner_mod.__file__).read_text()
    emitted = set(re.findall(r'reason = "(\w+)"', source)) | set(re.findall(r'terminal_reason="(\w+)"', source))
    assert {"committed", "budget_exhausted", "max_turns", "illegal_limit", "error"} <= emitted
    doc = TrialRecord.__doc__ or ""
    for value in emitted:
        assert f'"{value}"' in doc, value


# E ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dials",
    [
        {"variant": "coupling_told", "levers": ["root/uptake_route_in", "root/uptake_neutral_in"]},
        {
            "variant": "coupling_unobservable",
            "levers": ["root/uptake_route_in", "root/uptake_neutral_in"],
            "max_turns": 3, "sim_steps": 20, "sim_dt": 0.02, "budget": 40,
        },
    ],
)
def test_the_draft_check_builds_the_brief_the_run_builds(dials):
    from alienbio.suite.guards import _first_brief

    trial_seed = Seed(9).child("cond/0")
    world, task = DRAFTERS["phase1_pressure"](trial_seed.child("draft"), dict(dials))
    record = run(world, task, _wait_agent(), dials, trial_seed.child("run"))
    assert _first_brief(world, task, dials, trial_seed) == record.brief


def test_the_run_and_the_draft_check_share_one_preamble():
    import inspect

    from alienbio.suite import guards, runner as runner_mod

    assert "trial_preamble(" in inspect.getsource(runner_mod.run)
    first = inspect.getsource(guards._first_brief)
    assert "trial_preamble(" in first
    assert "narrow_observation" not in first and "build_brief(" not in first
