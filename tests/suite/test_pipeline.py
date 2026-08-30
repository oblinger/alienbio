"""Integration tests for M27.4 — ``build_suite`` end-to-end.

Runs a small ``SuiteSpec`` through the whole pipeline (sample → cover → draft →
carve/splice → objective → render round-trip → package) and asserts the
materialized suite is internally consistent: every task's key round-trips
through render/parse and self-grades to 1.0, and the build is deterministic.
"""

from __future__ import annotations

import pytest

from alienbio.bio.world import WorldImpl
from alienbio.suite.archetypes import identify_pathway
from alienbio.suite.dist import Choice, Constant, Seed
from alienbio.suite.grade import grade_answer
from alienbio.suite.pipeline import build_suite, draft_world
from alienbio.suite.render import parse, render
from alienbio.suite.types import AnswerObjective, Suite, SuiteSpec
from alienbio.suite.vocab import build_vocabulary


def _spec(pathway_length: int = 3) -> SuiteSpec:
    arch = identify_pathway(pathway_length=pathway_length)
    return SuiteSpec(archetype_mix=Constant(arch))


# ── draft_world ─────────────────────────────────────────────────────────────


def test_draft_world_hosts_the_motif():
    arch = identify_pathway(pathway_length=3)
    world = draft_world(arch.motif, Seed(0), distractor_count=2)
    assert isinstance(world, WorldImpl)
    mols = world.chemistry.molecules
    for role in arch.motif.roles:
        assert role.name in mols  # every role instantiated as a molecule
    assert "d0" in mols and "d1" in mols  # distractors present


# ── build_suite: one small spec green end-to-end ────────────────────────────


def test_build_suite_materializes_a_green_suite():
    suite = build_suite(_spec(), Seed(1), n_tasks=1, distractor_count=2)
    assert isinstance(suite, Suite)
    assert len(suite.worlds) == 1
    assert len(suite.tasks) == 1
    t = suite.tasks[0]
    assert t.archetype == "identify_pathway"
    assert isinstance(t.objective, AnswerObjective)


def test_every_task_key_round_trips_and_self_grades():
    suite = build_suite(_spec(pathway_length=4), Seed(2), n_tasks=3, distractor_count=1)
    assert len(suite.tasks) == 3
    for i, t in enumerate(suite.tasks):
        world = suite.worlds[i]
        vocab = build_vocabulary(world)
        obj = t.objective
        assert isinstance(obj, AnswerObjective)
        # Key round-trips losslessly.
        back = parse(render(obj.key, vocab), vocab, kind=obj.key.kind, as_answer=True)
        assert back == obj.key
        # Question round-trips with the archetype verb.
        q_back = parse(
            render(t.question, vocab, verb="identify"),
            vocab,
            kind=t.question.kind,
            as_answer=False,
            verb="identify",
        )
        assert q_back == t.question
        # Key self-grades to a perfect score.
        assert grade_answer(obj.key, obj.key, obj.grader) == 1.0


def test_keys_are_molecule_only_never_reaction_nodes():
    # Regression (Fable finding 1): empty role constraints let carve bind pathway
    # roles to reaction nodes, corrupting the ground-truth key. The molecule gate
    # must keep every key node inside the world's molecule namespace.
    for seed_val in range(8):
        suite = build_suite(_spec(pathway_length=3), Seed(seed_val), n_tasks=1, distractor_count=1)
        t = suite.tasks[0]
        obj = t.objective
        assert isinstance(obj, AnswerObjective)
        mols = set(suite.worlds[0].chemistry.molecules)
        rxns = set(suite.worlds[0].chemistry.reactions)
        for node in obj.key.value:
            assert node in mols, f"key node {node!r} is not a molecule (seed {seed_val})"
            assert node not in rxns


def test_draft_world_varies_dynamics_with_seed_but_not_structure():
    # Regression (Fable finding 2): draft_world must actually use its seed.
    from alienbio.suite.pipeline import draft_world

    arch = identify_pathway(pathway_length=3)
    w_a = draft_world(arch.motif, Seed(111), distractor_count=2)
    w_b = draft_world(arch.motif, Seed(999), distractor_count=2)
    # Structure (molecule/reaction ids) is seed-invariant …
    assert list(w_a.chemistry.molecules) == list(w_b.chemistry.molecules)
    assert list(w_a.chemistry.reactions) == list(w_b.chemistry.reactions)
    # … but the dynamics (rates) differ across seeds …
    rates_a = {n: r.rate for n, r in w_a.chemistry.reactions.items()}
    rates_b = {n: r.rate for n, r in w_b.chemistry.reactions.items()}
    assert rates_a != rates_b
    # … and are reproducible for the same seed.
    rates_a2 = {
        n: r.rate
        for n, r in draft_world(arch.motif, Seed(111), distractor_count=2).chemistry.reactions.items()
    }
    assert rates_a == rates_a2


def test_reject_sampling_explores_distinct_worlds():
    # With seed-varying draws, a predicate that rejects the first attempts must
    # eventually accept a later distinct world instead of raising.
    attempts = {"n": 0}

    def predicate(baseline, perturbed):
        attempts["n"] += 1
        return attempts["n"] >= 3  # reject the first two draws

    suite = build_suite(
        _spec(), Seed(2), n_tasks=1,
        verify_with=(lambda w: w, predicate), max_redraws=8,
    )
    assert len(suite.tasks) == 1
    assert attempts["n"] == 3  # recovered on the third distinct draw


def test_key_is_the_bound_chain_read_off_the_skeleton():
    suite = build_suite(_spec(pathway_length=3), Seed(5), n_tasks=1)
    t = suite.tasks[0]
    obj = t.objective
    assert isinstance(obj, AnswerObjective)
    # The key equals the ordered binding of the motif roles — by construction.
    expected = [t.skeleton.binding[name] for name in ("r0", "r1", "r2")]
    assert obj.key.value == expected


def test_build_suite_is_deterministic():
    s1 = build_suite(_spec(), Seed(9), n_tasks=2, distractor_count=2)
    s2 = build_suite(_spec(), Seed(9), n_tasks=2, distractor_count=2)
    assert [t.objective.key for t in s1.tasks] == [t.objective.key for t in s2.tasks]  # type: ignore[union-attr]
    assert [t.question for t in s1.tasks] == [t.question for t in s2.tasks]


def test_cover_assignment_recorded_on_each_task():
    suite = build_suite(_spec(), Seed(3), n_tasks=2)
    for t in suite.tasks:
        assert "container" in t.setup
        assert isinstance(t.setup["container"], int)


def test_n_tasks_below_one_rejected():
    with pytest.raises(ValueError, match="n_tasks must be >= 1"):
        build_suite(_spec(), Seed(0), n_tasks=0)


def test_archetype_mix_choice_is_sampled():
    # A Choice over two pathway lengths still materializes green.
    a3 = identify_pathway(pathway_length=3, archetype_id="p3")
    a4 = identify_pathway(pathway_length=4, archetype_id="p4")
    spec = SuiteSpec(archetype_mix=Choice((a3, a4)))
    suite = build_suite(spec, Seed(11), n_tasks=4)
    assert len(suite.tasks) == 4
    assert {t.archetype for t in suite.tasks} <= {"p3", "p4"}
