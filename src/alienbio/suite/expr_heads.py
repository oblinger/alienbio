"""Layers 0–2 of the Expr head catalog (M47.2): blocks, skeletons, worlds.

Every head here is a thin registration over an existing suite class or
function — nothing generative is re-implemented. The one new rule is
**pools-as-names**: a block head takes *pool names* where the block class
takes port names, and a :func:`block` binds any two children that name the
same pool through one parent port, so ``!source {pool: precursor}`` and
``!crux {precursor: precursor}`` share a molecule without a ``PoolBinding``
table. A ``rate`` (or any ``Dist`` slot) accepts a number (promoted to
``Constant``), a quoted form (already a ``Dist``) or a ``Dist``.

Importing this module registers the heads; ``Env.standard`` imports it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Mapping, Optional, Sequence

from ..bio.chemistry import ChemistryImpl
from ..bio.world import Compartment, PopulationLawSpec, Transport, WorldImpl
from ..infra.entity import Entity, get_registered_heads
from ..expr.env import Env, ExprError
from ..expr.form import is_form
from ..expr.interp import evaluate
from ..expr.registry import expander, fn
from .arch_diagnose import draft_diagnosis_world
from .arch_intervene import draft_intervention_world
from .arch_predict import draft_prediction_world
from .blocks import (
    ConflictCruxBlock,
    CooperativeBindingBlock,
    EnzymeBlock,
    InhibitionBlock,
    PoissonSchedule,
    PopulationBlock,
    PressureBlock,
    ReactionBlock,
    SignalingBlock,
    SinkBlock,
    SourceBlock,
    SpatialLatticeBlock,
    TransportBlock,
)
from .conflict_gen import draft_conflict_world
from .delta_gen import draft_delta_pair
from .dist import Constant, Dist, Seed
from .pressure_gen import draft_pressure_world
from .rate_law import RateLaw, compile_rate
from ..bio.molecule import MoleculeImpl
from ..bio.reaction import ReactionImpl
from ..infra.mk import mk
from .skeleton import Fragment, Provenance
from .skeleton import PoolBinding, Port, PortDir, Role, Skeleton, SkeletonBlock
from .verify import SimConfig, simulate

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _dist(value: Any, what: str, env: Env) -> Optional[Dist[float]]:
    """A ``Dist`` slot: None passes through (the class default applies), a number
    becomes ``Constant``, a ``Dist`` (a quoted form is one) is used as is."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise env.error(f"{what}: expected a number or a Dist, got a bool")
    if isinstance(value, (int, float)):
        return Constant(float(value))
    if isinstance(value, Dist):
        return value
    raise env.error(f"{what}: expected a number, a quoted form or a Dist, got {type(value).__name__}")


def _pool(name: Any, env: Env) -> str:
    """A pool name as this scope spells it (``Env.pool``): namespaced by the
    template instance unless it arrived as an argument (M47.5)."""
    return env.pool(name)


def _name(name: Optional[str], env: Env) -> str:
    """A block's node name: explicit, else the node's key in the document."""
    if name:
        return str(name)
    tail = env.path.rsplit(".", 1)[-1] if env.path else ""
    return tail or "block"


def _role(role: str, env: Env) -> Role:
    try:
        return Role[str(role).upper()]
    except KeyError:
        raise env.error(f"unknown role {role!r}; expected one of {[r.name.lower() for r in Role]}") from None


def _maybe(**kwargs: Any) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}


# ---------------------------------------------------------------------------
# Layer 1 — blocks (pools as names)
# ---------------------------------------------------------------------------


@fn(summary="SUPPLY: ∅ → pool @ rate")
def source(pool: str = "out", rate: Any = None, container: Optional[str] = None, name: Optional[str] = None, *, env: Env) -> SourceBlock:
    return SourceBlock.make(_name(name, env), port=_pool(pool, env), container=container, rate=_dist(rate, "source.rate", env))


@fn(summary="SINK: pool → ∅ @ rate")
def sink(pool: str = "in", rate: Any = None, container: Optional[str] = None, name: Optional[str] = None, *, env: Env) -> SinkBlock:
    return SinkBlock.make(_name(name, env), port=_pool(pool, env), container=container, rate=_dist(rate, "sink.rate", env))


from dataclasses import dataclass as _dataclass, field as _field
from typing import cast as _cast


