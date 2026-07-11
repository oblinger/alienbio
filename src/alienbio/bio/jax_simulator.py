"""JAX-accelerated world simulator (M24 vectorization & GPU scaling)."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple, TYPE_CHECKING

try:
    import jax
    import jax.numpy as jnp

    HAS_JAX = True
except ImportError:
    HAS_JAX = False

from . import jax_core

if TYPE_CHECKING:
    from .compartment_tree import CompartmentTreeImpl
    from .world_state import WorldStateImpl
    from .world_simulator import ReactionSpec
    from .flow import GeneralFlow

# A JAX-native linear transfer flow: (src_comp, dst_comp, molecule_id, rate).
NativeFlow = Tuple[int, int, int, float]


class JaxWorldSimulator:
    """GPU-accelerated world simulator using JAX/XLA.

    Same reaction/flow semantics as ``WorldSimulatorImpl`` but the hot path is
    a vectorized, jit-compilable kernel operating on a dense
    ``[compartments x molecules]`` array.

    Flows come in two forms:

    * ``flows`` -- Python ``GeneralFlow`` objects.  Applied on the host in
      ``step`` / ``run`` by round-tripping the array through a
      ``WorldStateImpl``, so *any* flow (including arbitrary ``apply_fn``)
      matches ``WorldSimulatorImpl`` exactly.  This fixes F8 (JAX used to drop
      flows silently).
    * ``native_flows`` -- ``(src, dst, molecule, rate)`` linear transfer tuples
      that compile into the jitted / vmapped device loop (``run_fast`` /
      ``run_batch``), so flows are not left in Python on the GPU path (M24.5).

    dtype defaults to float64 so trajectories match the float64 reference
    simulator (F9).  Pass ``dtype="float32"`` to trade parity for GPU speed.

    Requires JAX.  Raises ImportError if not available.
    """

    def __init__(
        self,
        tree: "CompartmentTreeImpl",
        reactions: List["ReactionSpec"],
        num_molecules: int,
        dt: float = 1.0,
        flows: Optional[List["GeneralFlow"]] = None,
        native_flows: Optional[Sequence[NativeFlow]] = None,
        dtype: str = "float64",
    ) -> None:
        if not HAS_JAX:
            raise ImportError("JAX is required: pip install jax jaxlib")

        self._tree = tree
        self._reactions = reactions
        self._num_molecules = num_molecules
        self._dt = dt
        self._num_compartments = tree.num_compartments
        self._flows = list(flows) if flows else []
        self._native_flows = list(native_flows) if native_flows else []

        if dtype not in ("float64", "float32"):
            raise ValueError(f"dtype must be 'float64' or 'float32', got {dtype!r}")
        self._dtype_name = dtype
        if dtype == "float64":
            jax_core.enable_x64()
            self._dtype = jnp.float64
        else:
            self._dtype = jnp.float32

        # Padded reaction tensors (M24.1) computed once.
        self._r_stoich, self._p_stoich, self._k, self._comp_mask = (
            jax_core.build_reaction_tensors(
                reactions, num_molecules, self._num_compartments, self._dtype
            )
        )

        # Pure device kernels.
        self._step_fn = jax_core.make_step_fn(
            self._r_stoich,
            self._p_stoich,
            self._k,
            self._comp_mask,
            self._dt,
            self._native_flows,
        )
        self._jit_step_fn = jax.jit(self._step_fn)
        self._run_fn = jax_core.make_run_fn(self._step_fn)

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def dt(self) -> float:
        return self._dt

    @property
    def num_molecules(self) -> int:
        return self._num_molecules

    @property
    def dtype(self) -> str:
        return self._dtype_name

    @property
    def flows(self) -> List["GeneralFlow"]:
        return self._flows

    @property
    def native_flows(self) -> List[NativeFlow]:
        return self._native_flows

    # ── Array <-> state conversion ─────────────────────────────────────────────

    def _state_to_array(self, state: "WorldStateImpl") -> "jnp.ndarray":
        flat: List[float] = []
        for c in range(self._num_compartments):
            flat.extend(state.get_compartment(c))
        return jnp.array(flat, dtype=self._dtype).reshape(
            self._num_compartments, self._num_molecules
        )

    def _array_to_state(
        self, arr: "jnp.ndarray", state: "WorldStateImpl"
    ) -> "WorldStateImpl":
        new_state = state.copy()
        values = arr.tolist()
        for c in range(self._num_compartments):
            new_state.set_compartment(c, values[c])
        return new_state

    # ── Host step (exact parity, supports arbitrary Python flows) ──────────────

    def step(self, state: "WorldStateImpl") -> "WorldStateImpl":
        """Advance one time step (reactions on device, flows on host).

        Reactions run through the jitted vectorized kernel; then any Python
        ``GeneralFlow`` objects are applied by round-tripping through a
        ``WorldStateImpl`` so results match ``WorldSimulatorImpl`` exactly.
        """
        arr = self._state_to_array(state)
        # Reactions + any native flows on device.
        arr = self._jit_step_fn(arr)
        new_state = self._array_to_state(arr, state)
        # Arbitrary Python flows on the host (parity path).
        for flow in self._flows:
            flow.apply(new_state, self._tree, self._dt)
        return new_state

    def run(
        self,
        state: "WorldStateImpl",
        steps: int,
        sample_every: Optional[int] = None,
    ) -> List["WorldStateImpl"]:
        """Run for multiple steps, returning a sampled timeline.

        Host-resident loop: works with arbitrary Python flows and supports
        ``sample_every``.  For the GPU-resident path (final state only), use
        ``run_fast``.
        """
        if sample_every is None:
            sample_every = 1

        history: List["WorldStateImpl"] = []
        current = state.copy()
        for i in range(steps):
            if i % sample_every == 0:
                history.append(current.copy())
            current = self.step(current)
        history.append(current.copy())
        return history

    # ── GPU-resident run (M24.3) ───────────────────────────────────────────────

    def run_fast(self, state: "WorldStateImpl", steps: int) -> "WorldStateImpl":
        """Run ``steps`` fully on-device via ``jax.lax.fori_loop`` + ``jax.jit``.

        State stays on the device for the whole trajectory (no per-step host
        transfer).  Returns only the final state.  Python ``GeneralFlow``
        objects cannot be compiled -- if any are present, raises rather than
        silently dropping them (F8 lesson).  Use ``native_flows`` instead.
        """
        if self._flows:
            raise ValueError(
                "run_fast cannot compile Python GeneralFlow objects; supply "
                "native_flows=[(src, dst, molecule, rate), ...] instead, or use "
                "run()/step() for the host path."
            )
        arr = self._state_to_array(state)
        arr = self._run_fn(arr, steps)
        return self._array_to_state(arr, state)

    # ── Batched trajectories (M24.4) ───────────────────────────────────────────

    def run_batch(
        self,
        states: Sequence["WorldStateImpl"],
        steps: int,
    ) -> List["WorldStateImpl"]:
        """Run N independent trajectories in one vectorized ``jax.vmap`` call.

        Every state must share this simulator's topology/molecule count; they
        differ only in initial concentrations.  Returns the N final states.
        Requires native (or no) flows, same as ``run_fast``.
        """
        if self._flows:
            raise ValueError(
                "run_batch cannot compile Python GeneralFlow objects; supply "
                "native_flows instead."
            )
        if not states:
            return []

        batch = jnp.stack([self._state_to_array(s) for s in states])  # [B, C, M]
        run_one = self._run_fn
        batched = jax.jit(
            lambda b: jax.vmap(lambda s: run_one(s, steps))(b)
        )(batch)
        return [
            self._array_to_state(batched[i], states[i]) for i in range(len(states))
        ]
