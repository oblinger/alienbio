# ABIO execution
**Parent**: [[ABIO Sys]]
Simulation engine that advances biological state through time, plus the agent interface and experimentation framework.

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
