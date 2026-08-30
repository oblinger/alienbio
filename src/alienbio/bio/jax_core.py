"""Vectorized JAX primitives for the world simulator (M24 core).

This module holds the pure-functional, GPU-ready kernels used by
``JaxWorldSimulator``.  Everything here operates on a dense state array
``S`` of shape ``[num_compartments, num_molecules]`` and is written so it
can be ``jax.jit`` / ``jax.lax.fori_loop`` / ``jax.vmap`` composed without
any host round-trips.

Design notes
------------
* **Compartments and molecules are fully vectorized** (M24.1/M24.2): the
  per-reaction math is expressed as array ops across all compartments and
  molecules at once, using padded ``[Rn, M]`` stoichiometry matrices.
* **Reactions are applied simultaneously** (H4): the reaction axis is fused
  into a single tensor update.  Every reaction's desired extent is computed
  from the SAME frozen start-of-step state; competition for shared reactants
  is resolved by single-pass proportional min-ratio scaling (identical to the
  scalar ``ReferenceSimulatorImpl`` / ``WorldSimulatorImpl``); the net stoich
  update is applied in one ``extentᵀ · (P - R)`` matmul.  This is
  order-independent, provably non-negative, mass-conserving, and reduces to
  the C1 clamp when reactions do not compete -- so it matches the scalar
  simulators, which now use the same simultaneous scheme.
* **Modulations and compiled rate laws** (M47.10): a reaction's non-consumed
  modulators (``Modulation`` kinds) are padded into ``[Rn, Mn]`` tensors and
  applied as a vectorised factor; a compiled rate expression
  (``bio.rate_expr``) is lowered to JAX ops over the state array and either
  replaces mass action (when it names a reactant) or multiplies it. Both
  match ``WorldSimulatorImpl`` to float64 precision.
* **C1 mass-conservation fix** is subsumed by the simultaneous scheme: for a
  single reaction the proportional ratio collapses to the old tightest-
  available-substrate clamp.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence, Tuple, cast

#: A JAX array in annotations — ``Any`` so the module types without JAX installed.
Array = Any

from .rate_expr import lower_jax

try:
    import jax
    import jax.numpy as jnp
    from jax import config as _jax_config

    HAS_JAX = True
except ImportError:  # pragma: no cover - exercised only when JAX absent
    HAS_JAX = False
    jax = jnp = _jax_config = cast(Any, None)  # every entry point checks HAS_JAX


def enable_x64() -> None:
    """Enable 64-bit floats in JAX (required for float64 parity)."""
    if HAS_JAX:
        _jax_config.update("jax_enable_x64", True)


def build_reaction_tensors(
    reactions: Sequence,
    num_molecules: int,
    num_compartments: int,
    dtype,
) -> Tuple[Array, Array, Array, Array]:
    """Pad reactions into uniform stoichiometry matrices (M24.1).

    Args:
        reactions: sequence of ReactionSpec-like objects with ``.reactants``,
            ``.products`` (Dict[molecule_id, stoich]), ``.rate_constant`` and
            ``.compartments`` (None = all).
        num_molecules: molecule vocabulary size (M).
        num_compartments: compartment count (C).
        dtype: jnp float dtype.

    Returns:
        r_stoich: [Rn, M] reactant stoichiometry (0 where not a reactant).
        p_stoich: [Rn, M] product stoichiometry.
        k:        [Rn]    rate constants.
        comp_mask:[Rn, C] 1.0 where the reaction is active, else 0.0.
    """
    rn = len(reactions)
    if rn == 0:
        z2 = jnp.zeros((0, num_molecules), dtype=dtype)
        return (
            z2,
            z2,
            jnp.zeros((0,), dtype=dtype),
            jnp.zeros((0, num_compartments), dtype=dtype),
        )

    r_stoich = [[0.0] * num_molecules for _ in range(rn)]
    p_stoich = [[0.0] * num_molecules for _ in range(rn)]
    k = [0.0] * rn
    comp_mask = [[0.0] * num_compartments for _ in range(rn)]

    for i, rxn in enumerate(reactions):
        for mol, s in rxn.reactants.items():
            r_stoich[i][mol] += float(s)
        for mol, s in rxn.products.items():
            p_stoich[i][mol] += float(s)
        k[i] = float(rxn.rate_constant)
        comps = rxn.compartments
        if comps is None:
            comps = range(num_compartments)
        for c in comps:
            comp_mask[i][c] = 1.0

    return (
        jnp.array(r_stoich, dtype=dtype),
        jnp.array(p_stoich, dtype=dtype),
        jnp.array(k, dtype=dtype),
        jnp.array(comp_mask, dtype=dtype),
    )


#: See ``world_simulator.ROUNDING_FLOOR``.
ROUNDING_FLOOR = 1e-12
RATE_CAP = 1e150

#: Modulation kinds by code, for the padded modulation tensors (0 = no slot).
MOD_KINDS: Tuple[str, ...] = ("", "activator", "inhibitor", "michaelis", "hill")


def build_modulation_tensors(
    reactions: Sequence, dtype
) -> Optional[Tuple[Array, Array, Array]]:
    """Pad every reaction's ``modulators`` into ``[Rn, Mn]`` tensors (M47.10):
    ``mod_mol`` (molecule index, 0 where padded), ``mod_kind`` (code into
    :data:`MOD_KINDS`, 0 where padded) and ``mod_params`` ``[Rn, Mn, 3]``
    (``a`` | ``Ki`` | ``K``, ``Vmax``, ``n``). ``None`` when no reaction is
    modulated — the fast path."""
    mods = [list(getattr(r, "modulators", {}).items()) for r in reactions]
    width = max((len(m) for m in mods), default=0)
    if width == 0:
        return None
    rn = len(reactions)
    mol = [[0] * width for _ in range(rn)]
    kind = [[0] * width for _ in range(rn)]
    params = [[[0.0, 1.0, 1.0] for _ in range(width)] for _ in range(rn)]
    for i, items in enumerate(mods):
        for j, (mol_id, m) in enumerate(items):
            code = MOD_KINDS.index(m.kind) if m.kind in MOD_KINDS else 0
            mol[i][j] = int(mol_id)
            if code == 1 and m.a is not None:
                kind[i][j], params[i][j][0] = 1, float(m.a)
            elif code == 2 and m.Ki is not None:
                kind[i][j], params[i][j][0] = 2, float(m.Ki)
            elif code == 3 and m.Vmax is not None and m.K is not None:
                kind[i][j], params[i][j] = 3, [float(m.K), float(m.Vmax), 1.0]
            elif code == 4 and m.Vmax is not None and m.K is not None and m.n is not None:
                kind[i][j], params[i][j] = 4, [float(m.K), float(m.Vmax), float(m.n)]
    return jnp.array(mol, dtype=jnp.int32), jnp.array(kind, dtype=jnp.int32), jnp.array(params, dtype=dtype)


def modulation_factors(S: Array, mod_mol: Array, mod_kind: Array, mod_params: Array) -> Array:
    """The dimensionless modulation factor per ``[Rn, C]`` — the product over
    a reaction's modulator slots of ``WorldSimulatorImpl._modulation_factor``'s
    per-kind terms (padded slots contribute 1)."""
    m = S[:, mod_mol]  # [C, Rn, Mn]
    m = jnp.transpose(m, (1, 0, 2))  # [Rn, C, Mn]
    kind = mod_kind[:, None, :]  # [Rn, 1, Mn]
    p0 = mod_params[:, None, :, 0]
    p1 = mod_params[:, None, :, 1]
    p2 = mod_params[:, None, :, 2]
    one = jnp.ones_like(m)
    activator = 1.0 + p0 * m
    inhibitor = 1.0 / (1.0 + m / jnp.where(kind == 2, p0, 1.0))
    denom_mm = p0 + m
    michaelis = jnp.where(denom_mm > 0.0, p1 * m / jnp.where(denom_mm > 0.0, denom_mm, 1.0), 0.0)
    m_n = m ** p2
    denom_h = p0**p2 + m_n
    hill = jnp.where(denom_h > 0.0, p1 * m_n / jnp.where(denom_h > 0.0, denom_h, 1.0), 0.0)
    factor = jnp.where(kind == 1, activator, one)
    factor = jnp.where(kind == 2, inhibitor, factor)
    factor = jnp.where(kind == 3, michaelis, factor)
    factor = jnp.where(kind == 4, hill, factor)
    return jnp.prod(factor, axis=2)  # [Rn, C]


#: A compiled rate law for the core: (reaction index, law over S -> [C], implicit mass action).
LawFn = Tuple[int, Callable[[Array], Array], bool]


def build_rate_laws(reactions: Sequence) -> List[LawFn]:
    """Lower every reaction's ``rate_law`` (species by molecule ID) to a JAX
    function over the state array (M47.10)."""
    laws: List[LawFn] = []
    for i, r in enumerate(reactions):
        law = getattr(r, "rate_law", None)
        if law is None:
            continue

        def fn(S: Array, _law: Any = law) -> Array:
            return lower_jax(_law, S, lambda mol_id: int(mol_id))

        laws.append((i, fn, bool(getattr(r, "implicit_mass_action", True))))
    return laws


def apply_reactions(
    S: Array,
    r_stoich: Array,
    p_stoich: Array,
    k: Array,
    comp_mask: Array,
    dt: float,
    modulation: Optional[Tuple[Array, Array, Array]] = None,
    laws: Sequence[LawFn] = (),
) -> Array:
    """Apply all reactions to state ``S`` [C, M] simultaneously (H4).

    Order-independent, provably non-negative, mass-conserving. Every reaction's
    desired extent is read from the frozen ``S``; shared reactants are rationed
    by single-pass proportional min-ratio scaling; the fused net update is one
    matmul.  Shapes: reactions ``Rn``, compartments ``C``, molecules ``M``.

      desired[r, c] = clip(k[r] * Π_m S[c, m] ** R[r, m] * dt, 0) * comp_mask[r, c]
      demand[c, m]  = Σ_r desired[r, c] * R[r, m]                    (consumption)
      ratio[c, m]   = min(1, S[c, m] / demand[c, m])   (1 where demand == 0)
      scale[r, c]   = min_{m : R[r, m] > 0} ratio[c, m]   (1 if r has no reactant)
      extent[r, c]  = desired[r, c] * scale[r, c]
      S            += extentᵀ · (P - R)

    Non-negativity: for any (c, m),
      Σ_r extent[r, c] R[r, m] = Σ_r desired[r, c] scale[r, c] R[r, m]
                              ≤ ratio[c, m] · demand[c, m] ≤ S[c, m],
    since scale[r, c] ≤ ratio[c, m] for every reactant m of r.
    """
    rn = r_stoich.shape[0]
    net = p_stoich - r_stoich  # [Rn, M]
    if rn == 0:
        return S

    inf = jnp.array(jnp.inf, dtype=S.dtype)
    is_reactant = r_stoich > 0  # [Rn, M]
    has_reactant = jnp.any(is_reactant, axis=1)  # [Rn]

    # desired[r, c]: mass-action rate from the frozen state. 0**0 == 1 in jnp,
    # so non-reactant molecules (stoich 0) contribute a factor of 1.
    powers = S[None, :, :] ** r_stoich[:, None, :]  # [Rn, C, M]
    mass_action = jnp.prod(powers, axis=2)  # [Rn, C]
    rate = k[:, None] * mass_action  # [Rn, C]
    for idx, law_fn, implicit in laws:
        # M47.10 — a compiled rate law: the whole rate, or the factor on mass action.
        law_rate = law_fn(S)  # [C]
        rate = rate.at[idx].set(law_rate * mass_action[idx] if implicit else law_rate)
    if modulation is not None:
        rate = rate * modulation_factors(S, *modulation)
    rate = rate * dt
    rate = jnp.where(jnp.isnan(rate), 0.0, jnp.minimum(rate, RATE_CAP))  # see WorldSimulatorImpl._desired_extent
    desired = jnp.maximum(rate, 0.0) * comp_mask  # [Rn, C]

    # demand[c, m] = total consumption of molecule m across reactions.
    demand = jnp.einsum("rc,rm->cm", desired, r_stoich)  # [C, M]
    safe_demand = jnp.where(demand > 0, demand, jnp.ones_like(demand))
    ratio = jnp.where(demand > 0, jnp.minimum(1.0, S / safe_demand), 1.0)  # [C, M]

    # scale[r, c] = tightest ratio over r's reactants (1 if r has no reactant).
    masked = jnp.where(is_reactant[:, None, :], ratio[None, :, :], inf)  # [Rn,C,M]
    scale = jnp.min(masked, axis=2)  # [Rn, C]
    scale = jnp.where(has_reactant[:, None], scale, 1.0)

    extent = desired * scale  # [Rn, C]
    S = S + jnp.einsum("rc,rm->cm", extent, net)
    # float rounding of an exact zero -> zero (matches WorldSimulatorImpl, M48.6)
    return jnp.where((S < 0.0) & (S > -ROUNDING_FLOOR), 0.0, S)


def apply_native_flows(
    S: Array,
    flows: Sequence[Tuple[int, int, int, float]],
    dt: float,
) -> Array:
    """Apply linear inter-compartment transfer flows, JAX-native (M24.5).

    Each flow is ``(src, dst, molecule, rate)`` and moves
    ``dt * rate * S[src, molecule]`` from ``src`` to ``dst`` for that
    molecule (proportional, stable for ``dt*rate <= 1``).  Applied in list
    order, matching an equivalent sequence of GeneralFlows.  This is a pure
    JAX op so it compiles into the jitted / vmapped time loop rather than
    being left in Python (fixing the F8 "JAX silently drops flows" bug).
    """
    for src, dst, mol, rate in flows:
        moved = dt * rate * S[src, mol]
        S = S.at[src, mol].add(-moved)
        S = S.at[dst, mol].add(moved)
    return S


def make_step_fn(
    r_stoich: Array,
    p_stoich: Array,
    k: Array,
    comp_mask: Array,
    dt: float,
    native_flows: Sequence[Tuple[int, int, int, float]],
    modulation: Optional[Tuple[Array, Array, Array]] = None,
    laws: Sequence[LawFn] = (),
):
    """Build a pure ``S -> S`` single-step function (reactions then flows)."""

    def step(S: Array) -> Array:
        S = apply_reactions(S, r_stoich, p_stoich, k, comp_mask, dt, modulation, laws)
        if native_flows:
            S = apply_native_flows(S, native_flows, dt)
        return S

    return step


def make_run_fn(step_fn):
    """Build a GPU-resident multi-step run using ``jax.lax.fori_loop`` (M24.3).

    Returns a jitted function ``(S0, steps) -> S_final`` that keeps the state
    on-device for the whole trajectory (no per-step host<->device transfer).
    """

    def run(S0: Array, steps: int) -> Array:
        def body(_i, S):
            return step_fn(S)

        return jax.lax.fori_loop(0, steps, body, S0)

    return jax.jit(run, static_argnums=(1,))
