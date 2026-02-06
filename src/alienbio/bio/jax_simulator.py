"""JAX-accelerated world simulator."""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

try:
    import jax
    import jax.numpy as jnp
    HAS_JAX = True
except ImportError:
    HAS_JAX = False

if TYPE_CHECKING:
    from .compartment_tree import CompartmentTreeImpl
    from .world_state import WorldStateImpl
    from .world_simulator import ReactionSpec


class JaxWorldSimulator:
    """GPU-accelerated world simulator using JAX/XLA.

    Same API as WorldSimulatorImpl but uses jax.numpy arrays and
    @jax.jit for the step() hot path.

    Requires JAX to be installed. Raises ImportError if not available.
    """

    def __init__(
        self,
        tree: "CompartmentTreeImpl",
        reactions: List["ReactionSpec"],
        num_molecules: int,
        dt: float = 1.0,
    ) -> None:
        if not HAS_JAX:
            raise ImportError("JAX is required: pip install jax jaxlib")

        self._tree = tree
        self._reactions = reactions
        self._num_molecules = num_molecules
        self._dt = dt
        self._num_compartments = tree.num_compartments

        # Pre-compute reaction data as JAX arrays for efficient simulation
        self._reactant_indices: List[jnp.ndarray] = []
        self._reactant_stoich: List[jnp.ndarray] = []
        self._product_indices: List[jnp.ndarray] = []
        self._product_stoich: List[jnp.ndarray] = []
        self._rate_constants: List[float] = []
        self._rxn_compartments: List[Optional[List[int]]] = []

        for rxn in reactions:
            r_idx = jnp.array(list(rxn.reactants.keys()), dtype=jnp.int32)
            r_sto = jnp.array(list(rxn.reactants.values()), dtype=jnp.float32)
            p_idx = jnp.array(list(rxn.products.keys()), dtype=jnp.int32)
            p_sto = jnp.array(list(rxn.products.values()), dtype=jnp.float32)

            self._reactant_indices.append(r_idx)
            self._reactant_stoich.append(r_sto)
            self._product_indices.append(p_idx)
            self._product_stoich.append(p_sto)
            self._rate_constants.append(rxn.rate_constant)
            self._rxn_compartments.append(rxn.compartments)

    @property
    def dt(self) -> float:
        return self._dt

    @property
    def num_molecules(self) -> int:
        return self._num_molecules

    def _state_to_array(self, state: "WorldStateImpl") -> "jnp.ndarray":
        """Convert WorldStateImpl to JAX array [compartments x molecules]."""
        flat = []
        for c in range(self._num_compartments):
            flat.extend(state.get_compartment(c))
        return jnp.array(flat, dtype=jnp.float32).reshape(
            self._num_compartments, self._num_molecules
        )

    def _array_to_state(
        self, arr: "jnp.ndarray", state: "WorldStateImpl"
    ) -> "WorldStateImpl":
        """Write JAX array back into a WorldStateImpl copy."""
        new_state = state.copy()
        values = arr.tolist()
        for c in range(self._num_compartments):
            row = values[c]
            new_state.set_compartment(c, row)
        return new_state

    def step(self, state: "WorldStateImpl") -> "WorldStateImpl":
        """Advance one time step using JAX."""
        arr = self._state_to_array(state)
        arr = self._jit_step(arr)
        return self._array_to_state(arr, state)

    @property
    def _jit_step(self):
        """Lazy-create the JIT-compiled step function."""
        if not hasattr(self, "_compiled_step"):
            self._compiled_step = jax.jit(self._step_impl)
        return self._compiled_step

    def _step_impl(self, arr: "jnp.ndarray") -> "jnp.ndarray":
        """Pure-functional step for JIT compilation."""
        new_arr = arr.copy()

        for i in range(len(self._reactions)):
            r_idx = self._reactant_indices[i]
            r_sto = self._reactant_stoich[i]
            p_idx = self._product_indices[i]
            p_sto = self._product_stoich[i]
            k = self._rate_constants[i]
            comps = self._rxn_compartments[i]

            comp_range = range(self._num_compartments) if comps is None else comps

            for c in comp_range:
                # Mass-action rate
                rate = k
                for j in range(len(r_idx)):
                    rate = rate * (new_arr[c, r_idx[j]] ** r_sto[j])
                rate = rate * self._dt

                # Consume reactants
                for j in range(len(r_idx)):
                    new_arr = new_arr.at[c, r_idx[j]].set(
                        jnp.maximum(0.0, new_arr[c, r_idx[j]] - rate * r_sto[j])
                    )

                # Produce products
                for j in range(len(p_idx)):
                    new_arr = new_arr.at[c, p_idx[j]].set(
                        new_arr[c, p_idx[j]] + rate * p_sto[j]
                    )

        return new_arr

    def run(
        self,
        state: "WorldStateImpl",
        steps: int,
        sample_every: Optional[int] = None,
    ) -> List["WorldStateImpl"]:
        """Run simulation for multiple steps."""
        if sample_every is None:
            sample_every = 1

        history = []
        current = state.copy()

        for i in range(steps):
            if i % sample_every == 0:
                history.append(current.copy())
            current = self.step(current)

        history.append(current.copy())
        return history
