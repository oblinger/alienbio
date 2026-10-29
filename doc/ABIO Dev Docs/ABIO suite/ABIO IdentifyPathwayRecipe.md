---
description: "`archetypes`: M27.1's archetype catalog, holding `identify_pathway` — a linear-chain motif of molecule-gated roles joined by `reacts_to` edges, and `IdentifyPathwayRecipe`, which asks for the chain between two endpoints and keys the full ordered chain read off the carve. Source: `src/alienbio/suite/archetypes.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO IdentifyPathwayRecipe](ha://p/ABIO%20IdentifyPathwayRecipe) 
# ABIO IdentifyPathwayRecipe
The one carved archetype: a chain motif the pipeline embeds in a drafted host, a question naming its two ends, and the full chain as the key.

![ABIO IdentifyPathwayRecipe](ABIO%20IdentifyPathwayRecipe.svg) 
*The key by construction* is the topic behind the recipe reading the carve (‡: the question already gives the key's first node, which `given_prefix: 1` withholds from the prefix credit, T088).

`suite/archetypes.py` ships the template the other M27 families were modelled on; those three generate their ground truth instead of carving it ([ABIO Generative](ABIO%20Generative.md)). The `identify_pathway` drafter wraps it in a `SuiteSpec` and runs `build_suite` for one task ([ABIO Drafters](ABIO%20Drafters.md)); the `discover` drafter builds on the same substrate. The motif is carved by [ABIO Carve](ABIO%20Carve.md), graded by [ABIO Grade](ABIO%20Grade.md)'s `ordered_path`, and its types are [ABIO Types](ABIO%20Types.md)'s. `identify_pathway` and `IdentifyPathwayRecipe` are re-exported from `alienbio.suite`. The design is [ABIO Suite Construction Data Model](../../ABIO%20Architecture/ABIO%20Suite%20Construction%20Data%20Model.md).



## IdentifyPathwayRecipe Interface
A frozen dataclass implementing the `ObjectiveRecipe` protocol.

| IdentifyPathwayRecipe | |
| --- | --- |
| [role_names](#^role-names) | The chain's roles in order |
| [verb](#^verb) | The question framing |
| [build_question](#^build-question) | The chain's two endpoints |
| [build_key](#^build-key) | The full bound chain |
| [grader_spec](#^grader-spec) | Ordered path, prefix credit past the start |

**role_names**`: tuple[str, ...]`
    `("r0", …, "r{n−1}")`. ^role-names

**verb**`: str = "identify"`
    Selects `"Which pathway connects: …?"` in the render guard. ^verb

**build_question**`(skeleton: CarveResult, world: WorldImpl) -> Question`
    `Question([first, last], "ordered_path")` from `skeleton.binding`. ^build-question

**build_key**`(skeleton: CarveResult, world: WorldImpl) -> Answer`
    `Answer([binding[r] for r in role_names], "ordered_path")`. ^build-key

**grader_spec**`() -> GraderSpec`
    `GraderSpec("ordered_path", {"partial": True, "given_prefix": 1})`: `max(0, lcp − 1) / (max(len) − 1)`, the question's start node earning nothing. ^grader-spec



## archetypes Interface
One constant, one predicate and the factory.

| archetypes | |
| --- | --- |
| [REACTS_TO](#^reacts-to) | The chain's edge tag |
| [_is_molecule](#^is-molecule) | Role gate excluding reactions |
| [identify_pathway](#^identify-pathway) | Build the archetype |

**REACTS_TO**` = "reacts_to"`
    Opaque; carve ignores relation tags and splice realizes it as incidence. ^reacts-to

**_is_molecule**`(node: object) -> bool`
    `not hasattr(node, "reactants")`, so no role binds a reaction node. ^is-molecule

**identify_pathway**`(pathway_length: int, *, constraints: tuple[Predicate, ...] = (), archetype_id: str = "identify_pathway") -> TaskArchetype`
    Roles `r0 … r{n−1}`, each gated by `_is_molecule` plus `constraints`; edges `(r_i, r_{i+1}, "reacts_to")`; empty `FeatureSet`; no drafter, so `build_suite` carves. `ValueError` for `pathway_length < 2`. ^identify-pathway




# IdentifyPathwayRecipe Semantics

## The key by construction
The key is whatever chain `carve` bound, so it is right by construction only if no other chain of the same length joins the endpoints. Over 12 seeds of `pathway_length = 3` through the Expr head, every world had exactly one molecule chain of that length between the endpoints. The question supplies both endpoints, so the grader withholds credit for the given start (`given_prefix: 1`, T088): echoing the question, `[r0, r2]` against the key `[r0, r1, r2]`, scores 0 (0.33 before), a bare `[r0]` 0, and `[r0, r1]` 0.5. The `pathway_puzzles` example shows it: `prefix_credit` (first two of four nodes) 1/3, `echo_credit` 0. That example's agent sees opaque, seed-shuffled names through the example's own `helpers.opaque_host` (T096), not through [ABIO NameMap](ABIO%20NameMap.md): the chain and the distractors are dealt a seed-drawn permutation of `m1` … `mN` and the reactions one of `x1` …, so the route shows only in the reactions and the key varies with the seed. The shared `identify_pathway` drafter is unchanged — it still names the chain `r0` … and its reactions `r0_r1` … (the goldens hold).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and the `identify_pathway` drafter; the 0.33 echo score and the one-chain check over 12 seeds measured on the HEAD export, no spend.
- 2026-10-28 — refreshed against `552c1a7`: `grader_spec` adds `given_prefix: 1`, so echoing the endpoints scores 0 (was 0.33).
- 2026-10-29 — refreshed for `aa53388` (T096): the `pathway_puzzles` example's opaque names come from its `helpers.opaque_host`, not NameMap; the shared drafter is unchanged.
