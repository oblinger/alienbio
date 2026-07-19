"""M27.4 — end-to-end suite construction: ``SuiteSpec -> Suite``.

Composes the eight shipped M26 engines (FT01–FT08) into one materialization
pipeline, supplying them the M27 semantic content (archetypes, vocabularies,
world-validity predicates). The stages follow ``ABIO Semantic Layer`` § M27.4:

    sample archetypes → cover → draft world → carve + splice → build objective
    → (optional) verify reject-sampling → render round-trip check → package.

**Materialization scope.** ``cover`` is computed and its assignment recorded on
each task (which tasks *could* share a world); this build drafts **one world per
task** for unambiguous carving. Physically merging a container's tasks into one
richer shared world (slot-namespaced) is the M28.1 size-dial path and is
deferred — it is an optimization, not a correctness requirement.
"""

from __future__ import annotations

import logging
import math
from typing import Callable, Optional, cast

from ..bio.chemistry import ChemistryImpl
from ..bio.world import Compartment, WorldImpl
from ..infra.mk import mk
from .carve import CarveFail, carve, splice
from .cover import cover
from .dist import Seed
from .grade import grade_answer, grade_outcome
from .render import parse, render
from .types import (
    AnswerObjective,
    CarveResult,
    Motif,
    Objective,
    Question,
    Suite,
    SuiteSpec,
    TaskArchetype,
    TaskInstance,
    Timeline,
)
from .verify import SimConfig, simulate
from .vocab import build_vocabulary

log = logging.getLogger(__name__)

# A world-validity gate: (perturbation, predicate) fed to reject-sampling.
Perturbation = Callable[[WorldImpl], WorldImpl]
ValidityPredicate = Callable[[Timeline, Timeline], bool]


def draft_world(
    motif: Motif,
    seed: Seed = Seed(0),
    *,
    distractor_count: int = 0,
) -> WorldImpl:
    """Draft a host world that ``motif`` embeds into (generic over any motif).

    Instantiates each role as a molecule (node id = role name), each edge as a
    ``a -> b`` reaction, plus ``distractor_count`` off-path molecules — so the
    motif carves in reuse-maximally (identity binding, zero synthesized nodes).
    The single compartment seeds the first chain node high and the rest at zero,
    giving the reaction chain something to propagate.

    ``seed`` varies the reaction *rates* (the dynamics), leaving the molecular
    *structure* — and therefore any carved key — seed-invariant. This makes the
    world deterministic in ``seed`` while giving :func:`_draft_valid_world`'s
    reject-sampling genuinely distinct redraws to explore.

    This is framework machinery: it is parameterized only by the motif's own
    structure and a size dial, never by a hand-authored scenario.
    """
    role_names = [role.name for role in motif.roles]
    molecules = [mk.M(name) for name in role_names]
    by_name = {name: molecules[i] for i, name in enumerate(role_names)}

    reactions = [
        mk.R(
            f"{a}_{b}",
            {by_name[a]: 1.0},
            {by_name[b]: 1.0},
            rate=float(seed.child(f"rate/{a}_{b}").rng().uniform(0.1, 1.0)),
        )
        for (a, b, _tag) in motif.edges
    ]

    distractors = [mk.M(f"d{i}") for i in range(distractor_count)]

    # mk.C is dynamically dispatched (-> Entity); this call yields a ChemistryImpl.
    chem = cast(ChemistryImpl, mk.C("host", molecules + distractors, reactions))

    # Seed the chain's source high so the reactions have substrate to move.
    concentrations: dict[str, float] = {name: 0.0 for name in role_names}
    if role_names:
        concentrations[role_names[0]] = 100.0
    for i in range(distractor_count):
        concentrations[f"d{i}"] = 1.0

    comp = Compartment("cell", None, "cell", 1.0, concentrations=concentrations)
    return WorldImpl(chem, (comp,))


def _carve_or_raise(chem, motif: Motif, seed: Seed) -> CarveResult:
    """Carve ``motif`` into ``chem`` or raise with the failure reason."""
    result = carve(chem, motif, seed)
    if isinstance(result, CarveFail):
        raise RuntimeError(f"carve failed: {result.reason}")
    return result