@_dataclass(frozen=True)
class RateLawBlock(ReactionBlock):
    """A :class:`ReactionBlock` whose rate is a compiled :class:`RateLaw`
    (M47.3): mass action over the reactant ports times the law's modulations,
    each attached to its modifier pool as a non-consumed ``ReactionImpl``
    modifier. The modifier pools are extra ``IN`` ports, so pools-as-names
    binding wires them like any other."""

    law: RateLaw = _field(default_factory=lambda: RateLaw(k=Constant(1.0)))

    def realize(self, seed: Seed, ns: str, bound: Mapping[str, MoleculeImpl]) -> Fragment:
        modifier_pools = set(self.law.modifier_pools)
        reactants: dict[MoleculeImpl, float] = {}
        products: dict[MoleculeImpl, float] = {}
        for port in self.ports:
            if port.name in modifier_pools:
                continue
            coef = self.stoich.get(port.name, 1.0)
            (reactants if port.direction is PortDir.IN else products)[bound[port.name]] = coef
        modifiers = {bound[m.pool]: m.sample(seed.child(f"mod/{m.pool}")) for m in self.law.modulations}
        k = float(self.law.k.sample(seed.child("rate")))
        rxn_id = f"{ns}/rxn"
        reaction = _cast(ReactionImpl, mk.R(rxn_id, reactants, products, modifiers=modifiers, rate=k))
        molecules = {m.name: m for m in [*reactants, *products, *modifiers]}
        container = self.ports[0].container if self.ports else None
        return Fragment(molecules=molecules, reactions={rxn_id: reaction}, provenance=(Provenance(rxn_id, container or "cell"),))


@fn(summary="one reaction over named pools; rate is k or a compiled rate law")
def reaction(
    reactants: Sequence[str] = (),
    products: Sequence[str] = (),
    rate: Any = None,
    stoich: Optional[Mapping[str, float]] = None,
    container: Optional[str] = None,
    role: str = "supply",
    name: Optional[str] = None,
    *,
    env: Env,
) -> ReactionBlock:
    if not reactants and not products:
        raise env.error("reaction: needs at least one reactant or product pool")
    reactant_pools = [_pool(p, env) for p in reactants]
    product_pools = [_pool(p, env) for p in products]
    law = compile_rate(rate, env, reactants=reactant_pools, products=product_pools)
    ports = tuple(Port(p, container, PortDir.IN) for p in reactant_pools) + tuple(
        Port(p, container, PortDir.OUT) for p in product_pools
    )
    if not law.modulations:
        return ReactionBlock(name=_name(name, env), role=_role(role, env), ports=ports, rate=law.k, stoich=dict(stoich or {}))
    ports = ports + tuple(Port(pool, container, PortDir.IN) for pool in law.modifier_pools)
    return RateLawBlock(name=_name(name, env), role=_role(role, env), ports=ports, rate=law.k, stoich=dict(stoich or {}), law=law)


@fn(summary="CRUX: one precursor pool feeding two rival routes")
def crux(precursor: str = "precursor", kA: Any = None, kB: Any = None, container: Optional[str] = None, name: Optional[str] = None, *, env: Env) -> ConflictCruxBlock:
    return ConflictCruxBlock.make(
        _name(name, env), precursor_port=_pool(precursor, env), container=container, kA=_dist(kA, "crux.kA", env), kB=_dist(kB, "crux.kB", env)
    )


@fn(summary="SIGNALING: a sensed pool modulates a reaction's rate")
def signal(
    in_pool: str = "in",
    out_pool: str = "out",
    modifier: str = "modifier",
    kind: str = "activator",
    a: Any = None,
    Ki: Any = None,
    rate: Any = None,
    container: Optional[str] = None,
    name: Optional[str] = None,
    *,
    env: Env,
) -> SignalingBlock:
    return SignalingBlock.make(
        _name(name, env),
        in_port=_pool(in_pool, env),
        out_port=_pool(out_pool, env),
        modifier_port=_pool(modifier, env),
        container=container,
        kind=kind,
        **_maybe(rate=_dist(rate, "signal.rate", env), a=_dist(a, "signal.a", env), Ki=_dist(Ki, "signal.Ki", env)),
    )


