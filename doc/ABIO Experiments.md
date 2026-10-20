:>> [[ABIO]] → [ABIO Experiments](ha://p/ABIO%20Experiments) 
# ABIO Experiments Specification
The specification of the experiments ABIO runs: the question each asks, the world it needs, and how its answer is graded.

| Table of Contents |  |
|---|---|
| **[[#Overall Objective]]** |  |
| **[[#Two Core Questions]]** |  |
|    [[#Q1: Provably Novel World Model Building]] |  |
|    [[#Q2: Long-Horizon Grounded Task Completion]] |  |
| **[[#H1: Representation Comprehension]]** |  |
|    [[#Test Specification]] |  |
| **[[#H2: Single-Step Dynamics Prediction]]** |  |
|    [[#Test Specification]] |  |
| **[[#H3: Control Interface Exercise]]** |  |
|    [[#Test Specification]] |  |
| **[[#H4: Goal-Directed Single Intervention]]** |  |
|    [[#Test Specification]] |  |
| **[[#H5: Hypothesis Formation from Observation]]** |  |
|    [[#Test Specification]] |  |
| **[[#Complexity Axes]]** |  |
| **[[#Evaluation Methods]]** |  |
| **[[#D1: World Size Scaling]]** |  |
| **[[#D2: Hidden Information Impact]]** |  |
| **[[#D3: Time Horizon Scaling]]** |  |
| **[[#D4: Multi-Goal Tradeoffs]]** |  |
| **[[#D5: Cross-Model Comparison]]** |  |
| **[[#Phase 1: Infrastructure (Required for all tests)]]** |  |
| **[[#Phase 2: H1-H3 (Basic Engagement)]]** |  |
| **[[#Phase 3: H4-H5 (Goal-Directed Reasoning)]]** |  |
| **[[#Phase 4: Systematic Measurement]]** |  |

**Related**: [[ABIO Roadmap]], ~~[[ABIO alienbio]]~~, ~~[[ABIO Notes#2026-01-14 ABIO Experiments roadmap]]~~ 

This document specifies the experiments that validate the Alien Biology testbed and measure LLM capabilities.

## Overall Objective

**Isolating Learning and Solving from Prior Training**

The Alien Biology testbed measures an LLM's ability to apply generalized knowledge in provably novel contexts. We distinguish between:

- **Generalized field knowledge** — Strategies and patterns learned from training (e.g., "reactions consume reactants and produce products")
- **Problem-specific knowledge** — What must be inferred when confronting a novel situation (e.g., "reaction R7 converts molecule M3 to M4")

Our tests should be insensitive to the former while measuring the latter in isolation.

## Two Core Questions

### Q1: Provably Novel World Model Building

To what degree can LLMs construct and manipulate internal representations of novel systems, versus relying on pattern interpolation from training data?

- **Verifiable ground truth** — Predictions can be checked against simulation
- **Multi-dimensional integration** — The world model must capture physical constraints, logical relationships, and novel conceptual distinctions

### Q2: Long-Horizon Grounded Task Completion

Can an LLM manage itself toward a complex objective over extended periods while interacting with a world it cannot fully see or understand?

- **Long-running tasks** — Decomposition into hundreds of sub-goals managed over time
- **Grounded interaction** — Acting through sensors and actuators, not just answering questions
- **Managing competing concerns** — Partial observability, limited understanding, resource constraints

---

# Hello World Progression

A sequence of experiments validating that the testbed functions and LLMs can meaningfully engage. Each test builds on the previous.

## H1: Representation Comprehension

**Purpose**: Verify the LLM can parse and understand the alien biology representation format.

**What it tests**:
- Can the LLM read the YAML/structured format?
- Can it extract factual information about static structure?
- Does it recognize the domain as "biology-like" without being told?

### Test Specification

**World Configuration**:
```yaml
compartments: 2-3
molecules: 3-5 per compartment
reactions: 2-3 total
flows: 1-2 between compartments
```

**Questions** (structural, no simulation needed):
1. "What molecules are in compartment X?"
2. "What are the reactants of reaction Y?"
3. "What are the products of reaction Y?"
4. "Which compartments share a membrane/flow?"
5. "How many molecules are in the entire system?"

**Evaluation**: Exact match against ground truth. Binary pass/fail per question.

**Success Criteria**: ≥80% accuracy on structural questions.

**Variants**:
- H1.1: Minimal world (2 compartments, 3 molecules, 1 reaction)
- H1.2: Small world (3 compartments, 5 molecules, 3 reactions)
- H1.3: With alien names (opaque identifiers instead of descriptive names)

---

## H2: Single-Step Dynamics Prediction

**Purpose**: Verify the LLM can reason about dynamics from indirect observations.

**What it tests**:
- Can it infer what happened from concentration changes?
- Can it predict future states based on inferred dynamics?
- Does it understand mass conservation?

### Test Specification

**World Configuration**:
```yaml
compartments: 1 (single compartment to start)
molecules: 4-6
reactions: 2-3 with different rates
initial_state: known concentrations
```

**Protocol**:
1. LLM observes concentrations at t=0
2. Simulation runs 1 step (LLM does NOT see which reactions fired)
3. LLM observes concentrations at t=1
4. Ask questions about what happened and what will happen

**Questions**:
1. "Which reactions likely fired? Why?"
2. "What do you expect concentrations to be at t=2?"
3. "If reaction X has rate k, what is your estimate of k based on the changes?"

**Evaluation**:
- Q1: Structured answer compared to ground truth reactions
- Q2: Numerical prediction within ±20% tolerance
- Q3: Rate estimate within ±50% tolerance

**Success Criteria**: Correct reaction identification AND directional predictions correct.

**Variants**:
- H2.1: Single reaction system (trivial inference)
- H2.2: Multiple reactions, one dominant
- H2.3: Multiple reactions, similar rates (harder disambiguation)
- H2.4: Multi-step (observe t=0, t=5, t=10 — predict t=15)

---

## H3: Control Interface Exercise

**Purpose**: Verify the LLM can operate the observation/action interface.

**What it tests**:
- Can it correctly invoke API/MCP tools?
- Can it follow a prescribed sequence of operations?
- Does it report observations coherently?

### Test Specification

**Instructions** (given explicitly):
```
1. Observe the current state of the world
2. Run the simulation for 10 steps
3. Observe the state again
4. Report what changed (which molecules increased/decreased)
```

**Available Tools**:
- `observe()` → returns current concentrations
- `step(n)` → advances simulation by n steps
- `report(text)` → submits final answer

**Evaluation**:
- Correct tool sequence invoked
- Report accurately describes concentration changes
- No hallucinated observations

**Success Criteria**: All tools invoked correctly AND report matches ground truth changes.

**Variants**:
- H3.1: Simple sequence (observe → step → observe → report)
- H3.2: With measurement cost (limited observations allowed)
- H3.3: With branching ("if molecule X > threshold, do A, else do B")

---

## H4: Goal-Directed Single Intervention

**Purpose**: Verify the LLM can connect goals to actions in this domain.

**What it tests**:
- Can it reason backward from desired outcome to intervention?
- Does it understand how actions affect the system?
- Can it articulate its reasoning?

### Test Specification

**World Configuration**:
```yaml
compartments: 1
molecules: 4-6 (including a "target" molecule)
reactions: 2-3
interventions_available:
  - add_molecule(name, amount, compartment)
  - remove_molecule(name, amount, compartment)
  - adjust_rate(reaction, factor)
```

**Goal Examples**:
1. "Increase the concentration of molecule X by at least 50%"
2. "Reduce the concentration of molecule Y to below threshold T"
3. "Make molecule Z the most abundant in the system"

**Protocol**:
1. Present world and goal
2. LLM chooses ONE intervention
3. Run simulation for N steps
4. Evaluate whether goal was achieved

**Evaluation**:
- Binary: Was the goal achieved?
- Partial credit: Did the metric move in the right direction?
- Reasoning quality: Did the explanation match the actual mechanism?

**Success Criteria**: Goal achieved AND reasoning correctly identifies the mechanism.

**Variants**:
- H4.1: Direct intervention (add the target molecule)
- H4.2: Indirect intervention (add a precursor that becomes the target)
- H4.3: Rate manipulation (speed up a production reaction)
- H4.4: Competing reactions (must choose which pathway to favor)

---

## H5: Hypothesis Formation from Observation

**Purpose**: Verify the LLM can observe dynamics and form hypotheses about hidden rules.

**What it tests**:
- Scientific reasoning transfer to novel domain
- Ability to design informative experiments
- Inference from limited data

### Test Specification

**World Configuration**:
```yaml
compartments: 1
molecules: 4-6
reactions: 2-3 (ONE reaction has hidden stoichiometry)
hidden_reaction:
  shown: "R? : ??? → ???"
  actual: "R7 : 2 M1 + M2 → M3"  # Ground truth, not revealed
```

**Available Actions**:
- `observe()` → current concentrations
- `step(n)` → advance simulation
- `set_concentration(molecule, amount)` → set initial conditions
- `submit_hypothesis(reaction_string)` → final answer

**Protocol**:
1. LLM sees all molecules but one reaction is "unknown"
2. LLM can run experiments (vary inputs, observe outputs)
3. Limited budget (e.g., 10 experiments max)
4. Submit final hypothesis about the hidden reaction

**Evaluation**:
- Reactants correctly identified (partial credit for subset)
- Products correctly identified (partial credit for subset)
- Stoichiometry correct (bonus)
- Rate estimate within tolerance (bonus)

**Success Criteria**: Correctly identify reactants AND products.

**Variants**:
- H5.1: Simple (1 reactant → 1 product)
- H5.2: Multiple reactants (A + B → C)
- H5.3: Multiple products (A → B + C)
- H5.4: Catalysis (A + E → B + E, enzyme not consumed)
- H5.5: With noise (measurement uncertainty)

---

# Measurement Dimensions

After the Hello World progression validates basic engagement, these dimensions allow systematic measurement of capabilities.

## Complexity Axes

| Dimension | Low | Medium | High |
|-----------|-----|--------|------|
| **World size** | 3-5 molecules | 10-20 molecules | 50+ molecules |
| **Reaction count** | 2-3 | 5-10 | 20+ |
| **Compartments** | 1 | 3-5 | 10+ |
| **Hidden information** | None | Some reactions hidden | Most hidden |
| **Observation cost** | Free | Limited budget | Expensive |
| **Time horizon** | 1-10 steps | 50-100 steps | 1000+ steps |
| **Goal complexity** | Single target | Multiple targets | Tradeoffs |

## Evaluation Methods

Prefer methods that don't require another LLM to grade:

1. **Multiple choice** — Objective, no grader needed
2. **Numerical prediction** — Within tolerance (±10%, ±20%)
3. **Binary success/failure** — Did the goal get achieved?
4. **Structured output** — Programmatically compared to ground truth
5. **Exact match** — For factual questions with unambiguous answers

---

# Difficulty Calibration Experiments

Experiments to understand how LLM performance degrades across complexity dimensions.

## D1: World Size Scaling

**Purpose**: Measure how performance degrades as the number of molecules and reactions increases.

**Protocol**:
1. Fix task type (e.g., H2 dynamics prediction or H4 goal-directed intervention)
2. Generate worlds at increasing sizes: 5, 10, 20, 50, 100 molecules
3. Run same agent across all sizes
4. Plot success rate vs. world size

**Expected Outcome**: Identify the complexity threshold where agent performance drops significantly.

## D2: Hidden Information Impact

**Purpose**: Measure how partial observability affects reasoning.

**Protocol**:
1. Fix world size and task type
2. Vary hidden information: 0%, 25%, 50%, 75% of reactions hidden
3. Run agent with same task but different visibility levels
4. Plot success rate vs. hidden fraction

**Expected Outcome**: Quantify the cost of incomplete information on task success.

## D3: Time Horizon Scaling

**Purpose**: Measure long-horizon planning capabilities.

**Protocol**:
1. Fix world complexity
2. Vary required planning horizon: 10, 50, 100, 500, 1000 steps
3. Tasks require reasoning about cumulative effects over time
4. Plot success rate vs. horizon length

**Expected Outcome**: Identify where long-horizon reasoning breaks down.

## D4: Multi-Goal Tradeoffs

**Purpose**: Measure ability to balance competing objectives.

**Protocol**:
1. Fix world complexity and horizon
2. Vary number of simultaneous goals: 1, 2, 3, 5
3. Include conflicting goals (optimizing A hurts B)
4. Score partial completion across all goals

**Expected Outcome**: Understand multi-objective optimization capabilities.

## D5: Cross-Model Comparison

**Purpose**: Compare capabilities across different LLMs.

**Protocol**:
1. Fix task battery (H1-H5 at multiple difficulty levels)
2. Run identical tests across multiple models
3. Control for cost budget (equivalent API spend per model)
4. Generate comparative performance profiles

**Expected Outcome**: Capability profiles showing relative strengths/weaknesses across models.

---

# Test Implementation Plan

## Phase 1: Infrastructure (Required for all tests)

- [ ] World generation from spec (compartments, molecules, reactions)
- [ ] Observation interface (`observe()` returns concentrations)
- [ ] Action interface (`step()`, `add_molecule()`, etc.)
- [ ] Ground truth recording for evaluation
- [ ] Test harness to run LLM through protocol

## Phase 2: H1-H3 (Basic Engagement)

- [ ] H1 test generator and evaluator
- [ ] H2 test generator and evaluator
- [ ] H3 test generator and evaluator
- [ ] Baseline runs with multiple LLMs

## Phase 3: H4-H5 (Goal-Directed Reasoning)

- [ ] H4 test generator and evaluator
- [ ] H5 test generator and evaluator
- [ ] Difficulty scaling infrastructure

## Phase 4: Systematic Measurement

- [ ] Complexity dimension generators
- [ ] Automated test battery execution
- [ ] Results aggregation and visualization

---

# Open Questions

1. **Agent interface**: MCP vs direct API vs chat-based? Need to decide before H3.

2. **Observation format**: YAML dump vs structured summary vs natural language description?

3. **Action vocabulary**: How verbose should action names be? `add_molecule` vs `inject_substance`?

4. **Alien naming**: When to use opaque names (M1, M2) vs descriptive (glucose, ATP)?

5. **Multi-turn budget**: How many API calls constitute a "fair" test?

6. **Baseline agents**: What non-LLM baselines should we include? (Random, Oracle, Scripted)
