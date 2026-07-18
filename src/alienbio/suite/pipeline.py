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
from typing import Callable, Optional, cast

from ..bio.chemistry import ChemistryImpl
from ..bio.world import Compartment, WorldImpl
from ..infra.mk import mk
from .carve import CarveFail, carve, splice
from .cover import cover
from .dist import Seed
from .grade import grade_answer
from .render import parse, render
from .types import (
    AnswerObjective,
    Motif,
    Question,
    Skeleton,
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


def _carve_or_raise(chem, motif: Motif, seed: Seed) -> Skeleton:
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
    ``cover`` over their feature requirements, drafts one world per task, carves
    + splices each archetype's motif in, builds its ``Question`` + graded
    ``AnswerObjective`` via the archetype's recipe, and (when ``verify_with`` is
    given) reject-samples worlds that fail the validity predicate. Every task's
    question and key are round-trip checked (``parse(render(x)) == x``) and the
    key self-grades to ``1.0`` before packaging — the guard against silent
    ground-truth corruption.

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
        motif = archetype.motif
        recipe = archetype.recipe

        # ── 3. Draft a world (reject-sampling on the validity gate) ─────────
        world = _draft_valid_world(
            motif,
            seed.child(f"draft/{i}"),
            distractor_count=distractor_count,
            verify_with=verify_with,
            max_redraws=max_redraws,
            sim_cfg=sim_cfg,
        )

        # ── 4. Carve + splice the motif into the host ──────────────────────
        skeleton = _carve_or_raise(world.chemistry, motif, seed.child(f"carve/{i}"))
        spliced = splice(world.chemistry, skeleton)
        if skeleton.added:
            # identify_pathway binds fully to existing nodes; a synthesized node
            # would need concentrations for the added ids before we could render.
            raise RuntimeError(
                f"task {i}: unexpected synthesized nodes {skeleton.added} — "
                "world drafting did not host the motif"
            )
        del spliced  # no structural edit for this archetype family; world stands

        vocab = build_vocabulary(world, seed.child(f"vocab/{i}"))

        # ── 5. Build the objective (question + graded key) via the recipe ──
        question = recipe.build_question(skeleton, world)
        key = recipe.build_key(skeleton, world)
        grader = recipe.grader_spec()
        objective = AnswerObjective(grader=grader, key=key)

        # ── 7. Render round-trip + self-grade guard ────────────────────────
        _assert_round_trip(question, key, vocab, archetype.verb, grader)

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


def _assert_round_trip(
    question: Question, key, vocab, verb: str, grader
) -> None:
    """Guard: question + key render/parse losslessly and the key self-grades 1.0."""
    q_back = parse(
        render(question, vocab, verb=verb),
        vocab,
        kind=question.kind,
        as_answer=False,
        verb=verb,
    )
    if q_back != question:
        raise RuntimeError(f"question round-trip failed: {q_back!r} != {question!r}")

    k_back = parse(render(key, vocab), vocab, kind=key.kind, as_answer=True)
    if k_back != key:
        raise RuntimeError(f"key round-trip failed: {k_back!r} != {key!r}")

    score = grade_answer(key, key, grader)
    if score != 1.0:
        raise RuntimeError(f"key does not self-grade to 1.0 (got {score})")