@fn(summary="INHIBITION: a modifier pool throttles a reaction")
def inhibit(in_pool: str = "in", out_pool: str = "out", modifier: str = "modifier", Ki: Any = None, rate: Any = None, container: Optional[str] = None, name: Optional[str] = None, *, env: Env) -> InhibitionBlock:
    return InhibitionBlock.make(
        _name(name, env), in_port=_pool(in_pool, env), out_port=_pool(out_pool, env), modifier_port=_pool(modifier, env), container=container,
        **_maybe(rate=_dist(rate, "inhibit.rate", env), Ki=_dist(Ki, "inhibit.Ki", env)),
    )


@fn(summary="ENZYME: catalysed substrate → product")
def enzyme(substrate: str = "substrate", product: str = "product", enzyme: str = "enzyme", Vmax: Any = None, K: Any = None, rate: Any = None, container: Optional[str] = None, name: Optional[str] = None, *, env: Env) -> EnzymeBlock:
    return EnzymeBlock.make(
        _name(name, env), substrate_port=_pool(substrate, env), product_port=_pool(product, env), modifier_port=_pool(enzyme, env), container=container,
        **_maybe(rate=_dist(rate, "enzyme.rate", env), Vmax=_dist(Vmax, "enzyme.Vmax", env), K=_dist(K, "enzyme.K", env)),
    )


@fn(summary="COOPERATIVE: Hill-shaped response to a modifier pool")
def cooperative(in_pool: str = "in", out_pool: str = "out", modifier: str = "modifier", Vmax: Any = None, K: Any = None, n: Any = None, rate: Any = None, container: Optional[str] = None, name: Optional[str] = None, *, env: Env) -> CooperativeBindingBlock:
    return CooperativeBindingBlock.make(
        _name(name, env), in_port=_pool(in_pool, env), out_port=_pool(out_pool, env), modifier_port=_pool(modifier, env), container=container,
        **_maybe(rate=_dist(rate, "cooperative.rate", env), Vmax=_dist(Vmax, "cooperative.Vmax", env), K=_dist(K, "cooperative.K", env), n=_dist(n, "cooperative.n", env)),
    )


@fn(summary="PRESSURE: an exogenous drain / Poisson-scheduled insult on a pool")
def insult(pool: str = "stressed", rate: Any = None, poisson: Optional[Mapping[str, float]] = None, container: Optional[str] = None, name: Optional[str] = None, *, env: Env) -> PressureBlock:
    schedule = None
    if poisson is not None:
        if not isinstance(poisson, Mapping) or not {"lam", "horizon"} <= set(poisson):
            raise env.error("insult.poisson: expected {lam: .., horizon: ..}")
        schedule = PoissonSchedule(float(poisson["lam"]), float(poisson["horizon"]))
    return PressureBlock.make(_name(name, env), port=_pool(pool, env), container=container, rate=_dist(rate, "insult.rate", env), poisson=schedule)


@fn(summary="TRANSPORT: flux of a pool between two compartments")
def transport(pool: str = "pool", container: Optional[str] = None, dest_container: str = "cell2", rate: Any = None, rate_law: str = "gradient", src_volume: float = 1.0, dest_volume: float = 1.0, name: Optional[str] = None, *, env: Env) -> TransportBlock:
    return TransportBlock.make(
        _name(name, env), port=_pool(pool, env), container=container, dest_container=dest_container, rate=_dist(rate, "transport.rate", env),
        rate_law=rate_law, src_volume=src_volume, dest_volume=dest_volume,
    )


@fn(summary="LATTICE: a k-cell diffusion patch")
def lattice(k: int = 3, molecule: str = "x", diffusion: Any = None, volume: float = 1.0, initial: Optional[Mapping[int, float]] = None, name: Optional[str] = None, *, env: Env) -> SpatialLatticeBlock:
    return SpatialLatticeBlock.make(_name(name, env), k=int(k), molecule=_pool(molecule, env), diffusion=_dist(diffusion, "lattice.diffusion", env), volume=volume, initial=initial)


@fn(summary="POPULATION: counts with per-capita growth/death, mass-coupled to a resource")
def population(name: Optional[str] = None, growth_rate: Any = None, death_rate: Any = None, *, env: Env, **kwargs: Any) -> PopulationBlock:
    return PopulationBlock.make(
        _name(name, env), **_maybe(growth_rate=_dist(growth_rate, "population.growth_rate", env), death_rate=_dist(death_rate, "population.death_rate", env)), **kwargs
    )


