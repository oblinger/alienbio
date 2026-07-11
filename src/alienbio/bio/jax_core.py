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
* **C1 mass-conservation fix** is subsumed by the simultaneous scheme: for a
  single reaction the proportional ratio collapses to the old tightest-
  available-substrate clamp.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

try:
    import jax
    import jax.numpy as jnp
    from jax import config as _jax_config

    HAS_JAX = True
except ImportError:  # pragma: no cover - exercised only when JAX absent
    HAS_JAX = False


def enable_x64() -> None:
    """Enable 64-bit floats in JAX (required for float64 parity)."""
    if HAS_JAX:
        _jax_config.update("jax_enable_x64", True)


def build_reaction_tensors(
    reactions: Sequence,
    num_molecules: int,
    num_compartments: int,
    dtype,
) -> Tuple["jnp.ndarray", "jnp.ndarray", "jnp.ndarray", "jnp.ndarray"]:
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


def apply_reactions(
    S: "jnp.ndarray",
    r_stoich: "jnp.ndarray",
    p_stoich: "jnp.ndarray",
    k: "jnp.ndarray",
    comp_mask: "jnp.ndarray",
    dt: float,
) -> "jnp.ndarray":
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
    rate = k[:, None] * jnp.prod(powers, axis=2) * dt  # [Rn, C]
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
    return S + jnp.einsum("rc,rm->cm", extent, net)


def apply_native_flows(
    S: "jnp.ndarray",
    flows: Sequence[Tuple[int, int, int, float]],
    dt: float,
) -> "jnp.ndarray":
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
    r_stoich: "jnp.ndarray",
    p_stoich: "jnp.ndarray",
    k: "jnp.ndarray",
    comp_mask: "jnp.ndarray",
    dt: float,
    native_flows: Sequence[Tuple[int, int, int, float]],
):
    """Build a pure ``S -> S`` single-step function (reactions then flows)."""

    def step(S: "jnp.ndarray") -> "jnp.ndarray":
        S = apply_reactions(S, r_stoich, p_stoich, k, comp_mask, dt)
        if native_flows:
            S = apply_native_flows(S, native_flows, dt)
        return S

    return step


def make_run_fn(step_fn):
    """Build a GPU-resident multi-step run using ``jax.lax.fori_loop`` (M24.3).

    Returns a jitted function ``(S0, steps) -> S_final`` that keeps the state
    on-device for the whole trajectory (no per-step host<->device transfer).
    """

    def run(S0: "jnp.ndarray", steps: int) -> "jnp.ndarray":
        def body(_i, S):
            return step_fn(S)

        return jax.lax.fori_loop(0, steps, body, S0)

    return jax.jit(run, static_argnums=(1,))
