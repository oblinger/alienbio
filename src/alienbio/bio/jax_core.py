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
* **Reactions are applied sequentially** (a Python loop that XLA unrolls at
  trace time).  This is deliberate: ``WorldSimulatorImpl`` applies reactions
  sequentially within a step, and each reaction sees the state left by the
  previous one.  Fusing the reaction axis into a single simultaneous tensor
  update would change the semantics to "all rates from step-start state,"
  which diverges from the reference for reactions that share molecules.
  Keeping the sequential loop preserves *exact* parity.
  TODO(H4): a reaction-axis-fused simultaneous kernel (competing-reactant
            global extent) is a documented follow-up, not implemented here.
* **C1 mass-conservation fix** is applied identically to the scalar
  reference: each reaction's extent is clamped to the tightest available
  substrate before being applied to both reactants and products.
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
    """Apply all reactions to state ``S`` [C, M], vectorized across C and M.

    Reactions are applied sequentially (per-compartment order matches
    ``WorldSimulatorImpl``).  Each reaction:

      rate[c]   = k * prod_m S[c, m] ** r_stoich[m] * dt          (mass action)
      max_ext[c]= min_m ( S[c, m] / r_stoich[m] )  over reactants (C1 clamp)
      extent[c] = clip(rate, 0, max_ext) * comp_mask[c]
      S        += extent[:, None] * (p_stoich - r_stoich)[None, :]
    """
    rn = r_stoich.shape[0]
    net = p_stoich - r_stoich  # [Rn, M]
    inf = jnp.array(jnp.inf, dtype=S.dtype)
    for i in range(rn):
        rs = r_stoich[i][None, :]  # [1, M]
        is_reactant = rs > 0
        # Mass-action rate per compartment. 0**0 == 1 in jnp, so non-reactant
        # molecules (stoich 0) contribute a factor of 1.
        powers = S ** rs  # [C, M]
        rate = k[i] * jnp.prod(powers, axis=1) * dt  # [C]
        # C1 extent clamp: limit by the tightest available substrate.
        safe_rs = jnp.where(is_reactant, rs, jnp.ones_like(rs))
        cap = jnp.where(is_reactant, S / safe_rs, inf)  # [C, M]
        max_ext = jnp.min(cap, axis=1)  # [C]
        extent = jnp.clip(rate, 0.0, max_ext) * comp_mask[i]  # [C]
        S = S + extent[:, None] * net[i][None, :]
    return S


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