@fn(summary="a pattern node: children sharing a pool name share the pool")
def block(children: Mapping[str, SkeletonBlock], role: str = "supply", name: Optional[str] = None, *, env: Env) -> SkeletonBlock:
    if not isinstance(children, Mapping):
        raise env.error("block: children must be a mapping of name -> block")
    kids: list[SkeletonBlock] = []
    pools: dict[str, dict[str, Any]] = {}  # pool -> {"out": bool, "container": ..}
    bindings: list[PoolBinding] = []
    for key, child in children.items():
        if not isinstance(child, SkeletonBlock):
            raise env.error(f"block: child {key!r} is not a block (got {type(child).__name__})")
        if child.name != key:
            child = replace(child, name=str(key))
        kids.append(child)
        for port in child.ports:
            info = pools.setdefault(port.name, {"out": False, "container": None})
            if port.direction is PortDir.OUT:
                info["out"] = True
            if info["container"] is None:
                info["container"] = port.container
            bindings.append(PoolBinding(f"self.{port.name}", f"{child.name}.{port.name}"))
    ports = tuple(
        Port(pool, info["container"], PortDir.OUT if info["out"] else PortDir.IN) for pool, info in pools.items()
    )
    return SkeletonBlock(name=_name(name, env), role=_role(role, env), ports=ports, children=tuple(kids), pool_bindings=tuple(bindings))


@fn(summary="a Skeleton: root block + control surface + crux")
def skeleton(root: SkeletonBlock, control_surface: Sequence[str] = (), crux: str = "", *, env: Env) -> Skeleton:
    if not isinstance(root, SkeletonBlock):
        raise env.error(f"skeleton: root must be a block, got {type(root).__name__}")
    return Skeleton(root=root, control_surface=tuple(str(c) for c in control_surface), crux=str(crux))


# ---------------------------------------------------------------------------
# Layer 2 — worlds
# ---------------------------------------------------------------------------


@fn(summary="materialize a skeleton into a World (under this node's seed)")
def world(skeleton: Skeleton, initial: Optional[Mapping[str, float]] = None, container: Optional[str] = None, seed: Optional[Seed] = None, *, env: Env) -> WorldImpl:
    if not isinstance(skeleton, Skeleton):
        raise env.error(f"world: skeleton must be a Skeleton, got {type(skeleton).__name__}")
    w = skeleton.materialize(seed or env.ctx.seed)
    if not initial:
        return w
    pools = dict(skeleton.root.resolved_ports)
    molecules = set(w.chemistry.molecules)
    comps = list(w.compartments)
    target_idx = 0
    if container is not None:
        ids = [c.id for c in comps]
        if container not in ids:
            raise env.error(f"world.initial: no compartment {container!r} (have {ids})")
        target_idx = ids.index(container)
    extra: dict[str, float] = {}
    for pool, value in initial.items():
        spelled = _pool(pool, env)
        mol = pools.get(spelled, pools.get(str(pool), spelled))
        if mol not in molecules:
            raise env.error(f"world.initial: no pool or molecule {pool!r} in this world")
        extra[mol] = float(value)
    comp = comps[target_idx]
    comps[target_idx] = replace(comp, concentrations={**comp.concentrations, **extra})
    return WorldImpl(w.chemistry, tuple(comps), flows=w.flows, population_laws=w.population_laws)


@fn(summary="integration parameters")
def sim(dt: float = 0.1, steps: int = 200, sample_every: int = 10) -> SimConfig:
    return SimConfig(dt=float(dt), steps=int(steps), sample_every=int(sample_every))


def _callable(value: Any, what: str, env: Env) -> Callable[..., Any]:
    if isinstance(value, str):
        return env.head(value).fn
    if callable(value):
        return value
    raise env.error(f"{what}: expected a head name or a callable")


