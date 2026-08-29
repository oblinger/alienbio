"""Build-suite-ready archetypes with generator-constructed ground truth (M29).

The M29 task families (``diagnose_perturbation``, ``predict_response``,
``design_intervention``) choose their ground truth by *generation* — a drafter
constructs a :class:`~alienbio.suite.types.CarveResult` directly (binding a role to
a chosen node) rather than carving a motif out of a host. Their bare factories
(in ``arch_diagnose`` / ``arch_predict`` / ``arch_intervene``) build the
*recipe + motif* but not the drafter, so they run only in isolation.

This module wires each into a :class:`~alienbio.suite.types.TaskArchetype` that
carries a ``drafter`` (and, for ``predict``, the non-node
``extra_answer_tokens``) so :func:`alienbio.suite.pipeline.build_suite`
materializes them through the same pipeline as the carved ``identify_pathway``.
The wrappers are thin: they reuse each family's bare factory for the recipe and
attach the drafter via :func:`dataclasses.replace`, so there is a single source
of truth for each recipe.

Structural invariance is what makes a *fixed* recipe correct across seeds: each
drafter varies only reaction *rates* (the dynamics), never the molecular
*structure*, so the perturbed/target ids a recipe holds stay valid for every
drafted world. Where the ground truth is a per-world value the recipe cannot
know a priori — the intervention goal defaults to the naturally-reached
concentration — the drafter builds the objective itself and hands it back.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from .arch_diagnose import DEFAULT_HAZARD_RATE, diagnose_perturbation, draft_diagnosis_world
from .arch_intervene import (
    design_intervention,
    draft_intervention_world,
    make_intervention_objective,
)
from .arch_predict import (
    DEFAULT_FACTOR,
    RESPONSE_TOKENS,
    draft_prediction_world,
    predict_response,
)
from .dist import Seed
from .types import CarveResult, Objective, TaskArchetype
from .verify import SimConfig
from ..bio.world import WorldImpl


def generative_diagnose(
    *,
    n_nodes: int = 4,
    distractor_count: int = 3,
    hazard: bool = False,
    hazard_rate: float = DEFAULT_HAZARD_RATE,
    perturbation: Optional[float] = None,
) -> TaskArchetype:
    """A ``diagnose_perturbation`` archetype wired for ``build_suite``.

    The drafter chooses one molecule of an ``n_nodes`` chain as perturbed (a
    seed-varying choice); the recipe reads that molecule off the skeleton, so the
    single bare recipe is correct for every drafted world. Answer-scored, so the
    drafter returns no objective (the pipeline builds the ``AnswerObjective``).
    """

    base = diagnose_perturbation(n_nodes=n_nodes)

    def drafter(seed: Seed) -> tuple[WorldImpl, CarveResult, Optional[Objective]]:
        world, skeleton = draft_diagnosis_world(
            seed,
            n_nodes=n_nodes,
            distractor_count=distractor_count,
            hazard=hazard,
            hazard_rate=hazard_rate,
            perturbation=perturbation,
        )
        return world, skeleton, None

    return replace(base, drafter=drafter)


def generative_predict(
    *, n_nodes: int = 4, factor: float = DEFAULT_FACTOR, ill_posed: bool = False
) -> TaskArchetype:
    """A ``predict_response`` archetype wired for ``build_suite``.

    The perturbed reaction (chain throttle ``m0_m1``) and target molecule
    (terminal sink ``m{n-1}``) are *structural* — seed-invariant — so a fixed
    recipe over those ids recomputes the correct response for every drafted
    world. ``extra_answer_tokens=RESPONSE_TOKENS`` unions the non-node
    ``up``/``down``/``same`` answer tokens into the vocabulary so the key renders.
    """
    if n_nodes < 2:
        raise ValueError(f"n_nodes must be >= 2, got {n_nodes}")

    reaction_id = "m0_m1"  # the chain's throttle — the first reaction
    target_id = f"m{n_nodes - 1}"  # the terminal sink
    base = predict_response(reaction_id, target_id, factor=factor)

    def drafter(seed: Seed) -> tuple[WorldImpl, CarveResult, Optional[Objective]]:
        world, skeleton, drafted_reaction_id = draft_prediction_world(
            seed, n_nodes=n_nodes, factor=factor, ill_posed=ill_posed
        )
        assert drafted_reaction_id == reaction_id, (
            f"drafted perturbed reaction {drafted_reaction_id!r} != recipe's "
            f"{reaction_id!r} — structural invariance broken"
        )
        return world, skeleton, None

    return replace(base, drafter=drafter, extra_answer_tokens=RESPONSE_TOKENS)


def generative_intervene(
    *,
    n_nodes: int = 4,
    target_value: Optional[float] = None,
    sim_cfg: SimConfig = SimConfig(),
) -> TaskArchetype:
    """A ``design_intervention`` archetype wired for ``build_suite`` (outcome-scored).

    The goal is a per-world value (defaulting to the sink's naturally-reached
    concentration), so the drafter — not the recipe — builds the
    :class:`~alienbio.suite.types.OutcomeObjective`: it reads the drafted
    ``(target_id, goal)`` and returns a scorer bound to that world. The recipe's
    own ``target_value`` is unused for grading (the objective is supplied), so it
    is a harmless placeholder when ``target_value`` is left to default.
    """

    base = design_intervention(
        target_value=target_value if target_value is not None else 0.0
    )

    def drafter(seed: Seed) -> tuple[WorldImpl, CarveResult, Optional[Objective]]:
        world, skeleton, (target_id, goal) = draft_intervention_world(
            seed, n_nodes=n_nodes, target_value=target_value, sim_cfg=sim_cfg
        )
        return world, skeleton, make_intervention_objective(target_id, goal)

    return replace(base, drafter=drafter)
