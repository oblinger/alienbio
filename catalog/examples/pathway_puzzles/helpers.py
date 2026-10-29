"""helpers.py for the pathway puzzles — thin heads over the pipeline
primitives (grade, render, parse, validity), the coverage predicates,
the knockout perturbation, and the drafter the experiment calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from alienbio.bio.chemistry import ChemistryImpl
from alienbio.bio.world import Compartment, WorldImpl
from alienbio.expr import Env, X, evaluate, fn
from alienbio.infra.mk import mk
from alienbio.suite.experiment import Draft
from alienbio.suite.archetypes import _is_molecule
from alienbio.suite.grade import grade_answer
from alienbio.suite.perturbations import perturb_rate
from alienbio.suite.render import parse, render
from alienbio.suite.types import Answer, AnswerObjective, Question
from alienbio.suite.validity import non_obvious_causal

HERE = Path(__file__).resolve().parent


@fn(summary="score an answer value against an AnswerObjective's key with its grader")
def grade(value: Any, objective: AnswerObjective) -> float:
    return grade_answer(Answer(value=list(value), kind=objective.key.kind), objective.key, objective.grader)


@fn(summary="a Question rendered through a vocabulary (suite.render)")
def render_question(question: Question, vocab: Any) -> str:
    return render(question, vocab, verb="identify")


@fn(summary="the inverse: text back to the Question (suite.render.parse)")
def parse_question(text: str, vocab: Any, kind: str = "ordered_path") -> Question:
    node = parse(text, vocab, kind=kind, verb="identify")
    assert isinstance(node, Question)
    return node


@fn(summary="the chain's role names r0 … r{n-1}")
def chain_names(n: int) -> list[str]:
    return [f"r{i}" for i in range(int(n))]


@fn(summary="the chain's roles, every one a pathway_node")
def chain_roles(n: int) -> dict[str, str]:
    return {name: "pathway_node" for name in chain_names(n)}


@fn(summary="the chain's edges: one reacts_to per step")
def chain_edges(n: int) -> list[list[str]]:
    names = chain_names(n)
    return [[names[i], names[i + 1], "reacts_to"] for i in range(len(names) - 1)]


@fn(summary="every role gated to molecules")
def chain_constraints(n: int) -> dict[str, list[str]]:
    return {name: ["is_molecule"] for name in chain_names(n)}


@fn(summary="a role constraint: the node is a molecule (archetypes._is_molecule)")
def is_molecule(node: Any) -> bool:
    return _is_molecule(node)


# ---- the host: a hidden chain among distractors, under opaque per-seed ids --

@fn(summary="a chain of `pathway_length` molecules among `distractors` inert ones, every id opaque and drawn from the seed")
def opaque_host(pathway_length: int, distractors: int, *, env: Any) -> WorldImpl:
    """The ``identify_pathway`` host (``pipeline.draft_world``'s shape: a
    linear chain seeded at 100 at its start, rates uniform in [0.1, 1.0],
    inert distractors at 1.0) under ids that do not spell the route (T096).

    ``draft_world`` names the chain's molecules after its roles (``r0`` …)
    and its reactions after their ends (``r0_r1``), so the visible ids state
    the answer and every seed shares one key. Here the chain and the
    distractors are dealt a seed-drawn permutation of ``m1`` … ``mN`` (zero-padded to one width) and
    the reactions one of ``x1`` … — the order is in the stoichiometry alone,
    and the key varies with the seed."""
    n, d = int(pathway_length), int(distractors)
    if n < 2 or d < 0:
        raise ValueError(f"opaque_host: pathway_length must be >= 2 and distractors >= 0, got {n}, {d}")
    rng = env.ctx.rng
    width = len(str(n + d))
    names = [f"m{i:0{width}d}" for i in rng.permutation(n + d) + 1]
    chain, filler = names[:n], names[n:]
    molecules = {name: mk.M(name) for name in names}
    rxn_names = [f"x{i:0{len(str(n - 1))}d}" for i in rng.permutation(n - 1) + 1]
    rates = rng.uniform(0.1, 1.0, size=n - 1)
    reactions = [
        mk.R(rxn_names[i], {molecules[chain[i]]: 1.0}, {molecules[chain[i + 1]]: 1.0}, rate=float(rates[i]))
        for i in range(n - 1)
    ]
    chem = mk.C("host", list(molecules.values()), reactions)
    assert isinstance(chem, ChemistryImpl)
    concentrations = {name: 0.0 for name in chain} | {name: 1.0 for name in filler}
    concentrations[chain[0]] = 100.0
    return WorldImpl(chem, (Compartment("cell", None, "cell", 1.0, concentrations=concentrations),))


# ---- coverage predicates: features of a puzzle world ----------------------

@fn(summary="a puzzle whose chain has at most three nodes")
def is_short(world: WorldImpl) -> bool:
    return len(world.chemistry.molecules) <= 6


@fn(summary="a puzzle whose chain has more than three nodes")
def is_long(world: WorldImpl) -> bool:
    return not is_short(world)


@fn(summary="a puzzle whose host has a molecule feeding two reactions")
def is_branched(world: WorldImpl) -> bool:
    seen: set[str] = set()
    for rxn in world.chemistry.reactions.values():
        for m in rxn.reactants:
            if m in seen:
                return True
            seen.add(m)
    return False


@fn(summary="an admissibility rule for cover: a container holds at most two features")
def at_most_two(features: frozenset[Any]) -> bool:
    return len({key for key, _ in features}) <= 2


# ---- reject-sampling: the perturbation and the validity predicate ---------

@fn(summary="the host with its lexically first reaction (a chain step) throttled to a tenth (suite.perturbations)")
def knockout_first(world: WorldImpl) -> WorldImpl:
    return perturb_rate(world, min(world.chemistry.reactions), 0.1)


@fn(summary="validity.non_obvious_causal: the perturbed trajectory must visibly differ")
def non_obvious(baseline: Any, perturbed: Any) -> bool:
    return non_obvious_causal(min_deviation=1e-3)(baseline, perturbed)


@fn(kind="drafter", summary="the pathway puzzles as a drafter: (world, task) with the dials bound")
def puzzles(*, pathway_length: int = 4, distractors: int = 3, env: Any) -> Draft:
    scope = Env.standard(seed=env.ctx.seed, trusted=True).load(HERE / "puzzles.yaml")
    scope.bindings["pathway_length"] = int(pathway_length)
    scope.bindings["distractors"] = int(distractors)
    return Draft(evaluate(X.name("host"), scope), evaluate(X.name("task"), scope))
