"""T088 primitives round — the suite-primitive module-doc findings.

Each test names its section in the findings doc
(``ABIO088 - Module-doc pass findings …``): ``grade 1`` is § suite/grade 1.
"""

from __future__ import annotations

import pytest

from alienbio.suite.agent import Commit, ScriptedAgent
from alienbio.suite.dist import Seed
from alienbio.suite.drafters import DRAFTERS
from alienbio.suite.experiment import record_from_json, record_to_json
from alienbio.suite.grade import MalformedAnswer, grade_answer
from alienbio.suite.runner import run
from alienbio.suite.types import Answer, GraderSpec


# ── grade 1–3: a wrong-shaped answer scores 0 as data ──────────────────────


def _commit_run(answer: Answer, seed: int = 2):
    world, task = DRAFTERS["discover"](Seed(seed), {"pathway_length": 4, "distractor_count": 2, "symbiosis": 0.8})
    agent = ScriptedAgent(policy=(Commit(answer),), seed=Seed(1))
    return run(world, task, agent, {}, Seed(3))


def test_grade1_integer_on_ordered_path_scores_zero_with_reason():
    record = _commit_run(Answer(value=7, kind="ordered_path"))
    assert record.terminal_reason == "committed"
    assert record.objective_score == 0.0
    assert record.grade_error and "ordered_path" in record.grade_error
    assert not record.is_error
    back = record_from_json(record_to_json(record, "x", 0))
    assert back.grade_error == record.grade_error


def test_grade2_bare_string_is_not_split_into_characters():
    with pytest.raises(MalformedAnswer, match="node_set"):
        grade_answer(Answer("m0", "node_set"), Answer({"m0"}, "node_set"), GraderSpec("node_set"))
    with pytest.raises(MalformedAnswer, match="ordered_path"):
        grade_answer(Answer("m0", "ordered_path"), Answer(["m0"], "ordered_path"), GraderSpec("ordered_path"))
    # the one-id answer in the right shape still grades
    assert grade_answer(Answer(["m0"], "node_set"), Answer({"m0"}, "node_set"), GraderSpec("node_set")) == 1.0


def test_grade_well_shaped_answer_writes_no_grade_error():
    record = _commit_run(Answer(value=[], kind="ordered_path"))
    assert record.grade_error is None
    assert "grade_error" not in record_to_json(record, "x", 0)


def test_grade3_partial_must_be_a_bool():
    with pytest.raises(ValueError, match="partial"):
        grade_answer(Answer(["a"], "node_set"), Answer({"a"}, "node_set"), GraderSpec("node_set", config={"partial": "false"}))
    with pytest.raises(MalformedAnswer, match="scalar"):
        grade_answer(Answer(True, "scalar"), Answer(1.0, "scalar"), GraderSpec("scalar"))


# ── stats 1: the default interval uses the t quantile for the n in hand ────


@pytest.mark.parametrize(
    "df, expected",
    [(1, 12.7062047362), (2, 4.3026527297), (5, 2.5705818356), (30, 2.0422724563), (120, 1.9799304050)],
)
def test_stats1_t_critical_matches_published_quantiles(df, expected):
    from alienbio.suite.stats_summary import t_critical

    assert t_critical(df) == pytest.approx(expected, rel=1e-9)


def test_stats1_default_interval_at_n3_is_the_t_interval():
    from alienbio.suite.stats_summary import mean_confidence_interval, standard_error

    values = [0.0, 0.5, 1.0]
    lo, hi = mean_confidence_interval(values)
    assert (hi - lo) / 2 == pytest.approx(4.3026527297 * standard_error(values), rel=1e-9)
    # an explicit z still wins
    lo, hi = mean_confidence_interval(values, z=1.96)
    assert (hi - lo) / 2 == pytest.approx(1.96 * standard_error(values))


# ── report_text 1: the idle twin is not pooled into the primary contrast ───


