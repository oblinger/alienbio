---
description: "`archetypes`: M27.1's archetype catalog, holding `identify_pathway` — a linear-chain motif of molecule-gated roles joined by `reacts_to` edges, and `IdentifyPathwayRecipe`, which asks for the chain between two endpoints and keys the full ordered chain read off the carve. Source: `src/alienbio/suite/archetypes.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO IdentifyPathwayRecipe](ha://p/ABIO%20IdentifyPathwayRecipe) 
# ABIO IdentifyPathwayRecipe
The one carved archetype: a chain motif the pipeline embeds in a drafted host, a question naming its two ends, and the full chain as the key.

![ABIO IdentifyPathwayRecipe](ABIO%20IdentifyPathwayRecipe.svg) 
*The key by construction* is the topic behind the recipe reading the carve (‡: the question already gives the key's first and last nodes, which `given_prefix: 1` and `given_suffix: 1` withhold from the credit, T088 and T091 AF11).

`suite/archetypes.py` ships the template the other M27 families were modelled on; those three generate their ground truth instead of carving it ([ABIO Generative](ABIO%20Generative.md)). The `identify_pathway` drafter wraps it in a `SuiteSpec` and runs `build_suite` for one task ([ABIO Drafters](ABIO%20Drafters.md)); the `discover` drafter builds on the same substrate. The motif is carved by [ABIO Carve](ABIO%20Carve.md), graded by [ABIO Grade](ABIO%20Grade.md)'s `ordered_path`, and its types are [ABIO Types](ABIO%20Types.md)'s. `identify_pathway` and `IdentifyPathwayRecipe` are re-exported from `alienbio.suite`. The design is [ABIO Suite Construction Data Model](../../ABIO%20Architecture/ABIO%20Suite%20Construction%20Data%20Model.md).



## IdentifyPathwayRecipe Interface
A frozen dataclass implementing the `ObjectiveRecipe` protocol. Construction refuses fewer than `MIN_PATHWAY_LENGTH` roles: the question states both endpoints, so a shorter chain's question would state the whole key.

| IdentifyPathwayRecipe | |
| --- | --- |
| [role_names](#^role-names) | The chain's roles in order |
| [verb](#^verb) | The question framing |
| [build_question](#^build-question) | The chain's two endpoints |
| [build_key](#^build-key) | The full bound chain |
| [grader_spec](#^grader-spec) | Ordered path, credit over the interior |

**role_names**`: tuple[str, ...]`
    `("r0", …, "r{n−1}")`. ^role-names

**verb**`: str = "identify"`
    Selects `"Which pathway connects: …?"` in the render guard. ^verb

**build_question**`(skeleton: CarveResult, world: WorldImpl) -> Question`
    `Question([first, last], "ordered_path")` from `skeleton.binding`, the chain first checked by `check_pathway_key`. ^build-question

**build_key**`(skeleton: CarveResult, world: WorldImpl) -> Answer`
    `Answer([binding[r] for r in role_names], "ordered_path")`, refused unless `check_pathway_key(path, world)` passes. ^build-key

**grader_spec**`() -> GraderSpec`
    `GraderSpec("ordered_path", {"partial": True, "given_prefix": 1, "given_suffix": 1})`: the key's last node is cut off (and off the answer when it ends with it), then `max(0, lcp − 1) / (max(len) − 1)` — the start and end the question states earn nothing, and omitting the end costs nothing. ^grader-spec



## archetypes Interface
Two constants, one predicate, the key check and the factory.

| archetypes | |
| --- | --- |
| [REACTS_TO](#^reacts-to) | The chain's edge tag |
| [MIN_PATHWAY_LENGTH](#^min-pathway-length) | The shortest chain, 3 |
| [_is_molecule](#^is-molecule) | Role gate excluding reactions |
| [check_pathway_key](#^check-pathway-key) | Refuse a key the world does not carry |
| [identify_pathway](#^identify-pathway) | Build the archetype |

**REACTS_TO**` = "reacts_to"`
    Not a modifier relation, so carve reads the edge as a directed reactant → product step and splice realizes it as one. ^reacts-to

**MIN_PATHWAY_LENGTH**` = 3`
    Checked by the recipe, by `identify_pathway` (and so by the drafter's `pathway_length` dial) and by `pathway_puzzles`' `opaque_host` (T091 AF3). ^min-pathway-length

**_is_molecule**`(node: object) -> bool`
    `not hasattr(node, "reactants")`, so no role binds a reaction node. ^is-molecule

**check_pathway_key**`(path: list[str], world: WorldImpl) -> None`
    Raises `ValueError` unless every node is a node of the world (a carve-synthesized `r2#new` is not — carve with `allow_add: False` — nor a hand binding naming an absent id), each step runs the chemistry's way (molecule to molecule through a reaction, molecule to a reaction consuming it, reaction to its product, so an inert end is caught), and no second route between the stated endpoints has the same length and molecule/reaction shape — that one refuses naming both routes, since the question would mark a true route wrong (T091 AF1, AF5). ^check-pathway-key

**identify_pathway**`(pathway_length: int, *, constraints: tuple[Predicate, ...] = (), archetype_id: str = "identify_pathway") -> TaskArchetype`
    Roles `r0 … r{n−1}`, each gated by `_is_molecule` plus `constraints`; edges `(r_i, r_{i+1}, "reacts_to")`; no drafter, so `build_suite` carves. `ValueError` for `pathway_length < MIN_PATHWAY_LENGTH`. ^identify-pathway




# IdentifyPathwayRecipe Semantics

## The key by construction
The key is whatever chain `carve` bound, so it is right only if the world carries it, the right way round, and no other chain of the same length joins the endpoints. That used to be measured (one route in 12 of 12 seeds at `pathway_length = 3`); since `288bf7a` `check_pathway_key` enforces it on every build, through the drafter and the `!identify` head alike. The question supplies both endpoints, so the grader withholds credit for both (`given_prefix: 1`, T088; `given_suffix: 1`, T091 AF11 — appending the end used to double `[r0, r1]`'s credit at three nodes): echoing the question, `[r0, r2]` against the key `[r0, r1, r2]`, scores 0, a bare `[r0]` 0, and `[r0, r1]` 1.0, the one interior node being right. The `pathway_puzzles` example records it (seed 11): first two of four nodes 1/2 (1/3 before), the full chain 1.0, echo and empty 0. That example's agent sees opaque, seed-shuffled names through the example's own `helpers.opaque_host` (T096), not through [ABIO NameMap](ABIO%20NameMap.md): the chain and the distractors are dealt a seed-drawn permutation of `m1` … `mN` and the reactions one of `x1` …, so the route shows only in the reactions and the key varies with the seed. The shared `identify_pathway` drafter is unchanged — it still names the chain `r0` … and its reactions `r0_r1` … (the goldens hold).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and the `identify_pathway` drafter; the 0.33 echo score and the one-chain check over 12 seeds measured on the HEAD export, no spend.
- 2026-10-28 — refreshed against `552c1a7`: `grader_spec` adds `given_prefix: 1`, so echoing the endpoints scores 0 (was 0.33).
- 2026-10-30 — refreshed for `288bf7a` and `8f778bd` (T091 AF1, AF3, AF5, AF11): `MIN_PATHWAY_LENGTH = 3` and `check_pathway_key` (new blocks), the key checked against its world in `build_question` / `build_key`, `given_suffix: 1` so the stated end earns nothing; the `FeatureSet` is gone. Figure's archetype, key, grader and note boxes rewritten.
- 2026-10-29 — refreshed for `aa53388` (T096): the `pathway_puzzles` example's opaque names come from its `helpers.opaque_host`, not NameMap; the shared drafter is unchanged.