@expander(summary="reject-sample a world until a validity predicate holds")
def verify(args: Sequence[Any], kwargs: Mapping[str, Any], env: Env) -> Any:
    allowed = {"world", "perturb", "valid", "max_redraws", "sim"}
    unknown = set(kwargs) - allowed
    if args or unknown:
        raise env.error(f"verify: keywords only, from {sorted(allowed)}; got {sorted(unknown)}")
    for key in ("world", "perturb", "valid"):
        if key not in kwargs:
            raise env.error(f"verify: missing {key!r}")
    perturb = _callable(evaluate(kwargs["perturb"], env.child("perturb")), "verify.perturb", env)
    valid = _callable(evaluate(kwargs["valid"], env.child("valid")), "verify.valid", env)
    max_redraws = int(evaluate(kwargs.get("max_redraws", 8), env.child("max_redraws")))
    cfg = evaluate(kwargs["sim"], env.child("sim")) if "sim" in kwargs else SimConfig()
    world_form = kwargs["world"]
    for attempt in range(max_redraws + 1):
        attempt_env = env.child(f"attempt{attempt}")
        w = evaluate(world_form, attempt_env)
        baseline = simulate(w, cfg, attempt_env.ctx.seed.child("base"))
        perturbed = simulate(perturb(w), cfg, attempt_env.ctx.seed.child("pert"))
        if valid(baseline, perturbed):
            return w
    raise env.error(f"verify: no world passed the validity predicate in {max_redraws + 1} attempts")


# ---- the generative world drafters, as heads over their own signatures -----

_DIST_KEYS = frozenset({"k_clean", "k_fast", "k_i2t", "k_byproduct", "k_hop", "kA", "kB", "k_drive", "k_sink", "k_t_sink"})


def _dist_kwargs(kwargs: Mapping[str, Any], env: Env) -> dict[str, Any]:
    out = dict(kwargs)
    for k in list(out):
        if k in _DIST_KEYS:
            out[k] = _dist(out[k], k, env)
    return out


@fn(summary="EXP-2 pressure world: {world, skeleton, objective}", guarded_params={"pi"})
def pressure_world(*, env: Env, **kwargs: Any) -> dict[str, Any]:
    w, sk, obj = draft_pressure_world(env.ctx.seed, **_dist_kwargs(kwargs, env))
    return {"world": w, "skeleton": sk, "objective": obj}


@fn(summary="conflict-ladder world: {world, skeleton, objective}", guarded_params={"rung"})
def conflict_world(*, env: Env, **kwargs: Any) -> dict[str, Any]:
    w, sk, obj = draft_conflict_world(env.ctx.seed, **_dist_kwargs(kwargs, env))
    return {"world": w, "skeleton": sk, "objective": obj}


@fn(summary="delta matched pair: [{world, skeleton, objective} match, ... mismatch]")
def delta_pair(*, env: Env, **kwargs: Any) -> list[dict[str, Any]]:
    pair = draft_delta_pair(env.ctx.seed, **_dist_kwargs(kwargs, env))
    return [{"world": w, "skeleton": sk, "objective": obj} for (w, sk, obj) in pair]


@fn(summary="diagnosis world: {world, skeleton}", guarded_params={"hazard", "perturbation"})
def diagnosis_world(*, env: Env, **kwargs: Any) -> dict[str, Any]:
    w, carve = draft_diagnosis_world(env.ctx.seed, **kwargs)
    return {"world": w, "skeleton": carve}


@fn(summary="prediction world: {world, skeleton, reaction_id}")
def prediction_world(*, env: Env, **kwargs: Any) -> dict[str, Any]:
    w, carve, rid = draft_prediction_world(env.ctx.seed, **kwargs)
    return {"world": w, "skeleton": carve, "reaction_id": rid}


@fn(summary="intervention world: {world, skeleton, target: {molecule, value}}", guarded_params={"target_margin"})
def intervention_world(*, env: Env, **kwargs: Any) -> dict[str, Any]:
    w, carve, (mol, value) = draft_intervention_world(env.ctx.seed, **kwargs)
    return {"world": w, "skeleton": carve, "target": {"molecule": mol, "value": value}}


# ---------------------------------------------------------------------------
# Constructors (M47.6) — every registered Entity head, by its head name
# ---------------------------------------------------------------------------
#
# ``!Molecule {...}`` / ``!Reaction {...}`` / ``!Chemistry {...}`` call the
# class's ``hydrate`` with the mapping; the node's key is the name when none
# is given. A mapping carrying ``_type: Reaction`` is the untagged spelling of
# the same call (the interpreter rewrites it), kept for saved worlds.
# ``Compartment`` and ``World`` build the world *records* the simulator runs
# (``bio.world.Compartment`` / ``WorldImpl``) — the M1 ``CompartmentImpl``
# entity tree is not what a suite world is made of.