def test_report_text1_primary_contrast_excludes_idle_twin():
    from alienbio.suite.report_text import primary_contrast_result
    from alienbio.suite.trial import TrialRecord
    from alienbio.suite.types import Timeline

    def rec(agent, level, score):
        return TrialRecord(
            task_id="w", condition_key=(("agent", agent), ("m", level)), final_timeline=Timeline((), ()),
            deliberation_trace=None, action_log=(), objective_score=score, terminal_reason="committed",
            budget=1.0, spent=0.0, remaining=1.0, illegal_actions=0, turns=1,
        )

    live = [rec("survey-commit", "lo", 0.0), rec("survey-commit", "lo", 0.1), rec("survey-commit", "hi", 1.0), rec("survey-commit", "hi", 0.9)]
    idle = [rec("idle", "lo", 0.0), rec("idle", "lo", 0.0), rec("idle", "hi", 0.0), rec("idle", "hi", 0.0)]

    class _Map:
        records = live + idle

    out = primary_contrast_result(_Map(), {"axis": "m", "low": "lo", "high": "hi"})
    assert out is not None and out["n_low"] == 2 and out["n_high"] == 2
    assert out["cohens_d"] == pytest.approx(12.727922, rel=1e-5)


# ── identify_pathway 1: the question's endpoints earn no credit ────────────


def test_identify_pathway1_echoing_the_question_scores_zero():
    from alienbio.suite.archetypes import identify_pathway

    spec = identify_pathway(pathway_length=3).recipe.grader_spec()
    key = Answer(["r0", "r1", "r2"], "ordered_path")
    assert grade_answer(Answer(["r0", "r2"], "ordered_path"), key, spec) == 0.0
    assert grade_answer(Answer(["r0"], "ordered_path"), key, spec) == 0.0
    assert grade_answer(Answer(["r0", "r1"], "ordered_path"), key, spec) == pytest.approx(0.5)
    assert grade_answer(key, key, spec) == 1.0


# ── perturbations 1–2, carve 2, augment 3: rebuilds keep the dynamics ──────


def _two_comp_world():
    from alienbio.bio.chemistry import ChemistryImpl, _mock_dat
    from alienbio.bio.molecule import MoleculeImpl
    from alienbio.bio.rate_expr import const
    from alienbio.bio.reaction import ReactionImpl
    from alienbio.bio.world import Compartment, DeathLaw, Transport, WorldImpl

    a = MoleculeImpl("A", dat=_mock_dat("mol/A"))
    b = MoleculeImpl("B", dat=_mock_dat("mol/B"))
    r = ReactionImpl("R", reactants={a: 1.0}, products={b: 1.0}, rate=1.0, rate_law=const(3.0),
                     description="law", dat=_mock_dat("rxn/R"))
    chem = ChemistryImpl("c", molecules={"A": a, "B": b}, reactions={"R": r}, dat=_mock_dat("chem/c"))
    comps = (
        Compartment("root", None, "env", 1.0, concentrations={"A": 1.0}),
        Compartment("cell", "root", "cell", 1.0, concentrations={"A": 0.5}),
    )
    tr = Transport(origin="root", dest="cell", stoichiometry={"A": 1.0}, driver_molecule="A", name="t")
    death = DeathLaw(compartment="cell", rate_constant=0.1, name="d")
    return WorldImpl(chem, comps, flows=(tr,), population_laws=(death,))


def test_perturbations_keep_flows_population_laws_and_scale_the_law():
    from alienbio.bio.rate_expr import eval_rate
    from alienbio.suite.perturbations import perturb_rate, remove_reaction

    world = _two_comp_world()
    for edited in (perturb_rate(world, "R", 2.0), remove_reaction(world, "R")):
        assert edited.flows == world.flows and edited.population_laws == world.population_laws
    rxn = perturb_rate(world, "R", 2.0).chemistry.reactions["R"]
    assert rxn.rate_law is not None and eval_rate(rxn.rate_law, lambda _s: 1.0) == 6.0
    assert rxn.description == "law"


