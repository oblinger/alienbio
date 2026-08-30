---
description: "Shared data model for the Suite Construction neutral primitives — the domain-neutral contracts (types + adapters over existing ABIO classes) that carve, cover, verify, grade, render, and sample close over. This is the boundary that keeps the primitives implementation-clean."
---
 [[ABIO Architecture Docs]] · [[ABIO Suite Construction]] 

# Suite Construction Data Model
**Subsystem**: [[ABIO Suite Runtime]] > Benchmark generation
The shared contract every [[ABIO Suite Construction]] primitive closes over. Deliberately **domain-neutral**: the primitives reason about graph structure and opaque tags, never about biology. The biology-semantic layer (archetype catalog, vocabularies, predicates, directives) reads and writes the tag content but is authored separately.

## The three load-bearing decisions
1. **World = a bipartite reaction network (Petri-net / SBML style).** Two node kinds — `Species` (state nodes) and `Reaction` (transformations) — with typed weighted edges: reactant/product (with stoichiometry) and modifier (activator/inhibitor, affects a rate without being consumed). Makes stoichiometry + modifiers first-class and is exactly what an ODE integrator consumes.
2. **All domain meaning lives in opaque tag/attr bags, never in the type system.** A `Species` is a state node with an `attrs` dict; the primitives only ever compare structure and tag-equality. This is what makes the primitives implementation-clean and independently testable on synthetic graphs.
3. **These are neutral Protocols/adapters over the *existing* ABIO classes**, not a new data model. See the adapter table below — single source of truth is preserved.

## Two guardrails
- **LLM ops return schema-validated structured output, and are seeded + cached.** Natural language is allowed as *input* (`Directive`) and *output* (rendering), but the machinery between always moves structured, checkable values — or reproducibility and verification break.
- **Natural-language rendering is deterministic templating over a controlled vocabulary — never an LLM.** Research validity requires that a human evaluator know with certainty what an alien-world question/answer *meant*; a paraphrase can drift. LLMs generate/judge (via ops); templates present (faithfully).