def _entity_name(name: Optional[str], env: Env) -> str:
    return str(name) if name else _name(None, env)


def _as_names(items: Any, what: str, env: Env) -> list[Any]:
    """Reaction sides as ``[{name: coef}]``: a repeated name sums (``[A, A]`` is
    ``{A: 2}``), a ``{name: coef}`` mapping is taken as given, a Molecule
    object stands for its name."""
    coefs: dict[str, float] = {}
    for item in items or ():
        if isinstance(item, Entity):
            coefs[item.local_name] = coefs.get(item.local_name, 0.0) + 1.0
        elif isinstance(item, str):
            coefs[item] = coefs.get(item, 0.0) + 1.0
        elif isinstance(item, Mapping):
            for key, coef in item.items():
                coefs[str(key)] = coefs.get(str(key), 0.0) + float(coef)
        else:
            raise env.error(f"{what}: expected molecule names, {{name: coef}} or Molecules, got {type(item).__name__}")
    return [{name: coef} for name, coef in coefs.items()]


def _side_names(items: Sequence[Any]) -> list[str]:
    names: list[str] = []
    for item in items:
        names.extend(item.keys() if isinstance(item, Mapping) else [str(item)])
    return names


def _register_entity_constructor(head_name: str, cls: type) -> None:
    def construct(name: Optional[str] = None, *, env: Env, **fields: Any) -> Any:
        data = {k: v for k, v in fields.items()}
        data["name"] = _entity_name(name, env)
        try:
            return cls.hydrate(data, local_name=data["name"])  # type: ignore[attr-defined]
        except (KeyError, TypeError, ValueError) as exc:
            raise env.error(f"{head_name}: {exc}") from exc

    construct.__name__ = head_name
    construct.__doc__ = f"``!{head_name} {{...}}`` — ``{cls.__name__}.hydrate`` over the mapping (M47.6)."
    fn(construct, kind="constructor", name=head_name, summary=f"construct a {cls.__name__} (by hydrate)")


for _head_name, _cls in get_registered_heads().items():
    if _head_name not in ("Entity", "Compartment"):
        _register_entity_constructor(_head_name, _cls)


@fn(kind="constructor", name="Reaction", summary="construct a Reaction; unknown molecule names are minted")
def Reaction(
    reactants: Sequence[Any] = (),
    products: Sequence[Any] = (),
    rate: Any = None,
    name: Optional[str] = None,
    molecules: Optional[Mapping[str, Any]] = None,
    *,
    env: Env,
    **fields: Any,
) -> ReactionImpl:
    """``!Reaction {reactants: [A], products: [B], rate: 0.1}``. Molecule
    names resolve against ``molecules`` (a mapping, or the Molecules given
    inline); any other name is minted as a plain Molecule."""
    lhs = _as_names(reactants, "Reaction.reactants", env)
    rhs = _as_names(products, "Reaction.products", env)
    known: dict[str, MoleculeImpl] = {}
    for item in list(reactants or ()) + list(products or ()):
        if isinstance(item, MoleculeImpl):
            known[item.local_name] = item
    for key, value in (molecules or {}).items():
        known[str(key)] = value if isinstance(value, MoleculeImpl) else _cast(MoleculeImpl, mk.M(str(key)))
    for mol_name in _side_names(lhs) + _side_names(rhs):
        known.setdefault(mol_name, _cast(MoleculeImpl, mk.M(mol_name)))
    data: dict[str, Any] = {"reactants": lhs, "products": rhs, **fields}
    if rate is not None:
        data["rate"] = float(rate) if isinstance(rate, (int, float)) and not isinstance(rate, bool) else rate
    rxn_name = _entity_name(name, env)
    data["name"] = rxn_name
    try:
        return ReactionImpl.hydrate(data, molecules=known, local_name=rxn_name)
    except (KeyError, TypeError, ValueError) as exc:
        raise env.error(f"Reaction: {exc}") from exc