def test_spike_keeps_population_laws():
    from alienbio.bio.chemistry import ChemistryImpl, _mock_dat
    from alienbio.bio.molecule import MoleculeImpl
    from alienbio.bio.world import Compartment, DeathLaw, WorldImpl
    from alienbio.suite.perturbations import spike_concentration

    a = MoleculeImpl("A", dat=_mock_dat("mol/A"))
    chem = ChemistryImpl("c", molecules={"A": a}, reactions={}, dat=_mock_dat("chem/c"))
    world = WorldImpl(chem, (Compartment("cell", None, "cell", 1.0, concentrations={"A": 1.0}),),
                      population_laws=(DeathLaw(compartment="cell", rate_constant=0.1),))
    assert spike_concentration(world, "A", 1.0).population_laws == world.population_laws


def test_augment_keeps_flows():
    from alienbio.suite.augment import augment

    world = _two_comp_world()
    grown = augment(world, {"n_species": (4, 0)}, protected={"A", "B", "R"})
    assert len(grown.chemistry.molecules) == 4
    assert grown.flows == world.flows and grown.population_laws == world.population_laws


def test_carve2_splice_keeps_rate_law():
    from alienbio.suite.carve import splice
    from alienbio.suite.types import CarveResult, Motif, RoleSlot

    world = _two_comp_world()
    motif = Motif(roles=(RoleSlot("x", "t"), RoleSlot("r", "t")), edges=(("r", "x", "produces"),))
    out = splice(world.chemistry, CarveResult(motif=motif, binding={"x": "N", "r": "R"}, added=("N",)))
    rxn = out.reactions["R"]
    assert "N" in {m.name for m in rxn.products}
    assert rxn.rate_law == world.chemistry.reactions["R"].rate_law


# ── refresh 1: rate_expr.modulation refuses the Ki that Modulation refuses ─


@pytest.mark.parametrize("ki", [-1.0, float("nan")])
def test_refresh1_modulation_refuses_negative_or_nan_ki(ki):
    from alienbio.bio import rate_expr

    with pytest.raises(ValueError, match="Ki"):
        rate_expr.modulation("inhibitor", "I", {"Ki": ki})
    assert "inhibitor_ratio" in rate_expr.__all__
    assert rate_expr.modulation("inhibitor", "I", {"Ki": 0.0})[3] == {"Ki": 0.0}


# ── generative 1: the intervene goal is read on the episode's horizon ──────


def test_generative1_passive_reach_is_read_at_the_episode_horizon():
    from alienbio.suite.arch_intervene import _final_concentration
    from alienbio.suite.verify import SimConfig, simulate

    world, task = DRAFTERS["intervene"](Seed(10), {"n_nodes": 5, "max_turns": 12, "sim_steps": 10})
    oracle = task.setup["oracle"]["intervene"]
    assert oracle["episode_horizon_s"] == pytest.approx(12.0)
    assert oracle["derivation_horizon_s"] == pytest.approx(12.0)
    do_nothing = simulate(world, SimConfig(dt=0.1, steps=120))
    assert oracle["passive"] == pytest.approx(_final_concentration(do_nothing, oracle["target"]))
    assert task.objective.scorer(do_nothing) == pytest.approx(1.0)


def test_generative1_a_goal_above_the_chain_mass_refuses_at_draft():
    with pytest.raises(ValueError, match="exceeds the 100 units the chain holds"):
        DRAFTERS["intervene"](Seed(2), {"n_nodes": 4, "target_margin": 0.2})  # 50 s default: reach ~100


# ── archetype drafters 1: the diagnose answer is in the dynamics ───────────


def test_archetype_drafters1_diagnose_worlds_differ_with_the_target():
    from alienbio.suite.arch_diagnose import draft_diagnosis_world
    from alienbio.suite.verify import SimConfig, simulate

    finals = {}
    for s in range(12):
        world, sk = draft_diagnosis_world(Seed(s), n_nodes=6)
        target = sk.binding["target"]
        if target in finals or target in ("m0", "m1"):  # m0/m1 share r0
            continue
        state = simulate(world, SimConfig(dt=0.1, steps=60)).states[-1]
        finals[target] = tuple(round(v, 9) for row in state.as_array() for v in row)
    assert len(finals) >= 2
    assert len(set(finals.values())) == len(finals)  # one world per answer
