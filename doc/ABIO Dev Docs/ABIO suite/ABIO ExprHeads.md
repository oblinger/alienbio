---
description: "`expr_heads`: layers 0–2 of the Expr head catalog — the block heads over `suite/blocks.py` with pools taken as names (`source`, `sink`, `reaction`, `crux`, `signal`, `inhibit`, `enzyme`, `cooperative`, `insult`, `transport`, `lattice`, `population`, `block`, `skeleton`), `RateLawBlock` for a compiled rate law, the world heads (`world`, `sim`, the `verify` expander, the six generator worlds), and the constructor heads (`!Molecule`, `!Reaction`, `!Chemistry`, `!Compartment`, `!Transport`, `!GrowthLaw`, `!DeathLaw`, `!CountFlow`, `!World`). Source: `src/alienbio/suite/expr_heads.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO ExprHeads](ha://p/ABIO%20ExprHeads) 
# ABIO ExprHeads
The page for the heads a spec uses to build chemistry: how a block head turns pool names into ports, how `block` wires children that name the same pool, how `world` materializes a skeleton under the node's seed, what `verify` redraws, and what each constructor head builds.

![ABIO ExprHeads](ABIO%20ExprHeads.svg) 
*Pools as names* is the topic behind the `block` node (children naming one pool share it through one parent port); *Dist slots* governs every `rate`-like argument; *verify's redraws* governs the `attempt` edge (‡ marks that a redraw keeps a template's instance name).

`expr_heads.py` re-implements nothing generative: every head is a thin registration over a class or function that already exists — the blocks of [ABIO Blocks](ABIO%20Blocks.md), the tree and `materialize` of [ABIO Skeleton](ABIO%20Skeleton.md), the generators of [ABIO PressureGen](ABIO%20PressureGen.md), [ABIO ConflictGen](ABIO%20ConflictGen.md) and [ABIO DeltaGen](ABIO%20DeltaGen.md), the world records of [ABIO WorldImpl](../ABIO%20bio/ABIO%20WorldImpl.md) and the chemistry of [ABIO ChemistryImpl](../ABIO%20bio/ABIO%20ChemistryImpl.md). A `rate:` slot is compiled by [ABIO RateLaw](ABIO%20RateLaw.md). Pool names are namespaced by `Env.pool` ([ABIO Env](../ABIO%20expr%20Modules/ABIO%20Env.md)); the heads register through `fn` and `expander` ([ABIO Registry](../ABIO%20expr%20Modules/ABIO%20Registry.md)) when `Env.standard` imports this module. Layers 3–6 (tasks, briefs, episodes, experiments) are [ABIO ExprExperiment](ABIO%20ExprExperiment.md). The head catalog by layer, with examples, is [ABIO Expr Templates](../../ABIO%20Design/ABIO%20Expr/ABIO%20Expr%20Templates.md).



## Block heads
Layer 1, all kind `fn`, all with `env` injected. Each returns a block; a pool argument is a name passed through `Env.pool`, and the block's node name is `name=` or the key the call is bound to. A `rate` or other numeric parameter is a Dist slot (§ [Dist slots](#dist-slots)); omitted, the block class's default applies.

