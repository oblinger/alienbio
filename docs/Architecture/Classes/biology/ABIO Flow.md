 [[ABIO Architecture Docs]] → [[ABIO biology]] 

Transport between compartments: `TransportFlux`, applied in one rationed pass.

Rewritten 2026-10-07 (T068). This page described a `MembraneFlow` /
`GeneralFlow` hierarchy anchored to parent-child membranes, with a dozen
`MembraneFlow` examples. `MembraneFlow` was deleted in T056 — its `apply`
was a bare `pass` — and the tree relationship went with it.

## Overview

Flows move molecules between compartments; reactions transform molecules
within one. The live hierarchy is three classes in `bio/flow.py`:

- **`Flow`** — the abstract base: a flow states what it wants and is then
  applied to a state.
- **`TransportFlux`** — the one real flow (F016/S3). It moves conserved
  **amount** (not concentration) between **any two** compartments, with no
  tree relationship required, which is what lets a `SpatialLatticeBlock`
  wire an arbitrary neighbour graph. Amount-conserving regardless of the
  two compartments' volumes or multiplicities.
- **`GeneralFlow`** — a placeholder for an arbitrary state edit. It cannot
  state a demand, so it is applied sequentially after the fluxes.

## The rate law

One `driver_molecule`'s concentration drives the event rate (Q1 = C):

- `rate_law="gradient"` (the default) — Fickian:
  `rate_constant * ([X]_origin − [X]_dest)`, which drives the driver
  species toward equal concentration across the two pools. This is the
  mechanism a diffusive lattice relaxes through.
- `rate_law="first_order"` — `rate_constant * [X]_origin`: a pump-flavoured
  unidirectional law with no dependence on the destination.

**Either law's raw rate is floored at 0**: one flux is strictly
`origin -> dest`. A reversed local gradient contributes nothing from THAT
flux — wire a second, reversed `TransportFlux` for true bidirectional
equilibration (a lattice wires each neighbour pair both ways). The floor is
also what keeps a settled pair from flip-flopping sign on numerical
overshoot.

`stoichiometry` (`{molecule_id: count}`) moves several species per event, so
active co-transport needs no new law — just an extra entry, possibly with a
negative count for a counter-direction energy carrier. Every species is
rationed against the SAME shared event count, so a co-transported group
moves in lockstep, and each species' losing compartment is clamped so its
amount never goes negative.

## One rationed pass (T053)

`apply_flows(flows, new_state, frozen, tree, dt)` applies every flow
together, the way the reaction and population passes apply theirs: each
flux states its desired event count off the **frozen** start-of-step state,
the draws on each losing `(compartment, molecule)` are summed across
fluxes, every flux is scaled by the tightest `min(1, available / demand)`
over the pools it draws, and the scaled events are applied at once.

So the split no longer depends on list order — two fluxes over-drawing one
pool used to give `a=0.04 b=0.80 c=0.16` or `b=0.16 c=0.80` depending on
which came first — and no pool goes negative. With no pool over-drawn every
ratio is exactly 1.0, so a non-competing world is bit-identical to the old
sequential pass except that a flux now reads the frozen state rather than
its predecessors' writes: the same operator-splitting rule the other two
passes already follow.

Both steppers call it, and no golden world carries a flow, so the change
moved only the example worlds (measured before it landed).

## See Also

- [[ABIO Compartment]] — the compartments a flux connects
- [[ABIO CompartmentTree]] — the topology (no longer what a flux needs)
- [[ABIO WorldSimulator]] — the stepper that runs the three passes
- [[ABIO Suite Runtime]] — `TransportBlock` / `SpatialLatticeBlock`, how a
  skeleton declares flows
