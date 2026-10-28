---
description: "`blocks`: the concrete `SkeletonBlock` library every generator composes — the mass-action primitive and its source/sink configs, the conflict crux and its frontier sweep, the pressure drain with its Poisson schedule, the four modifier blocks, transport and the lattice, the population block. Source: `src/alienbio/suite/blocks.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Blocks](ha://p/ABIO%20Blocks) 
# ABIO Blocks
The block catalog of the world generators: twelve frozen `SkeletonBlock` subclasses, each emitting one reaction, one flux set or one law set when it realizes, plus the Poisson schedule and the conflict-frontier sweep.

![ABIO Blocks](ABIO%20Blocks.svg) 
*One realize path* is the topic behind the `ReactionBlock` family (source, sink and pressure inherit its body); *Leaf blocks* governs the three blocks that mint their own species instead of taking bound pools.

`suite/blocks.py` holds no machinery: `Port`, `PoolBinding`, `Fragment`, the tree walk and `Skeleton` itself are in [ABIO Skeleton](ABIO%20Skeleton.md), which also carries the library table of who uses which block. What the blocks emit is read by [ABIO ReactionImpl](../ABIO%20bio/ABIO%20ReactionImpl.md) (reactions and `Modulation`), [ABIO TransportFlux](../ABIO%20bio/ABIO%20TransportFlux.md) (`Transport` specs) and [ABIO PopulationLaw](../ABIO%20bio/ABIO%20PopulationLaw.md) (`GrowthLaw`, `DeathLaw`), all placed by [ABIO WorldImpl](../ABIO%20bio/ABIO%20WorldImpl.md). The generators that compose these blocks are [ABIO PressureGen](ABIO%20PressureGen.md), [ABIO W2Gen](ABIO%20W2Gen.md) and [ABIO Phase1Gen](ABIO%20Phase1Gen.md); two blocks live outside this module, `ModulatedSourceBlock` in `w2_gen.py` and `RateLawBlock` in `expr_heads.py`. Every block except the private generator cruxes is also an Expr head (§ [Expr heads](#expr-heads)). Nothing here is re-exported from `alienbio.suite`.



## ReactionBlock Interface
The one reaction primitive: every `IN` port becomes a reactant, every `OUT` port a product, and `realize` emits exactly one constant-rate mass-action `ReactionImpl` with id `f"{ns}/rxn"`. It has no `make`; generators construct it directly with explicit ports. `SourceBlock`, `SinkBlock` and `PressureBlock` are subclasses that only fix the ports.

| ReactionBlock | |
| --- | --- |
| [rate](#^rate) | The rate-constant hole |
| [stoich](#^stoich) | Per-port coefficient overrides |
| [realize](#^realize) | Emit the one reaction |

**rate**`: Dist[float] = Constant(1.0)`
    Sampled once per realize from `seed.child("rate")`, where `seed` is the block's own tree-position seed, so the drawn constant depends on the block's path only. ^rate

**stoich**`: Mapping[str, float] = {}`
    Port name to coefficient; a port not named gets `1.0`. A key naming no port is refused with `SkeletonError` at realize. ^stoich

**realize**`(seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]) -> Fragment`
    Builds `mk.R(f"{ns}/rxn", reactants, products, rate=…)` over the bound molecules and returns a fragment with those molecules, the one reaction and one `Provenance` attributed to the first declared port container (`cell` when none is). Two ports bound to one pool sum their coefficients (§ [One realize path](#one-realize-path)). ^realize



## SourceBlock Interface
A `ReactionBlock` with one `OUT` port: `∅ -> pool`. Boundary reactions are exempt from the conservation gate (`bio.conservation.is_boundary_reaction`). Role `SUPPLY`.

| SourceBlock | |
| --- | --- |
| [make](#^make) | Build a source on one port |

**make**`(name, *, port="out", container=None, rate=None, params=None) -> SourceBlock` (classmethod)
    One `OUT` port named `port`; `rate` defaults to `Constant(1.0)`. ^make



## SinkBlock Interface
A `ReactionBlock` with one `IN` port: `pool -> ∅`, the bounded fate that keeps a pool homeostatic. Role `SINK`.

| SinkBlock | |
| --- | --- |
| [make](#^sinkblock-make) | Build a sink on one port |

**make**`(name, *, port="in", container=None, rate=None, params=None) -> SinkBlock` (classmethod)
    One `IN` port named `port`; `rate` defaults to `Constant(1.0)`. ^sinkblock-make



## ConflictCruxBlock Interface
A pattern block with no `realize` of its own: a shared `precursor` pool feeding two rival routes, each drained by its own internal sink, so the parent wires only the precursor. The two routes have independent rate holes `kA` and `kB` (not a split ratio); the budget is shared only through the precursor pool. Role `CRUX`.

| ConflictCruxBlock | |
| --- | --- |
| [make](#^conflictcruxblock-make) | Build the four-child crux |
| [ground_truth](#^ground-truth) | The achieved `(prodA, prodB)` point |

**make**`(name, *, precursor_port="precursor", container=None, kA=None, kB=None, params=None) -> ConflictCruxBlock` (classmethod)
    Children `route_a` and `route_b` (`ReactionBlock`, `in -> out` at `kA` / `kB`, default `Constant(1.0)`), `sink_a` and `sink_b` (`SinkBlock`, rate 1). Bindings: `self.<precursor_port>` to both routes' `in`, each route's `out` to its sink's `in`; the product pools are therefore minted as `f"{ns}/sink_a_in"` and `f"{ns}/sink_b_in"`. ^conflictcruxblock-make

**ground_truth**`(timeline: Timeline) -> tuple[float, float]`
    Finds `route_a` and `route_b` among the realized children and returns `final_amount` of each route's resolved `out` pool. Raises `SkeletonError` on an unrealized block. The point, not a scalar score: a scorer collapses it. ^ground-truth



## PressureBlock Interface
A `SinkBlock` on a `stressed` port: a constant drain (the default arm) that can also carry a Poisson insult schedule (the opt-in arm). The schedule is metadata only; it never changes the reaction's rate. Role `PRESSURE`.

| PressureBlock | |
| --- | --- |
| [poisson](#^poisson) | The opt-in schedule, or `None` |
| [insult_times](#^insult-times) | The drawn times, set at realize |
| [make](#^pressureblock-make) | Build a drain on one port |
| [realize](#^pressureblock-realize) | The sink's fragment, then draw the schedule |

**poisson**`: Optional[PoissonSchedule] = None`
    When set, `realize` draws insult times from it. ^poisson

**insult_times**`: tuple[float, ...] = ()`
    Written by `realize` with `object.__setattr__` onto the block being realized, which on a first materialize is the authored block itself (§ [The Poisson schedule](#the-poisson-schedule)). The only reader is the stochastic example's `insult_times` helper (`catalog/examples/stochastic/helpers.py`), which walks the realized root. ^insult-times

**make**`(name, *, port="stressed", container=None, rate=None, poisson=None, params=None) -> PressureBlock` (classmethod)
    One `IN` port; `rate` is the drain magnitude, default `Constant(1.0)`. ^pressureblock-make

**realize**`(seed, ns, bound) -> Fragment`
    `SinkBlock`'s fragment unchanged; when `poisson` is set, also draws the schedule from `seed.child(ns)` and caches it. ^pressureblock-realize



## PoissonSchedule Interface
A frozen config: a Poisson process of rate `lam` over `[0, horizon]`. Only `_draw_poisson_times` samples it.

| PoissonSchedule | |
| --- | --- |
| [lam](#^lam) | Events per unit time |
| [horizon](#^horizon) | End of the window |

**lam**`: float`
    Inter-arrival times are `exponential(1 / lam)`. Construction refuses a `lam` that is not positive and finite, and a negative or non-finite `horizon`, with `SkeletonError`. ^lam

**horizon**`: float`
    Arrivals are summed until one passes `horizon`; that one is dropped. ^horizon



## SignalingBlock Interface
A control wire: one `in -> out` reaction whose rate is scaled by a linear modifier species, an activator (`1 + a·[M]` on the numerator) or an inhibitor (`1 + [M]/Ki` on the denominator). The modifier is an `IN` port that is never consumed. Role `SIGNALING`; used by `phase1_gen` as the down variants' `scrub`.

| SignalingBlock | |
| --- | --- |
| [rate](#^signalingblock-rate) | The base rate hole |
| [kind](#^kind) | `"activator"` or `"inhibitor"` |
| [a](#^a) | Activator gain hole |
| [Ki](#^ki) | Inhibitor constant hole |
| [modifier_port](#^modifier-port) | Which port is the modifier |
| [make](#^signalingblock-make) | Build the three-port wire |
| [realize](#^signalingblock-realize) | Emit the modulated reaction |

**rate**`: Dist[float] = Constant(1.0)`
    Sampled from `seed.child("rate")`. ^signalingblock-rate

**kind**`: str = "activator"`
    Checked by `make`, and by `realize` on a directly constructed block: any value other than `"activator"` or `"inhibitor"` raises `SkeletonError`. ^kind

**a**`: Dist[float] = Constant(1.0)`
    Sampled from `seed.child("a")` when `kind` is `"activator"`. ^a

**Ki**`: Dist[float] = Constant(1.0)`
    Sampled from `seed.child("Ki")` otherwise. ^ki

**modifier_port**`: str = "modifier"`
    The port `_modulator_fragment` attaches as `ReactionImpl.modifiers` instead of as a reactant. ^modifier-port

**make**`(name, *, in_port="in", out_port="out", modifier_port="modifier", container=None, rate=None, kind="activator", a=None, Ki=None, params=None) -> SignalingBlock` (classmethod)
    Ports `in` (`IN`), `out` (`OUT`), `modifier` (`IN`). Raises `SkeletonError` on any other `kind`. ^signalingblock-make

**realize**`(seed, ns, bound) -> Fragment`
    Samples the rate and the one parameter its kind needs, then `_modulator_fragment` (§ [Modifier blocks](#modifier-blocks)). ^signalingblock-realize



## InhibitionBlock Interface
`SignalingBlock(kind="inhibitor")` as its own single-purpose block: `in -> out` divided by `1 + [M]/Ki`. Fields `rate`, `Ki` and `modifier_port` as on `SignalingBlock`. Role `SIGNALING`; Expr `inhibit`.

| InhibitionBlock | |
| --- | --- |
| [make](#^inhibitionblock-make) | Build the three-port inhibitor |

**make**`(name, *, in_port="in", out_port="out", modifier_port="modifier", container=None, rate=None, Ki=None, params=None) -> InhibitionBlock` (classmethod)
    Same three ports; `realize` samples `rate` and `Ki` and emits one reaction with an `inhibitor` modulation. ^inhibitionblock-make



## EnzymeBlock Interface
One `substrate -> product` reaction scaled by a saturating catalyst, `Vmax·[E] / (K + [E])` in the enzyme's own concentration, with no `ES` intermediate pool. Fields `rate`, `Vmax`, `K` (all `Dist`, default `Constant(1.0)`) and `modifier_port = "enzyme"`. Role `SIGNALING`; Expr `enzyme`.

| EnzymeBlock | |
| --- | --- |
| [make](#^enzymeblock-make) | Build substrate, product and enzyme ports |

**make**`(name, *, substrate_port="substrate", product_port="product", modifier_port="enzyme", container=None, rate=None, Vmax=None, K=None, params=None) -> EnzymeBlock` (classmethod)
    `realize` samples `rate`, `Vmax`, `K` from same-named seed children and emits one reaction with a `michaelis` modulation. ^enzymeblock-make



## CooperativeBindingBlock Interface
One `in -> out` reaction scaled by a Hill term, `Vmax·[M]^n / (K^n + [M]^n)`; `n = 1` is the enzyme's hyperbola, larger `n` a step around `K`. Fields `rate`, `Vmax`, `K` (default `Constant(1.0)`), `n` (default `Constant(2.0)`), `modifier_port = "modifier"`. Role `SIGNALING`; Expr `cooperative`.

| CooperativeBindingBlock | |
| --- | --- |
| [make](#^cooperativebindingblock-make) | Build the three-port Hill block |

**make**`(name, *, in_port="in", out_port="out", modifier_port="modifier", container=None, rate=None, Vmax=None, K=None, n=None, params=None) -> CooperativeBindingBlock` (classmethod)
    `realize` samples `rate`, `Vmax`, `K`, `n` and emits one reaction with a `hill` modulation. ^cooperativebindingblock-make



## TransportBlock Interface
One `Transport` flux moving its bound species from its port's container (the origin) to `dest_container`, which is a bare container id, not a port: the same species in another compartment column. The one port is `IN`, so used alone something else must supply the pool's `OUT` side for `validate`. Role `TRANSPORT`; Expr `transport`.

| TransportBlock | |
| --- | --- |
| [rate](#^transportblock-rate) | The rate-constant hole |
| [rate_law](#^rate-law) | `"gradient"` or `"first_order"` |
| [dest_container](#^dest-container) | Where the species is moved to |
| [src_volume](#^src-volume) | Origin compartment volume |
| [dest_volume](#^dest-volume) | Destination compartment volume |
| [make](#^transportblock-make) | Build the one-port transporter |
| [realize](#^transportblock-realize) | Emit the flux and both compartments |

**rate**`: Dist[float] = Constant(1.0)`
    Sampled from `seed.child("rate")`. ^transportblock-rate

**rate_law**`: str = "gradient"`
    `"gradient"` relaxes toward equal concentration (Fickian, floored at zero when the gradient reverses); `"first_order"` is `k·[X]_origin`, a pump. Passed through unchecked to `Transport`. ^rate-law

**dest_container**`: NodeId = "cell2"`
    The destination compartment id. ^dest-container

**src_volume**`: float = 1.0`
    Volume written on the origin's `Compartment` record. ^src-volume

**dest_volume**`: float = 1.0`
    Volume written on the destination's record. ^dest-volume

**make**`(name, *, port="pool", container=None, dest_container="cell2", rate=None, rate_law="gradient", src_volume=1.0, dest_volume=1.0, params=None) -> TransportBlock` (classmethod)
    One `IN` port; `container=None` means origin `cell`. ^transportblock-make

**realize**`(seed, ns, bound) -> Fragment`
    Emits `Transport(origin, dest, {x: 1}, driver_molecule=x, rate_constant, rate_law, name=f"{ns}/transport")` and declares both compartments, origin as a root (`parent None`) and destination as its child (§ [Compartments a block declares](#compartments-a-block-declares)). ^transportblock-realize



## SpatialLatticeBlock Interface
A leaf with no ports: a 1-D chain of `k` compartments `f"{ns}/cell0"` … `cell{k-1}`, each nested in the previous, one minted species `f"{ns}/{molecule}"`, and per neighbour edge a reversed pair of gradient fluxes sharing one diffusion constant, so any stamped profile relaxes toward flat. Role `TRANSPORT`; Expr `lattice`.

| SpatialLatticeBlock | |
| --- | --- |
| [k](#^k) | Number of cells |
| [molecule](#^molecule) | Local name of the diffusing species |
| [diffusion](#^diffusion) | The shared rate-constant hole |
| [volume](#^volume) | Volume of every cell |
| [initial](#^initial) | Cell index to starting concentration |
| [make](#^spatiallatticeblock-make) | Build a chain, refusing `k < 2` |
| [realize](#^spatiallatticeblock-realize) | Emit cells, fluxes and `initial` |

**k**`: int = 3`
    Construction refuses a non-int `k` or `k < 2` with `SkeletonError`, so `make` and a direct build agree. ^k

**molecule**`: str = "x"`
    Minted as `f"{ns}/{molecule}"`; it is not a port, so no other block can bind it. ^molecule

**diffusion**`: Dist[float] = Constant(1.0)`
    Sampled once from `seed.child("diffusion")`, the same constant on every edge in both directions. ^diffusion

**volume**`: float = 1.0`
    Written on every cell. ^volume

**initial**`: Mapping[int, float] = {}`
    Index `i` stamps `cell{i}`; an absent index starts at 0. Construction refuses an index outside `0..k-1` (or not an int) with `SkeletonError`. ^initial

**make**`(name, *, k=3, molecule="x", diffusion=None, volume=1.0, initial=None, params=None) -> SpatialLatticeBlock` (classmethod)
    Copies `initial` into a fresh dict. ^spatiallatticeblock-make

**realize**`(seed, ns, bound) -> Fragment`
    Ignores `bound`. Emits the `k` compartments, `2(k−1)` fluxes named `f"{ns}/edge{i}_fwd"` / `_rev`, one `Provenance` per flux and the `initial` map keyed `(cell_id, molecule_id)`; the only library block that sets `Fragment.initial`. ^spatiallatticeblock-realize



## PopulationBlock Interface
A leaf with no ports: a population compartment `f"{ns}/pop"` whose `multiplicity` is the count, a child pool compartment `f"{ns}/pool"` holding a minted resource, a resource-coupled `GrowthLaw` and an optional `DeathLaw`. The resource is an ordinary molecule, so it is a valid `Intervene` target with no new lever kind. Role `POPULATION`; Expr `population`.

| PopulationBlock | |
| --- | --- |
| [initial_multiplicity](#^initial-multiplicity) | Starting count |
| [resource_name](#^resource-name) | Local name of the resource |
| [resource_initial](#^resource-initial) | Starting resource concentration |
| [growth_rate](#^growth-rate) | Growth rate-constant hole |
| [growth_stoich](#^growth-stoich) | Resource amount drawn per new instance |
| [death_rate](#^death-rate) | Death rate-constant hole |
| [volume](#^population-volume) | Volume of one instance |
| [resource_volume](#^resource-volume) | Volume of the pool |
| [biomass_name](#^biomass-name) | Local name of the biomass species |
| [biomass_conc](#^biomass-conc) | Per-instance biomass concentration |
| [make](#^populationblock-make) | Build the block |
| [realize](#^populationblock-realize) | Emit compartments and laws |
| [ground_truth](#^populationblock-ground-truth) | Final count |

**initial_multiplicity**`: float = 1.0`
    Written as the `pop` compartment's `multiplicity`. ^initial-multiplicity

**resource_name**`: str = "resource"`
    Minted as `f"{ns}/{resource_name}"`. ^resource-name

**resource_initial**`: float = 100.0`
    The pool compartment's starting concentration of the resource. ^resource-initial

**growth_rate**`: Dist[float] = Constant(0.01)`
    Sampled from `seed.child("growth_rate")`; growth extent is `growth_rate · N · [resource] · dt`. ^growth-rate

**growth_stoich**`: float = 1.0`
    Resource amount drawn from the pool per unit of `ΔN`. Mass balances when it equals `volume · biomass_conc` (the defaults do); `0.0` is the deliberately leaky config the conservation test uses. ^growth-stoich

**death_rate**`: Dist[float] = Constant(0.0)`
    Sampled from `seed.child("death_rate")`; a draw of exactly `0.0` adds no `DeathLaw`. Sign is not checked. ^death-rate

**volume**`: float = 1.0`
    The `pop` compartment's volume. ^population-volume

**resource_volume**`: float = 1.0`
    The `pool` compartment's volume. ^resource-volume

**biomass_name**`: str = "biomass"`
    Minted as `f"{ns}/{biomass_name}"`; every instance, old or new, holds `biomass_conc` of it (born full). ^biomass-name

**biomass_conc**`: float = 1.0`
    Written on the `pop` compartment's concentrations. ^biomass-conc

**make**`(name, *, initial_multiplicity=1.0, resource_name="resource", resource_initial=100.0, growth_rate=None, growth_stoich=1.0, death_rate=None, volume=1.0, resource_volume=1.0, biomass_name="biomass", biomass_conc=1.0, params=None) -> PopulationBlock` (classmethod)
    Every field passes through; no value is validated. ^populationblock-make

**realize**`(seed, ns, bound) -> Fragment`
    Ignores `bound`. Emits both molecules, both compartments (`pop` a root, `pool` its child), `GrowthLaw(name=f"{ns}/growth")` and, when the death draw is non-zero, `DeathLaw(name=f"{ns}/death")`, each with a `Provenance` on `pop`. ^populationblock-realize

**ground_truth**`(timeline: Timeline) -> float`
    `final_multiplicity` of the container named by the first `provenance` entry, which is the `pop` compartment; raises `SkeletonError` when `provenance` is empty, that is, on an unrealized block. ^populationblock-ground-truth



## blocks Interface
The one module-level public function. The private helpers `_container_of`, `_draw_poisson_times` and `_modulator_fragment` are described under the semantics below.

| blocks | |
| --- | --- |
| [sweep_conflict_frontier](#^sweep-conflict-frontier) | Achieved points over a list of `(kA, kB)` |

**sweep_conflict_frontier**`(build: Callable[[Dist[float], Dist[float]], Skeleton], seed: Seed, points: Sequence[tuple[float, float]], sim_cfg: SimConfig = SimConfig()) -> tuple[tuple[float, float], ...]`
    For each `(kA, kB)` calls `build(Constant(kA), Constant(kB)).oracle(seed, sim_cfg)` and returns the achieved points in order, every point under the same seed. `conflict_gen`'s forced-gate is its only production caller ([ABIO ConflictGen](ABIO%20ConflictGen.md)). ^sweep-conflict-frontier




# Blocks Semantics

## One realize path
Source, sink and pressure blocks add no realize logic: a `ReactionBlock` with only `OUT` ports emits `∅ -> products`, one with only `IN` ports emits `reactants -> ∅`, and the subclasses differ only in the ports their `make` builds and the `Role` they carry. All four modifier blocks share the other body, `_modulator_fragment`, which is the same loop with the modifier port skipped. Both paths build their sides through one helper, `_sides`, keyed by `MoleculeImpl`: two ports of one block bound to the same pool sum their coefficients (`A + A -> B` is `2 A`), and a `stoich` key naming no port raises `SkeletonError`.

The reaction is attributed to `_container_of(ports)`, the first port with a declared container, else `cell`. That attribution reaches only `Provenance`; the reaction runs in every compartment the world has ([ABIO Skeleton](ABIO%20Skeleton.md) § Materialize).

Every sampled parameter comes from a named child of the block's own seed (`"rate"`, `"a"`, `"Ki"`, `"Vmax"`, `"K"`, `"n"`, `"diffusion"`, `"growth_rate"`, `"death_rate"`), so two blocks at the same tree path draw the same values whatever else the tree holds.



## Modifier blocks
`_modulator_fragment` attaches the modifier through `ReactionImpl.modifiers` with a `Modulation(kind=…)`, never as a reactant or product, so the modifier is not consumed and never enters the conservation gate. The rate factor is computed by the simulator off the frozen start-of-step state, in the reaction's compartment:

| Block | Modulation kind | Factor on the mass-action rate |
| --- | --- | --- |
| `SignalingBlock` activator | `activator` | `1 + a·[M]` |
| `SignalingBlock` inhibitor, `InhibitionBlock` | `inhibitor` | `1 / (1 + [M]/Ki)` |
| `EnzymeBlock` | `michaelis` | `Vmax·[E] / (K + [E])` |
| `CooperativeBindingBlock` | `hill` | `Vmax·[M]^n / (K^n + [M]^n)` |

The saturating kinds multiply to zero when the modifier is absent, so an enzyme block with no enzyme runs nothing; the linear activator leaves the base rate standing. The forms are [ABIO WorldSimulatorImpl](../ABIO%20bio/ABIO%20WorldSimulatorImpl.md)'s `_modulation_factor`; the JAX core applies the same ones.



## Leaf blocks
`SpatialLatticeBlock` and `PopulationBlock` take no ports and ignore `bound`: one species living in `k` compartments, or a count with its resource, has no producer and consumer to bind. They mint their own ids under `ns`, so their species cannot be wired to the rest of a tree by `pool_bindings`; a composite reaches them only through their compartments' shared ids. `TransportBlock` is the half-way case: it takes its species as a bound port but its destination as a bare container id.



## Compartments a block declares
Only the transport, lattice and population blocks put `Compartment` records in their fragment; every other block leaves the world's compartment tree to `materialize`'s default `cell`. Each declares every compartment it touches, self-contained, and `Fragment.merge` accepts a compartment id from two blocks when the two records are equal, or when they differ only in that one leaves `parent` unset (the placed declaration wins).

That rule makes parallel transport blocks compose (two blocks on the default `cell -> cell2` declare identical records) and makes a chain build: `TransportBlock` writes its origin as a root (`parent None`) and its destination as the origin's child, so `A -> B` declares `B` with parent `A` and `B -> C` declares `B` with parent `None`; the parentless record yields to the placed one, and `A -> B -> C` nests `B` under `A` and `C` under `B`. The same equality check refuses two transport blocks that state different volumes for one shared container.



## The Poisson schedule
`_draw_poisson_times` sums `exponential(1/lam)` inter-arrivals from `seed.child(ns).rng()` until one passes `horizon`, so the times are reproducible per seed and per tree path. `PressureBlock.realize` caches them with `object.__setattr__` on `self`, and `_realize_tree` calls `realize` on the block it was handed before copying it with `dataclasses.replace`: on a skeleton's first `materialize` that is the authored block, so the authored tree carries the first seed's times, and a block instance shared between two skeletons carries whichever realized last. A second `materialize` of the same skeleton re-realizes its already-realized copy and leaves the authored block alone. The Expr `insult` head builds the schedule from `{lam, horizon}`; the stochastic example reads it back and applies the insults in its own piecewise runner, since the reaction's rate never sees it.



## Expr heads
`suite/expr_heads.py` wraps each public block as a head: `source`, `sink`, `reaction` (a `ReactionBlock`, or `RateLawBlock` when given a rate law), `crux`, `signal`, `inhibit`, `enzyme`, `cooperative`, `insult` (`PressureBlock`), `transport`, `lattice`, `population`. Each head names pools through `Env.pool` and wraps rate arguments as `Dist`s; the block itself never sees Expr ([ABIO Skeleton](ABIO%20Skeleton.md) § Expr heads and template namespacing).




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `7c1db83`. The transport-chain refusal, the lattice index behaviour, the two-ports-one-pool collapse, `lam = 0` and the authored-block write were each reproduced by a local realize or materialize, no spend. One interface section per class, with the four modifier blocks and the three source/sink/pressure configs documented only for what they add over their shared body. Left out: `ModulatedSourceBlock` and `RateLawBlock` (their own modules), the test coverage, and the conflict generator's use of the crux (on [ABIO ConflictGen](ABIO%20ConflictGen.md)).
- 2026-10-28 — refreshed against 0eb23e5 (`6631831`): two ports on one pool sum, an unknown `stoich` key, `lam ≤ 0`, an unknown `kind` and an out-of-range lattice `k`/index all refuse, and a transport chain builds (`Fragment.merge` lets a parentless declaration yield).