def build_suite(
    spec: SuiteSpec,
    seed: Seed = Seed(0),
    *,
    n_tasks: int = 1,
    distractor_count: int = 0,
    verify_with: Optional[tuple[Perturbation, ValidityPredicate]] = None,
    max_redraws: int = 8,
    sim_cfg: SimConfig = SimConfig(),
) -> Suite:
    """Materialize ``spec`` into a :class:`Suite` (``n_tasks`` task instances).

    Samples ``n_tasks`` archetypes from ``spec.archetype_mix``, computes a
    ``cover`` over their feature requirements, and materializes each task by ONE
    of two ground-truth paths:

    - **Carved** (``archetype.drafter is None``, e.g. ``identify_pathway``): draft
      a host world, carve + splice the archetype's motif in, and read an
      ``AnswerObjective`` key off the resulting skeleton. Honours ``verify_with``
      reject-sampling on the drafted world.
    - **Generated** (``archetype.drafter`` present, e.g. diagnose / predict /
      intervene): call the drafter for a ``(world, skeleton, objective?)`` whose
      ground truth is a *generation choice* — no carve. When the drafter supplies
      an ``objective`` (outcome archetypes build their own per-world scorer) it is
      used verbatim; otherwise an ``AnswerObjective`` is built from the recipe's
      skeleton-read key.

    The per-world vocabulary unions ``archetype.extra_answer_tokens`` so
    non-node answer tokens (e.g. ``up``/``down``/``same``) can render. Every task
    passes a consistency guard before packaging (``_assert_task_consistent``):
    the question round-trips (``parse(render(q)) == q``); an answer key
    additionally round-trips and self-grades to ``1.0``; an outcome objective's
    scorer produces a finite score in ``(0, 1]`` on the drafted world — the guard
    against silent ground-truth corruption.

    Deterministic in ``(spec, seed, n_tasks, distractor_count)``.
    """
    if n_tasks < 1:
        raise ValueError(f"n_tasks must be >= 1, got {n_tasks}")

    # ── 1. Sample the archetype bag ─────────────────────────────────────────
    archetypes: list[TaskArchetype] = [
        spec.archetype_mix.sample(seed.child(f"arch/{i}")) for i in range(n_tasks)
    ]

    # ── 2. Cover over feature requirements (records task→container grouping) ─
    cov = cover([a.feature_reqs for a in archetypes], seed=seed.child("cover"))

    worlds: list[WorldImpl] = []
    tasks: list[TaskInstance] = []

    for i, archetype in enumerate(archetypes):
        recipe = archetype.recipe

        if archetype.drafter is not None:
            # ── 3g. Generated ground truth: drafter constructs (world, skeleton,
            #        objective?) directly — no carve. ──────────────────────────
            world, skeleton, drafted_objective = archetype.drafter(
                seed.child(f"draft/{i}")
            )
        else:
            # ── 3c. Carved ground truth: draft a host, then carve + splice. ──
            world = _draft_valid_world(
                archetype.motif,
                seed.child(f"draft/{i}"),
                distractor_count=distractor_count,
                verify_with=verify_with,
                max_redraws=max_redraws,
                sim_cfg=sim_cfg,
            )
            skeleton = _carve_or_raise(
                world.chemistry, archetype.motif, seed.child(f"carve/{i}")
            )
            spliced = splice(world.chemistry, skeleton)
            if skeleton.added:
                # identify_pathway binds fully to existing nodes; a synthesized
                # node would need concentrations for the added ids to render.
                raise RuntimeError(
                    f"task {i}: unexpected synthesized nodes {skeleton.added} — "
                    "world drafting did not host the motif"
                )
            del spliced  # no structural edit for this family; world stands
            drafted_objective = None

        vocab = build_vocabulary(
            world, seed.child(f"vocab/{i}"), extra_tokens=archetype.extra_answer_tokens
        )

        # ── 5. Build the objective (question + graded ground truth) ────────
        question = recipe.build_question(skeleton, world)
        objective = _resolve_objective(
            i, archetype, recipe, skeleton, world, drafted_objective
        )

        # ── 7. Consistency guard (question round-trip + key / outcome check) ─
        _assert_task_consistent(question, objective, vocab, archetype.verb, world, sim_cfg)

        worlds.append(world)
        tasks.append(
            TaskInstance(
                archetype=archetype.id,
                world=f"world{i}",
                skeleton=skeleton,
                objective=objective,
                question=question,
                setup={"container": cov.assignment[i]},
            )
        )

    # ── 8. Package ─────────────────────────────────────────────────────────
    return Suite(worlds=tuple(worlds), tasks=tuple(tasks))


