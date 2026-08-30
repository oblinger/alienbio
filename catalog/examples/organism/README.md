# Organism — compartments, flows, spatial, energy, invariants

*A compartment tree with membrane transport and a diffusion lattice, gated by energy accounting and the boundedness check, with a predict task on a transport-limited response.*

A body as a compartment tree (organism → liver → hepatocyte → mitochondrion) whose chemistry is annotated with free energies, with glucose crossing two membranes by transport before it is metabolised and pyruvate crossing a third; a tissue patch where oxygen diffuses along a lattice; two gates over the finished world — energy accounting (every internal reaction runs downhill) and the boundedness invariant (no pool grows or collapses without bound) — as guards with `on_fail: reject`; and a `predict` task whose key is computed by re-simulating the world with one step throttled.

## Run it

    bio suite run catalog/examples/organism/organism.yaml --dry
    bio suite run catalog/examples/organism/organism.yaml

## What it covers

| Capability dimension | Where |
|---|---|
| a compartment **tree** with per-compartment volume and initial state | `body.compartments` (`!Compartment` records with `parent:`) |
| membrane transport, gradient- and first-order-driven | `body.flows` (`!Transport` records) |
| spatial diffusion | `tissue` (`!lattice`) |
| energy accounting (F018) | `metabolism` formation energies; the `energy_valid` guard |
| the boundedness gate (F019) | the `bounded` guard (`check_boundedness`) |
| a hand-built world through the constructor heads | `!Chemistry` / `!Compartment` / `!Transport` / `!World` |
| an objective computed from the physics | `task` (`!predict_q`) |
| an experiment over a world-side dial | `experiment` (`organism` drafter, `transport_rate` axis) |

Deliberately absent: every AI-safety dial (roadmap M48.9).

## Test

`tests/expr/test_organism_example.py`.
