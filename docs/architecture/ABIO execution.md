 [[Architecture Docs]]

# ABIO execution
Simulation engine that advances biological state through time, plus the agent interface and experimentation framework.

## Bio Workflow

The core workflow for running biological experiments uses four operations:

| Operation | What it does | Returns |
|-----------|--------------|---------|
| `build` | Lookup recipe + template instantiation | DAT (with manifest) |
| `run` | Execute the DAT per its manifest | Outputs in DAT |
| `store` | Persist DAT to storage | — |
| `fetch` | Retrieve existing DAT | DAT object |

### Basic Workflow: Build → Run → Store

```python
from alienbio import Bio

# Build creates a DAT from a generator recipe
dat = Bio.build("generators/b10_mutualism", seed=42)

# Run executes simulation, analysis, etc. per the manifest
dat.run()

# Store persists the DAT (scenario, results, debug info)
Bio.store("experiments/run_42", dat)
```

### Extended Workflow: Build → Store → Fetch → Run

```python
# Build and store immediately (before running)
dat = Bio.build("generators/b10_mutualism", seed=42)
Bio.store("experiments/run_42", dat)

# Later: fetch and run
dat = Bio.fetch("experiments/run_42")
dat.run(steps=1000)
dat.run(analyze=True)  # Additional operations add to same DAT
```

### What's in a DAT

When you `build`, the DAT folder contains:
- **Expanded scenario** — molecules, reactions with resolved templates
- **Ground truth** — internal names before visibility mapping
- **Visibility mapping** — how internal names map to agent-visible names
- **Manifest** — declares what operations are valid (simulate, analyze, score)
- **Seed** — for reproducibility

When you `run`, outputs accumulate:
- **Simulation results** — timeline of states
- **Analysis reports** — scoring, statistics
- **Debug artifacts** — logs, intermediate states

## Runtime
The runtime environment and pegboard for all subsystems.
- **[[Context]]** - Runtime pegboard containing config, connections, and all major subsystems.

## Multi-Compartment Simulation
Execution engine for multi-compartment biology dynamics with reactions and membrane transport.
- **[[WorldState]]** - Dense concentration storage: `[num_compartments × num_molecules]` array. GPU-friendly.
- **[[CompartmentTree]]** - Hierarchical topology of compartments with parent-child relationships.
- **[[Flow]]** - Membrane transport between compartments (diffusion, active transport).
- **[[WorldSimulator]]** - Multi-compartment simulation engine. Applies reactions within compartments, flows across membranes.
- **[[Timeline]]** - Sequence of states with intervention hooks for perturbations.
- **[[World]]** - Complete runnable setup combining system, generators, and initial conditions.

## Legacy Single-Compartment (Rust)
Original single-compartment simulation. Use multi-compartment for new work.
- **[[State]]** - Single-compartment concentrations. See [[WorldState]] for multi-compartment.
- **[[Step]]** - Single time advancement applying all active reactions.
- **[[Simulator]]** - Single-compartment simulator. See [[WorldSimulator]] for multi-compartment.

## Interface
Agent-facing API for observations and actions.
- **[[Measurement]]** - Function to observe limited aspects of system state.
- **[[Action]]** - Function to perturb system state.
- **[[Task]]** - Goal specification with scoring criteria. Types: predict, diagnose, cure.

## Experimentation
Framework for LLM capability testing.
- **[[Experiment]]** - Single world setup with task, agent, and scoring.
- **[[Test]]** - Batch of experiments across world/agent/task variations.
- **[[TestHarness]]** - Execution runner with timeout handling, logging, and result aggregation.