@fn(kind="constructor", name="Chemistry", summary="construct a Chemistry from molecules + reactions (names, mappings or objects)")
def Chemistry(
    molecules: Any = (),
    reactions: Any = (),
    name: Optional[str] = None,
    *,
    env: Env,
    **fields: Any,
) -> ChemistryImpl:
    """``!Chemistry {molecules: [A, B], reactions: {r1: {reactants: [A], products: [B]}}}``.
    ``molecules`` is a list of names / Molecules or a mapping name -> fields;
    ``reactions`` a mapping name -> fields / Reaction, or a list of Reactions."""
    mols: dict[str, Any] = {}
    if isinstance(molecules, Mapping):
        for key, value in molecules.items():
            mols[str(key)] = _entity_fields(value) if isinstance(value, Entity) else (value or {})
    else:
        for item in molecules or ():
            key = item.local_name if isinstance(item, Entity) else str(item)
            mols[key] = _entity_fields(item) if isinstance(item, Entity) else {}
    rxns: dict[str, Any] = {}
    items = reactions.items() if isinstance(reactions, Mapping) else [(r.local_name if isinstance(r, Entity) else None, r) for r in reactions or ()]
    for key, value in items:
        if isinstance(value, Entity):
            fields_ = _entity_fields(value)
        elif isinstance(value, Mapping):
            fields_ = dict(value)
        else:
            raise env.error(f"Chemistry.reactions[{key!r}]: expected a mapping or a Reaction")
        if key is None:
            raise env.error("Chemistry.reactions: a listed reaction must be a Reaction object (it carries its name)")
        rxns[str(key)] = fields_
        for side in ("reactants", "products", "modifiers"):
            for mol_name in _side_names([fields_.get(side, ())] if isinstance(fields_.get(side), Mapping) else list(fields_.get(side) or ())):
                mols.setdefault(mol_name, {})
    chem_name = _entity_name(name, env)
    try:
        return ChemistryImpl.hydrate({"name": chem_name, "molecules": mols, "reactions": rxns, **fields}, local_name=chem_name)
    except (KeyError, TypeError, ValueError) as exc:
        raise env.error(f"Chemistry: {exc}") from exc


def _entity_fields(entity: Entity) -> dict[str, Any]:
    """An entity's hydratable fields (its attributes minus the name)."""
    return {k: v for k, v in entity.attributes().items() if k != "name"}


@fn(kind="constructor", name="Compartment", summary="a world compartment record: id, kind, volume, parent, concentrations")
def Compartment_(
    id: Optional[str] = None,
    kind: str = "cell",
    volume: float = 1.0,
    parent: Optional[str] = None,
    concentrations: Optional[Mapping[str, float]] = None,
    multiplicity: float = 1.0,
    *,
    env: Env,
) -> Compartment:
    return Compartment(
        id=_entity_name(id, env), parent=parent, kind=str(kind), volume=float(volume),
        concentrations={str(k): float(v) for k, v in (concentrations or {}).items()}, multiplicity=float(multiplicity),
    )


@fn(kind="constructor", name="World", summary="a World from a Chemistry and its compartment records")
def World(
    chemistry: ChemistryImpl,
    compartments: Sequence[Compartment] = (),
    flows: Sequence[Transport] = (),
    population_laws: Sequence[PopulationLawSpec] = (),
    *,
    env: Env,
) -> WorldImpl:
    if not isinstance(chemistry, ChemistryImpl):
        raise env.error(f"World: chemistry must be a Chemistry (see !Chemistry), got {type(chemistry).__name__}")
    comps = list(compartments) or [Compartment(id="cell", parent=None, kind="cell", volume=1.0)]
    for c in comps:
        if not isinstance(c, Compartment):
            raise env.error(f"World: compartments must be Compartment records (see !Compartment), got {type(c).__name__}")
    unknown = sorted({m for c in comps for m in c.concentrations} - set(chemistry.molecules))
    if unknown:
        raise env.error(f"World: concentrations name molecules not in the chemistry: {unknown}")
    return WorldImpl(chemistry, tuple(comps), flows=tuple(flows), population_laws=tuple(population_laws))


__all__ = [
    "Chemistry", "Compartment_", "Reaction", "World",
    "block", "conflict_world", "cooperative", "crux", "delta_pair", "diagnosis_world", "enzyme", "inhibit",
    "insult", "intervention_world", "lattice", "population", "prediction_world", "pressure_world", "reaction",
    "signal", "sim", "sink", "skeleton", "source", "transport", "verify", "world", "is_form", "ExprError",
]
