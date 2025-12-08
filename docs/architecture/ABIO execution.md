# ABIO execution
**Parent**: [[alienbio]]
Simulation engine that advances biological state through time, plus the agent interface and experimentation framework.

## Runtime
The runtime environment and pegboard for all subsystems.
- **[[Context]]** - Runtime pegboard containing config, connections, and all major subsystems.

## Simulation (Rust)
Execution engine for biology dynamics.
- **[[State]]** - Snapshot of all molecule concentrations at a point in time.
- **[[Step]]** - Single time advancement applying all active reactions.
- **[[Timeline]]** - Sequence of states with intervention hooks for perturbations.
- **[[World]]** - Complete runnable setup combining system, generators, and initial conditions.
- **[[Simulator]]** - Execution engine protocol. Two implementations: PythonSimulator and RustSimulator.

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
