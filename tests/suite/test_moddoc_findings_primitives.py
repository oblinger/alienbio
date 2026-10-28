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


# ── registration 1: a repeated id refuses ──────────────────────────────────


def test_registration1_duplicate_id_refuses(tmp_path):
    from alienbio.suite.registration import load_registry

    entry = "  osf: abcde\n  filed: '2026-01-01'\n  dials: [{d}]\n  drafters: [pressure]\n"
    path = tmp_path / "registrations.yaml"
    path.write_text("a:\n" + entry.format(d="pi") + "a:\n" + entry.format(d="pi, stakes"))
    with pytest.raises(ValueError, match="duplicate key 'a'"):
        load_registry(path)
    path.write_text("a:\n" + entry.format(d="pi"))
    assert set(load_registry(path)) == {"a"}


# ── boundedness 1: a closed world's terminal product is not an accumulator ─


def test_boundedness1_closed_batch_is_bounded_a_sourced_chain_is_not():
    from alienbio.infra.mk import mk
    from alienbio.suite.boundedness import static_bounded_fate

    a, b, c = mk.M("a"), mk.M("b"), mk.M("c")
    closed = mk.C("closed", [a, b, c], [mk.R("r1", {a: 1.0}, {b: 1.0}), mk.R("r2", {b: 1.0}, {c: 1.0})])
    assert static_bounded_fate(closed) == []
    a2, b2 = mk.M("a"), mk.M("b")
    sourced = mk.C("sourced", [a2, b2], [mk.R("src", {}, {a2: 1.0}), mk.R("r1", {a2: 1.0}, {b2: 1.0})])
    assert [p.name for p in static_bounded_fate(sourced)] == ["b"]


# ── carve 1: an edge's relation tag is part of the match ───────────────────


def test_carve1_a_catalyst_edge_is_not_satisfied_by_a_substrate():
    from alienbio.infra.mk import mk
    from alienbio.suite.carve import CarveFail, carve
    from alienbio.suite.types import Motif, RoleSlot

    def is_mol(n):
        return not hasattr(n, "reactants")

    def is_rxn(n):
        return hasattr(n, "reactants")

    e, p = mk.M("e"), mk.M("p")
    host = mk.C("h", [e, p], [mk.R("r", {e: 1.0}, {p: 1.0})])
    motif = Motif(roles=(RoleSlot("E", "cat", (is_mol,)), RoleSlot("R", "rxn", (is_rxn,))), edges=(("E", "R", "catalyzes"),))
    assert isinstance(carve(host, motif, allow_add=False), CarveFail)
    e2, p2, k = mk.M("e"), mk.M("p"), mk.M("k")
    host2 = mk.C("h2", [e2, p2, k], [mk.R("r", {e2: 1.0}, {p2: 1.0}, modifiers={k: "catalyst"})])
    out = carve(host2, motif, allow_add=False)
    assert not isinstance(out, CarveFail) and out.binding == {"E": "k", "R": "r"}


# ── validity 1: a heuristic that recovers half the answer cracks it ────────


def test_validity1_partial_top_k_recovery_is_not_resistant():
    from alienbio.infra.mk import mk
    from alienbio.suite.validity import is_shortcut_resistant

    h, a, b, c, d = (mk.M(n) for n in "habcd")
    hub = mk.C("hub", [h, a, b, c, d], [mk.R("r1", {h: 1.0}, {a: 1.0}), mk.R("r2", {h: 1.0}, {b: 1.0}), mk.R("r3", {h: 1.0}, {c: 1.0}), mk.R("r4", {d: 1.0}, {a: 1.0})])
    assert not is_shortcut_resistant(hub, {"h"})
    assert not is_shortcut_resistant(hub, {"h", "d"})  # the degree pick is half of it
    assert is_shortcut_resistant(hub, {"b", "c", "d"})


# ── cover 1: features compare by key, not predicate object ─────────────────


def test_cover1_items_naming_one_key_share_it():
    from alienbio.suite.cover import cover
    from alienbio.suite.types import FeatureSet

    a = FeatureSet(features=frozenset({("x", lambda w: True)}))
    b = FeatureSet(features=frozenset({("x", lambda w: True)}))
    out = cover([a, b])
    assert len(out.containers) == 1 and out.assignment == (0, 0)


# ── dist 1: two places never share a draw ──────────────────────────────────


def test_dist1_paths_that_spell_the_same_string_draw_independently():
    from alienbio.suite.dist import ParamSchema, Uniform

    u = Uniform(0.0, 1.0)
    out = ParamSchema({"a/b": u, "a": {"b": u}}).sample(Seed(3))
    assert out["a/b"] != out["a"]["b"]
    out = ParamSchema({"x": {"0": u}, "y": [u]}).sample(Seed(3))
    keyed = ParamSchema({"x": {"0": u}}).sample(Seed(3))["x"]["0"]
    listed = ParamSchema({"x": [u]}).sample(Seed(3))["x"][0]
    assert keyed != listed


# ── verify 1: SimConfig refuses what the simulator cannot run ─────────────


@pytest.mark.parametrize(
    "kwargs, field",
    [({"sample_every": 0}, "sample_every"), ({"steps": -1}, "steps"), ({"steps": 0}, "steps"),
     ({"dt": 0.0}, "dt"), ({"dt": -0.1}, "dt"), ({"dt": float("inf")}, "dt"), ({"steps": 2.5}, "steps"), ({"steps": True}, "steps")],
)
def test_verify1_simconfig_validates(kwargs, field):
    from alienbio.suite.verify import SimConfig

    with pytest.raises(ValueError, match=f"SimConfig.{field}"):
        SimConfig(**kwargs)


# ── render 1: no phrase may hold half the separator ────────────────────────


@pytest.mark.parametrize("phrase", ["a |", "| b", "a|b"])
def test_render1_a_bar_anywhere_in_a_phrase_refuses(phrase):
    from alienbio.suite.render import Vocabulary

    with pytest.raises(ValueError, match="separator"):
        Vocabulary(phrases={"x": phrase, "y": "b"})


# ── info_seeking 1: rejected actions count neither way ─────────────────────


def test_info_seeking1_rejected_actions_are_not_counted():
    from alienbio.suite.info_seeking import ActionRecord, actions_before_commit, destructive_rate, info_seeking_ratio

    log = [ActionRecord(kind="measure", accepted=False), ActionRecord(kind="commit", accepted=False)]
    assert info_seeking_ratio(log, {"measure"}) == 0.0
    assert actions_before_commit(log, {"commit"}) == 0
    log = [ActionRecord(kind="measure"), ActionRecord(kind="intervene", destructive=True, accepted=False), ActionRecord(kind="commit")]
    assert info_seeking_ratio(log, {"measure"}) == 0.5
    assert destructive_rate(log) == 0.0
    assert actions_before_commit(log, {"commit"}) == 1


# ── CellStats 1: keys equal under == but not in type refuse ────────────────


def test_cellstats1_true_one_and_one_point_oh_do_not_merge():
    from alienbio.suite.reliability_grid import aggregate_cells

    with pytest.raises(ValueError, match="compare equal but differ"):
        aggregate_cells([((("flag", True),), 1.0), ((("flag", 1),), 0.0), ((("flag", 1.0),), 0.5)])
    out = aggregate_cells([((("flag", True),), 1.0), ((("flag", True),), 0.0), ((("flag", False),), 0.5)])
    assert out[(("flag", True),)].n == 2