def _draft_valid_world(
    motif: Motif,
    seed: Seed,
    *,
    distractor_count: int,
    verify_with: Optional[tuple[Perturbation, ValidityPredicate]],
    max_redraws: int,
    sim_cfg: SimConfig,
) -> WorldImpl:
    """Draft a world, reject-sampling until the validity predicate passes."""
    for attempt in range(max_redraws + 1):
        world = draft_world(
            motif, seed.child(f"attempt/{attempt}"), distractor_count=distractor_count
        )
        if verify_with is None:
            return world
        perturbation, predicate = verify_with
        baseline = simulate(world, sim_cfg, seed.child(f"base/{attempt}"))
        perturbed = simulate(
            perturbation(world), sim_cfg, seed.child(f"pert/{attempt}")
        )
        if predicate(baseline, perturbed):
            return world
        log.info("draft attempt %d rejected by validity predicate; redrawing", attempt)
    raise RuntimeError(
        f"could not draft a world passing the validity predicate in "
        f"{max_redraws + 1} attempts"
    )


def _resolve_objective(
    i: int,
    archetype: TaskArchetype,
    recipe,
    skeleton: CarveResult,
    world: WorldImpl,
    drafted_objective: Optional[Objective],
) -> Objective:
    """Pick the task's objective: drafter-supplied, else answer-key from the recipe.

    A drafter-supplied objective (outcome archetypes build their own per-world
    scorer) is used verbatim. Otherwise the grader kind decides: an ``outcome``
    archetype MUST supply its objective through the drafter (its scorer is
    per-world), so a missing one is a wiring error; every other kind builds an
    :class:`AnswerObjective` from the recipe's skeleton-read key.
    """
    if drafted_objective is not None:
        return drafted_objective

    grader = recipe.grader_spec()
    if grader.kind == "outcome":
        raise RuntimeError(
            f"task {i}: outcome archetype {archetype.id!r} produced no objective — "
            "an outcome archetype must build its per-world scorer in its drafter"
        )
    return AnswerObjective(grader=grader, key=recipe.build_key(skeleton, world))


def _assert_task_consistent(
    question: Question,
    objective: Objective,
    vocab,
    verb: str,
    world: WorldImpl,
    sim_cfg: SimConfig,
) -> None:
    """Guard against silent ground-truth corruption before a task is packaged.

    The question always round-trips (``parse(render(q)) == q``). An
    :class:`AnswerObjective` additionally round-trips its key and self-grades to
    ``1.0``; an :class:`OutcomeObjective`'s scorer must produce a finite score in
    ``(0, 1]`` on the drafted world (a coherent, reachable goal).
    """
    q_back = parse(
        render(question, vocab, verb=verb),
        vocab,
        kind=question.kind,
        as_answer=False,
        verb=verb,
    )
    if q_back != question:
        raise RuntimeError(f"question round-trip failed: {q_back!r} != {question!r}")

    if isinstance(objective, AnswerObjective):
        key = objective.key
        k_back = parse(render(key, vocab), vocab, kind=key.kind, as_answer=True)
        if k_back != key:
            raise RuntimeError(f"key round-trip failed: {k_back!r} != {key!r}")
        score = grade_answer(key, key, objective.grader)
        if score != 1.0:
            raise RuntimeError(f"key does not self-grade to 1.0 (got {score})")
    else:  # OutcomeObjective
        timeline = simulate(world, sim_cfg)
        score = grade_outcome(timeline, objective.scorer, objective.target)
        if not math.isfinite(score) or not (0.0 < score <= 1.0):
            raise RuntimeError(
                f"outcome objective scorer produced an out-of-range score {score!r} "
                "(expected a finite value in (0, 1] on the drafted world)"
            )