| Block heads | |
| --- | --- |
| [source](#^source) | `∅ → pool` |
| [sink](#^sink) | `pool → ∅` |
| [reaction](#^reaction) | One reaction over named pools, any rate law |
| [crux](#^crux) | A precursor into two rival routes |
| [signal](#^signal) | `in → out` modulated by a sensed pool |
| [inhibit](#^inhibit) | `in → out` throttled by a modifier |
| [enzyme](#^enzyme) | Catalysed `substrate → product` |
| [cooperative](#^cooperative) | Hill-shaped response to a modifier |
| [insult](#^insult) | A drain, optionally a Poisson insult schedule |
| [transport](#^transport) | A flux of one pool between two compartments |
| [lattice](#^lattice) | A `k`-cell diffusion chain |
| [population](#^population) | Counts with growth and death on a resource |
| [block](#^block) | A pattern node binding children by pool name |
| [skeleton](#^skeleton) | Root, control surface and crux |

**source**`(pool="out", rate=None, container=None, name=None)`
    `SourceBlock.make`, its one port the pool. ^source

**sink**`(pool="in", rate=None, container=None, name=None)`
    `SinkBlock.make`. ^sink

**reaction**`(reactants=(), products=(), rate=None, stoich=None, container=None, role="supply", name=None)`
    Refuses with no pool on either side. Compiles `rate` with the reactant and product pools ([ABIO RateLaw](ABIO%20RateLaw.md)). A plain constant returns a `ReactionBlock`; a law with modulations or an expression returns a `RateLawBlock` whose extra `IN` ports are the modifier pools and the pools the expression reads that are neither consumed nor produced. `stoich` keys are pool names spelled in this scope like the reactant and product lists (`Env.pool`), so inside a `!template` a key `A` names the port `one.A` (T091 A6). ^reaction

**crux**`(precursor="precursor", kA=None, kB=None, container=None, name=None)`
    `ConflictCruxBlock.make`: one precursor pool, two routes, two sinks. ^crux

**signal**`(in_pool="in", out_pool="out", modifier="modifier", kind="activator", a=None, Ki=None, rate=None, container=None, name=None)`
    `SignalingBlock.make`; `kind` picks a linear activator or inhibitor. ^signal

**inhibit**`(in_pool="in", out_pool="out", modifier="modifier", Ki=None, rate=None, container=None, name=None)`
    `InhibitionBlock.make`. ^inhibit

**enzyme**`(substrate="substrate", product="product", enzyme="enzyme", Vmax=None, K=None, rate=None, container=None, name=None)`
    `EnzymeBlock.make`: a Michaelis catalyst modifier. ^enzyme

**cooperative**`(in_pool="in", out_pool="out", modifier="modifier", Vmax=None, K=None, n=None, rate=None, container=None, name=None)`
    `CooperativeBindingBlock.make`: a Hill modifier. ^cooperative

**insult**`(pool="stressed", rate=None, poisson=None, container=None, name=None)`
    `PressureBlock.make`; `poisson: {lam, horizon}` attaches a `PoissonSchedule` (metadata the insult runner reads), refusing a mapping without both keys. ^insult

**transport**`(pool="pool", container=None, dest_container="cell2", rate=None, rate_law="gradient", src_volume=1.0, dest_volume=1.0, name=None)`
    `TransportBlock.make`: one `Transport` flux and both compartments. `rate_law` is passed through unchecked here; the `!Transport` constructor checks it. ^transport

**lattice**`(k=3, molecule="x", diffusion=None, volume=1.0, initial=None, name=None)`
    `SpatialLatticeBlock.make`: `k` compartments with neighbour fluxes; `initial` maps a cell index to a concentration. ^lattice

**population**`(name=None, growth_rate=None, death_rate=None, **kwargs)`
    `PopulationBlock.make` with the two rates as Dist slots and every other keyword passed through. The block owns its resource as a molecule name (`resource_name`), not a port, so it exposes no pool for `block` to wire. ^population

**block**`(children: Mapping[str, SkeletonBlock], role="supply", name=None) -> SkeletonBlock`
    Renames each child to its key, then gives the parent one port per distinct pool name across the children (`OUT` when any child produces it, the container a child declares for it) and a `PoolBinding("self.<pool>", "<child>.<pool>")` per child port. Refuses a non-mapping, a child that is not a block, and one pool named in two different containers. § [Pools as names](#pools-as-names). ^block

**skeleton**`(root: SkeletonBlock, control_surface=(), crux="") -> Skeleton`
    Wraps a root block; refuses a non-block. ^skeleton



## RateLawBlock Interface
A frozen `ReactionBlock` subclass: one reaction whose rate is a compiled `RateLaw` rather than a constant.

| RateLawBlock | |
| --- | --- |
| [law](#^law) | The compiled law |
| [extra_pools](#^extra-pools) | Ports read but neither consumed nor produced |
| [realize](#^realize) | The fragment: one reaction with modifiers or an expression |

**law**`: RateLaw`
    `k` plus modulations, or an expression ([ABIO RateLaw](ABIO%20RateLaw.md)). ^law

**extra_pools**`: tuple[str, ...]`
    The modifier pools and the pools the expression reads beyond the reactants and products; each is an `IN` port so `block` wires it like any other. ^extra-pools

**realize**`(seed, ns, bound) -> Fragment`
    Reactants and products from the non-extra ports through `blocks._sides`, the reaction primitive's own rule: `stoich` coefficients (default 1), two ports on one pool summing theirs, a `stoich` key naming no port refused (T091 A5); each modulation sampled under `seed.child("mod/<pool>")` into a non-consumed modifier; `k` drawn under `seed.child("rate")`. With an expression, the tree is drawn under `seed.child("law")`, mapped to molecule names, and every extra pool it reads rides as an inert modifier so the chemistry records the dependency. The reaction id is `"<ns>/rxn"`, placed in the first port's container or `cell`. ^realize



## World heads
Layer 2.

| World heads | |
| --- | --- |
| [world](#^world) | Materialize a skeleton under the node's seed |
| [sim](#^sim) | A `SimConfig` |
| [verify](#^verify) | Redraw a world until a predicate holds |
| [pressure_world](#^pressure-world) | The EXP-2 pressure world |
| [conflict_world](#^conflict-world) | A conflict-ladder world |
| [delta_pair](#^delta-pair) | The matched pair |
| [diagnosis_world](#^diagnosis-world) | A diagnosis world |
| [prediction_world](#^prediction-world) | A prediction world |
| [intervention_world](#^intervention-world) | An intervention world with its target |

**world**`(skeleton: Skeleton, initial=None, container=None, seed=None) -> WorldImpl`
    `skeleton.materialize(seed or ctx.seed)`. With `initial`, each name is spelled through `Env.pool`, looked up among the root's resolved ports (falling back to the name itself), refused if it is not a molecule of the world, and set as a concentration in `container` (default the first compartment, refused if absent); the `WorldImpl` is rebuilt with flows and population laws kept. ^world

**sim**`(dt=0.1, steps=200, sample_every=10) -> SimConfig`
    Integration parameters for `verify`. ^sim

**verify** (expander)`(world=, perturb=, valid=, max_redraws=8, sim=)`
    Keywords only. Evaluates `perturb` and `valid` to callables (a head name resolves to its function), then for each attempt evaluates the `world` form under `env.with_seed(ctx.seed.child("attempt<n>"))`, a child seed at the same path, simulates it and `perturb(world)` under seeds `base` and `pert`, and returns the first world for which `valid(baseline, perturbed)` holds; refuses after `max_redraws + 1` attempts. § [verify's redraws](#verifys-redraws). ^verify

**pressure_world**`(**kwargs) -> {world, skeleton, objective}`
    `draft_pressure_world(ctx.seed, ...)`, with the rate keywords in `_DIST_KEYS` turned into Dists. ^pressure-world

**conflict_world**`(**kwargs) -> {world, skeleton, objective}`
    `draft_conflict_world`. ^conflict-world

**delta_pair**`(**kwargs) -> [match, mismatch]`
    `draft_delta_pair`, each side a `{world, skeleton, objective}`. ^delta-pair

**diagnosis_world**`(**kwargs) -> {world, skeleton}`
    `draft_diagnosis_world`. ^diagnosis-world

**prediction_world**`(**kwargs) -> {world, skeleton, reaction_id}`
    `draft_prediction_world`. ^prediction-world

**intervention_world**`(**kwargs) -> {world, skeleton, target: {molecule, value}}`
    `draft_intervention_world`. ^intervention-world



## Constructor heads
Kind `constructor`, called by tag (`!Reaction {...}`) or by the untagged `_type:` key the interpreter rewrites. The node's key is the name when none is given.

| Constructor heads | |
| --- | --- |
| [Entity heads](#^entity-heads) | `cls.hydrate` over the mapping |
| [Reaction](#^reaction-ctor) | A reaction; unknown molecule names minted |
| [Chemistry](#^chemistry) | Molecules and reactions in one chemistry |
| [Compartment](#^compartment) | A world compartment record |
| [Transport](#^transport-ctor) | A cross-compartment flux record |
| [GrowthLaw](#^growthlaw) | A per-capita growth record |
| [DeathLaw](#^deathlaw) | A per-capita death record |
| [CountFlow](#^countflow) | A size-class transition record |
| [World](#^world-ctor) | A `WorldImpl` from a chemistry and records |

**Entity heads**`(name=None, **fields)`
    One head per entry of `infra.entity.get_registered_heads()` except `Entity`, `Compartment`, `Reaction` and `Chemistry` (which have their own): `cls.hydrate({**fields, "name": name})`, a `KeyError`/`TypeError`/`ValueError` re-raised as `ExprError` naming the head. `!Molecule` is one. ^entity-heads

**Reaction**`(reactants=(), products=(), rate=None, name=None, molecules=None, **fields) -> ReactionImpl`
    Each side is a list of names (a repeat sums: `[A, A]` is `{A: 2}`), `{name: coef}` mappings or Molecule objects. Names resolve against `molecules` and any Molecules given inline; any other name is minted as a plain Molecule. A numeric rate is coerced to float. ^reaction-ctor

**Chemistry**`(molecules=(), reactions=(), name=None, **fields) -> ChemistryImpl`
    `molecules` as names, Molecules or a mapping of fields; `reactions` as a mapping of name to fields or Reaction, or a list of Reactions (a listed mapping refuses: it carries no name). Every molecule a reaction side or modifier names is added. ^chemistry

**Compartment**`(id=None, kind="cell", volume=1.0, parent=None, concentrations=None, multiplicity=1.0) -> Compartment`
    The `bio.world.Compartment` record the simulator runs, not the M1 entity. ^compartment

**Transport**`(origin, dest, molecule, rate=1.0, rate_law="gradient", stoich=1.0, name="") -> Transport`
    Refuses a `rate_law` other than `gradient` or `first_order`; default name `origin->dest:molecule`. ^transport-ctor

**GrowthLaw**`(compartment, resource_compartment, resource, rate=1.0, stoich=1.0, name="") -> GrowthLaw`
    Default name `compartment:growth`. ^growthlaw

**DeathLaw**`(compartment, rate=1.0, release_compartment=None, release_resource=None, release_stoich=0.0, name="") -> DeathLaw`
    Default name `compartment:death`. ^deathlaw

**CountFlow**`(origin, dest, rate=1.0, name="") -> CountFlowSpec`
    Default name `origin->dest`. ^countflow

**World**`(chemistry: ChemistryImpl, compartments=(), flows=(), population_laws=()) -> WorldImpl`
    Refuses a non-chemistry, a non-`Compartment` record, and a concentration naming a molecule the chemistry lacks; with no compartments, one `cell` of volume 1. Flows and population laws are not type-checked. ^world-ctor




# ExprHeads Semantics

## Pools as names
A block class takes port names; a block head takes pool names and uses them as the port names, so two heads that name the same pool produce ports of the same name. `block` then binds each child port to a parent port of that name, and `Skeleton.materialize` resolves every binding group to one molecule: `!source {pool: precursor}` and `!crux {precursor: precursor}` share the precursor without a binding table. Inside a template instance a name is namespaced (`inst.precursor`) unless it arrived as a pool argument ([ABIO Env](../ABIO%20expr%20Modules/ABIO%20Env.md) § Pool names). A pool lives in one compartment: two children naming one pool in two different containers are refused, naming both children (a cross-compartment pool needs a `transport`); since `64988be`. The rule reaches ported blocks only: `population` is a portless leaf that mints its own resource, so a `source` cannot be wired to it by name.



## Dist slots
A numeric slot accepts `None` (the class default applies), a number (`Constant`), or a `Dist` — a quoted form is one, so `rate: !q lognormal(0, 0.3)` is drawn per world at materialize time under the block's seed. A bool refuses. The generator world heads apply the same rule only to the keywords in `_DIST_KEYS` (`k_clean`, `k_fast`, `k_i2t`, `k_byproduct`, `k_hop`, `kA`, `kB`, `k_drive`, `k_sink`, `k_sink_b`, `k_t_sink`); every other keyword reaches the drafter as given.



## verify's redraws
Each attempt evaluates the world form on a child seed at the same path (`ctx.seed.child("attempt<n>")`), so attempt `n` draws from its own seed and a world that fails the predicate is never reused, while the path, and so any template instance name, is unchanged (‡): a template bound to `one:` and called inside `verify` namespaces its pools `one.P` on every attempt, and two `verify` nodes under one parent no longer collide (since `64988be`; the path step `attempt<n>` named them `attempt0.P` before). The seeds are the same as before. The `pathway_puzzles` example draws its host this way (`max_redraws: 16`, `valid: non_obvious`, `343b22a`): over seeds 0–59 no seed needs more than two redraws.



## Guarded parameters on the world heads
`pressure_world`, `conflict_world`, `diagnosis_world` and `intervention_world` declare no guard metadata (since `64988be`; the `guarded_params` they carried were read by nothing, since the no-peeking guard collects guarded dials only from heads of kind `drafter`, [ABIO Drafters](ABIO%20Drafters.md)). An agent reaches a world only through a drafter, and the guard that applies is carried by the drafter heads an experiment names (`pressure`, `conflict`, `diagnose`, …).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `afd519c` (read with `git show`; `expr_heads.py` unchanged since `c67f052`). Run against an export of that tree: a template bound to `one:` and called as `verify`'s world materialized `root/attempt0.P` where the same template bound to `plain:` gave `root/plain.P`; two instances of a template whose body is a `population` block gave identical molecule sets, the block exposing no ports. Not run: the container merge in `block` (read from 293–301). Findings filed on T088.
- 2026-10-28 — refreshed against 0eb23e5 (`64988be`, `719261e`): `verify` redraws on a child seed at the same path (instance names kept); `block` refuses one pool in two containers; the world heads' unread `guarded_params` removed; `k_sink_b` is a Dist key; the figure's dagger follows.
- 2026-10-29 — refreshed for `cbcedfd` (T091 A5, A6): `reaction`'s `stoich` keys are namespaced like its ports, and `RateLawBlock.realize` builds its sides through `blocks._sides` (duplicate ports sum, a stray key refuses).
- 2026-10-30 — refreshed for `343b22a` (T091 AM5): `pathway_puzzles` draws its host through `verify` (`max_redraws: 16`); `!pattern` and `!identify` are `expr_experiment`'s heads, refreshed for `2a29e7b` in [ABIO ExprExperiment](ABIO%20ExprExperiment.md).
