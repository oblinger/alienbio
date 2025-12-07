# Execution - Running Simulations and Experiments

Running simulations and experiments: the engine that advances biological state through time and the framework for testing AI agents.

**Parent**: [[alienbio|ALIEN BIO]]

## Simulation

Execution engine for biology dynamics.

### [[state|State]]
Snapshot of all molecule concentrations at a point in time.

### [[step|Step]]
Single time advancement applying all active reactions.

### [[timeline|Timeline]]
Sequence of states with intervention hooks for perturbations.

### [[world|World]]
Complete runnable setup combining system, generators, and initial conditions.

### [[simulator|Simulator]]
Execution engine protocol. Two implementations: PythonSimulator (reference) and RustSimulator (performance).

## Interface

Agent-facing API for observations and actions.

### [[measurement|Measurement]]
Function to observe limited aspects of system state.

### [[action|Action]]
Function to perturb system state.

### [[task|Task]]
Goal specification with scoring criteria. Types: predict, diagnose, cure.

## Experimentation

Framework for LLM capability testing.

### [[experiment|Experiment]]
Single world setup with task, agent, and scoring.

### [[test|Test]]
Batch of experiments across world/agent/task variations.

### [[harness|Harness]]
Execution runner with timeout handling, logging, and result aggregation.