## The type model
```
# ── L0 primitives ──────────────────────────────
Seed        # opaque; child seeds derived deterministically: seed.child("species")
NodeId = str
Tags = dict[str, str|float]                 # opaque to all neutral primitives

# ── L1 reaction network (neutral bipartite digraph) ──
Species:  id: NodeId; attrs: Tags                          # scalar state node; meaning is in attrs
RateSpec = Expr                                            # a FORMULA over concs + params + modifiers;
                                                           # mass_action/michaelis_menten/hill are sugar
                                                           # that compile to Expr (ABIO Expr + rate-compiler)
Reaction: id: NodeId
          reactants: list[(NodeId, stoich:int)]
          products:  list[(NodeId, stoich:int)]
          modifiers: list[(NodeId, role:Tag)]              # affects rate, not consumed
          rate: RateSpec
ReactionNetwork: species:{NodeId:Species}; reactions:{NodeId:Reaction}
                 # queries: neighbors(), paths(a,b), subgraph(nodes), match(pattern)

# ── L2 world (physics + space + state) ─────────
Compartment: id; parent: NodeId|None; kind: Tag; volume: float
Topology:    tree[Compartment] + membrane flows
StateVector: dense array [n_compartments × n_species]      # = ABIO WorldState (JAX-friendly)
Trace:       StateVector over time (a trajectory)
World:       network: ReactionNetwork; topology: Topology; initial: StateVector

# ── L3 motif (abstract pattern) vs skeleton (concrete binding) ──
RoleSlot: name; type_tag: Tag; constraints: list[Predicate]    # predicates opaque to neutral code
Motif:    roles: list[RoleSlot]; edges: list[(role,role,relation:Tag)]; params: dict
Skeleton: motif: Motif; binding: {RoleSlot: NodeId}; added: list[NodeId]; removed: list[NodeId]

# ── L4 dynamism seam + covering / envelopes ────
Directive = str                                            # optional natural-language guidance
Op[T]     = ScriptedOp[T] | LLMOp[T]                       # any decision/generator; opaque callable
LLMOp[T]:   directive: Directive; context_schema; out_schema: Schema[T]; seed; cached
FeatureSet:    set[(key, Predicate)]                       # a task's structural requirements on a world
WorldEnvelope: params: ParamSchema; must_satisfy: FeatureSet; directive: Directive|None

# ── L5 question / objective / answer (both human-faithful) ──
Answer:    value: JSON; kind: Tag                          # kind ∈ {node_set|ordered_path|node_id|scalar|json}
Renderable: render(vocabulary) -> text                    # DETERMINISTIC template, exact — never an LLM
Question:  structured: JSON; kind: Tag; +Renderable        # the posed problem, human-faithful
GraderSpec: kind + tolerance/partial-credit config
Objective =

  | AnswerObjective(grader: GraderSpec, key: Answer)                  # agent submits a structured answer
  | OutcomeObjective(scorer: fn(Trace|FinalState)->score, target)    # agent acts; score its effect

# ── L6 distributions everywhere, vector difficulty, worlds as input ──
Dist[T]      # a seeded sampler; may appear ANYWHERE a T is expected; sampled when reached
ParamSchema  # a tree whose leaves may each be a Dist[T]   # ABIO normal()/lognormal()/discrete()
Difficulty = dict[dimension, value]                        # a VECTOR, not a scalar
TaskArchetype: id; motif: Motif; verb: Tag; feature_reqs: FeatureSet; recipe: ObjectiveRecipe
ObjectiveRecipe:  # opaque bundle joining an archetype's world-demand to its grading (Protocol, suite/types.py)
  build_question(skeleton, world) -> Question          # the posed problem (kind matches an FT08 render kind)
  build_key(skeleton, world) -> Answer                 # ground truth, read off the skeleton by construction
  build_distractors(skeleton, world, seed) -> [Answer] # plausible near-misses (MC / incorrect-answer gen)
  grader_spec() -> GraderSpec                           # which FT06 grader + partial-credit config
TaskInstance:  archetype:id; world:id; skeleton:Skeleton; objective:Objective; question:Question; setup:WorldSetup
SuiteSpec: archetype_mix: Dist[TaskArchetype];
           per_archetype: {params: ParamSchema, difficulty: Dist[Difficulty]}; seed
# SuiteGen input also takes available_worlds: list[World]  (reuse-biased; create only as needed)
Suite:     worlds: list[World]; tasks: list[TaskInstance]
```

## Adapters over existing ABIO classes (no parallel model)

| Neutral type | Existing ABIO class |
|---|---|
| `Species` | [[ABIO Molecule]] (as a node) |
| `Reaction` | [[ABIO Reaction]] |
| `RateSpec` | [[ABIO Expr Class]] + the rate-compiler |
| `ReactionNetwork` | [[ABIO Chemistry]] |
| `Compartment` / `Topology` | [[ABIO Compartment]] / [[ABIO CompartmentTree]] |
| `StateVector` / `Trace` | [[ABIO WorldState]] (+ time axis) |
| `World` | Chemistry + CompartmentTree + WorldState |
| `Motif` / `Skeleton` | [[ABIO Pathway]] (extended with role slots / bindings) |
| verification integrator | [[ABIO WorldSimulator]] |
| `Dist` | ABIO `Expr` distributions |

## The neutral / semantic boundary
The primitives (Fable-buildable) close over the types above and treat all `Tags`/`Predicate`/`Directive`/`vocabulary` as opaque. The semantic layer (Opus-authored) supplies their content.

| Engine (neutral) | Semantic content it consumes |
|---|---|
| set-covering solver | what a feature *means* |
| carve/splice | what a role/constraint *means* |
| verification harness | what the predicate *means* |
| graders | what "correct" / "disease-free" *means* |
| Op harness | the directive text |
| NL renderer | the controlled vocabulary |
| Dist sampler | which distributions to use |

## See Also
- [[ABIO Suite Construction]] — the pipeline this model serves.
- [[Suite Construction Fable Tasks]] — the primitive implementation specs built against this model (vault-only tracking).
