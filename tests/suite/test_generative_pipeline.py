"""Integration tests: all four M29 archetypes materialize through ``build_suite``.

Wave-1 wired the generator-constructed archetypes (diagnose / predict /
intervene) and the carved one (identify_pathway) into a single
:func:`~alienbio.suite.pipeline.build_suite` path. These tests assert each runs
GREEN end-to-end — sample → draft/carve → objective → consistency guard →
package — and that the guard's ground-truth protections actually fire:

- an **answer** archetype's key round-trips and self-grades to 1.0 (diagnose,
  predict, identify_pathway);
- an **outcome** archetype's scorer yields a coherent score on the drafted world
  (intervene) — carried as an :class:`OutcomeObjective`, not an answer key;
- ``predict``'s non-node response tokens render because ``extra_answer_tokens``
  unions them into the per-world vocabulary;
- a mixed ``Choice`` over answer + outcome archetypes materializes together.
"""

from __future__ import annotations

from alienbio.suite.archetypes import identify_pathway
from alienbio.suite.dist import Choice, Constant, Seed
from alienbio.suite.generative import (
    generative_diagnose,
    generative_intervene,
    generative_predict,
)
from alienbio.suite.grade import grade_answer, grade_outcome
from alienbio.suite.pipeline import build_suite
from alienbio.suite.render import parse, render
from alienbio.suite.types import (
    AnswerObjective,
    OutcomeObjective,
    Suite,
    SuiteSpec,
    TaskArchetype,
)
from alienbio.suite.verify import SimConfig, simulate
from alienbio.suite.vocab import build_vocabulary


def _spec(arch: TaskArchetype) -> SuiteSpec:
    return SuiteSpec(archetype_mix=Constant(arch), per_archetype={}, seed=0)


# ── each archetype materializes green ───────────────────────────────────────


def test_generative_diagnose_materializes_green():
    suite = build_suite(_spec(generative_diagnose(n_nodes=4)), Seed(1), n_tasks=2)
    assert isinstance(suite, Suite)
    assert len(suite.tasks) == 2
    for i, t in enumerate(suite.tasks):
        assert t.archetype == "diagnose_perturbation"
        obj = t.objective
        assert isinstance(obj, AnswerObjective)
        # Key is a real molecule of this world (never a reaction), self-grades 1.0.
        world = suite.worlds[i]
        assert obj.key.value in world.chemistry.molecules
        assert obj.key.value not in world.chemistry.reactions
        assert grade_answer(obj.key, obj.key, obj.grader) == 1.0
        # CarveResult was constructed directly — no carve edits.
        assert t.skeleton.added == () and t.skeleton.removed == ()


def test_generative_predict_materializes_green_with_response_tokens():
    suite = build_suite(_spec(generative_predict(n_nodes=4)), Seed(2), n_tasks=2)
    assert len(suite.tasks) == 2
    for i, t in enumerate(suite.tasks):
        assert t.archetype == "predict_response"
        obj = t.objective
        assert isinstance(obj, AnswerObjective)
        # The key is a response token (not a world node) and self-grades 1.0.
        assert obj.key.value in {"up", "down", "same"}
        world = suite.worlds[i]
        assert obj.key.value not in world.chemistry.molecules
        assert obj.key.value not in world.chemistry.reactions
        assert grade_answer(obj.key, obj.key, obj.grader) == 1.0
        # The key renders only because extra_answer_tokens unioned it into vocab.
        vocab = build_vocabulary(world, extra_tokens=("up", "down", "same"))
        back = parse(render(obj.key, vocab), vocab, kind=obj.key.kind, as_answer=True)
        assert back == obj.key


def test_generative_intervene_materializes_green_as_outcome():
    suite = build_suite(_spec(generative_intervene(n_nodes=4)), Seed(3), n_tasks=2)
    assert len(suite.tasks) == 2
    for i, t in enumerate(suite.tasks):
        assert t.archetype == "design_intervention"
        obj = t.objective
        # Outcome-scored: an OutcomeObjective, not an answer key.
        assert isinstance(obj, OutcomeObjective)
        # The scorer yields a coherent score in (0, 1] on the drafted world; with
        # the default goal (naturally-reached value) it peaks at ~1.0.
        timeline = simulate(suite.worlds[i], SimConfig())
        score = grade_outcome(timeline, obj.scorer, obj.target)
        assert 0.0 < score <= 1.0


def test_generative_identify_still_materializes_green():
    # The carved family is unchanged by the drafter seam (drafter is None).
    suite = build_suite(_spec(identify_pathway(pathway_length=3)), Seed(4), n_tasks=2)
    assert len(suite.tasks) == 2
    for i, t in enumerate(suite.tasks):
        assert t.archetype == "identify_pathway"
        obj = t.objective
        assert isinstance(obj, AnswerObjective)
        mols = set(suite.worlds[i].chemistry.molecules)
        for node in obj.key.value:
            assert node in mols  # every path node is a molecule
        assert grade_answer(obj.key, obj.key, obj.grader) == 1.0


# ── mixing answer + outcome archetypes in one suite ─────────────────────────


def test_mixed_answer_and_outcome_archetypes_materialize_together():
    spec = SuiteSpec(
        archetype_mix=Choice(
            (
                generative_diagnose(n_nodes=4),
                generative_intervene(n_nodes=4),
            )
        ),
        per_archetype={},
        seed=0,
    )
    suite = build_suite(spec, Seed(7), n_tasks=6)
    assert len(suite.tasks) == 6
    kinds = {t.archetype for t in suite.tasks}
    assert kinds <= {"diagnose_perturbation", "design_intervention"}
    for t in suite.tasks:
        if t.archetype == "design_intervention":
            assert isinstance(t.objective, OutcomeObjective)
        else:
            assert isinstance(t.objective, AnswerObjective)


# ── determinism holds across the generated path ─────────────────────────────


def test_generative_build_is_deterministic():
    a = build_suite(_spec(generative_predict(n_nodes=5)), Seed(9), n_tasks=3)
    b = build_suite(_spec(generative_predict(n_nodes=5)), Seed(9), n_tasks=3)
    assert [t.objective.key for t in a.tasks] == [  # type: ignore[union-attr]
        t.objective.key for t in b.tasks  # type: ignore[union-attr]
    ]
    assert [t.question for t in a.tasks] == [t.question for t in b.tasks]


def test_outcome_archetype_without_drafter_objective_is_a_wiring_error():
    # A bare outcome archetype (no drafter, so no per-world objective) must fail
    # loudly in build_suite rather than silently mis-grade.
    import pytest

    from alienbio.suite.arch_intervene import design_intervention

    bare_outcome = design_intervention(target_value=1.0)  # no drafter attached
    with pytest.raises(RuntimeError, match="outcome archetype"):
        build_suite(_spec(bare_outcome), Seed(0), n_tasks=1)
