 [[ABIO docs]] → [[Alienbio User Guide]]

# Execution Guide

**Contents**
- [[#New Execution Model]]
- [[#CLI Commands]]
- [[#Python API]]
- [[#Experiments]]

**Command Reference:** [[ABIO Commands|Commands]]

---

## New Execution Model

The execution pipeline: <span style="white-space: nowrap">DAT Spec + Bio → <b>.build()</b> → DAT Folder → <b>.run()</b> → Results</span>

**Build** uses the DAT spec as a template to create a new folder, then calls the Bio generators to populate it with biological content.

**Run** executes the commands listed in the spec, operating on the newly created DAT folder.

---

### Example Experiment

**[[DAT|DAT Spec]]** — Defines the folder structure for the experiment.
- `build:` — what content to generate
- `run:` — actions to perform
#### `scenarios/baseline.yaml`
```yaml
scenarios.baseline:
  path: data/scenarios/baseline_{seed}/

  build:
    index.yaml: generators.baseline

  run:
    - run . --agent claude
    - report .
```

<br>

**[[ABIO Scenario|Scenario Generator]]** — Bio content that produces the biological scenario (species, interactions, rules).
#### `generators/baseline.yaml`
```yaml
generators.baseline:
  template: !include templates/mutualism.yaml
  species_count: !ev "random.randint(3, 6)"
  interactions: !ev "generate_interactions(species_count)"
```

<br>

**[[#Experiments|Experiment Spec]]** — Defines what to iterate over: which scenarios, which agents, how many seeds.
- `axes:` — dimensions to iterate or sample over
- `post_actions:` — commands to run after the experiment
#### `experiments/mutualism.yaml`
```yaml
experiments.mutualism:
  path: data/experiments/mutualism_{date}_{seq}/

  axes:
    scenarios: [scenarios.baseline, scenarios.competition]
    agents: [claude, gpt-4, random]
    seeds: 10
    name: "{scenario}_{agent}_s{seed}"    # naming pattern for child DATs
  mode: iterate                            # or: sample

  post_actions:                            # executed after experiment completes
    - report summary
    - report comparison
```

Experiments are just specs—run them with `bio run experiments.mutualism`.

---

### Step by Step

**`bio build scenarios.baseline --seed 42`**

1. Load `scenarios/baseline.yaml` (the DAT spec)
2. Create folder `data/scenarios/baseline_42/` using path template
3. For each entry in `build:`:
   - Look up `generators.baseline` (the Bio generator)
   - Call Bio.build with seed=42 to generate content
   - Write result to `index.yaml`
4. Done — folder exists with generated content

**`bio run data/scenarios/baseline_42/`**

1. Load the spec from the DAT folder
2. Execute each command in `run:` sequentially:
   - `run . --agent claude` — run the scenario with agent
   - `report .` — generate report
3. Results written to the same folder

**Shortcut:** `bio run scenarios.baseline --seed 42` does build + run in one step.

---

### Output Structure

After build + run of an experiment, the [[DAT]] folder contains:
```
data/experiments/mutualism_2026-01-09_001/
├── _spec_.yaml                   # copy of the DAT spec used
├── scenarios/
│   ├── baseline_claude_s0/       # child DAT
│   ├── baseline_claude_s1/       # child DAT
│   ├── baseline_gpt-4_s0/        # child DAT
│   └── ...
├── results.yaml
└── report.md
```

### Escape Hatch

For non-bio commands, prefix with `shell:`:
```yaml
run:
  - run . --agent claude        # runs the experiment with the Claude agent
  - shell: python analysis.py   # shell command runs in the DAT folder
  - report .
```

---

## CLI Commands

See [[ABIO Commands|Commands]] for full reference. Key commands:

```bash
# Build only (creates DAT folder, prints path)
bio build scenarios.baseline --seed 42
# → Created: data/scenarios/baseline_s42/

# Run existing DAT (see [[ABIO Run|bio run]])
bio run data/scenarios/baseline_s42/         # run previously built scenario

# Build + run in one step (dots = recipe, slashes = DAT)
bio run scenarios.baseline --seed 42         # builds, then runs
bio run scenarios.baseline --agent claude    # specify agent

# Experiments (see Experiments section)
bio run experiments.mutualism                # build + run full experiment

# Reports (see [[ABIO Report|bio report]])
bio report data/experiments/mutualism_2026-01-09/

# Agent management (see [[ABIO Agent|bio agent]])
bio agent add claude --api anthropic --model claude-opus-4
bio agent list
bio agent test claude
bio agent remove claude
```

---

## Python API

```python
from alienbio import Bio

# Build only - returns DAT path
dat_path = Bio.build("scenarios.baseline", seed=42)
# → "data/scenarios/baseline_s42/"

# Run existing DAT
result = Bio.run(dat_path, agent="claude")

# Build + run in one step (dotted name = recipe)
result = Bio.run("scenarios.baseline", agent="claude", seed=42)

# Result access
result.score                    # canonical score
result.scores                   # all scoring metrics
result.success                  # pass/fail
result.timeline                 # state at each step
result.dat_path                 # path to DAT folder
```

**Programmatic iteration:**
```python
for seed in range(10):
    result = Bio.run("scenarios.baseline", agent="claude", seed=seed)
    print(f"seed {seed}: {result.score:.2f} at {result.dat_path}")
```

---

## Experiments

Experiments run scenarios across multiple agents and seeds, then generate reports.

Experiment pipeline: <span style="white-space: nowrap">Experiment (YAML) → <b>.build()</b> → Experiment (DAT) containing Scenario DATs → <b>.run()</b> → Results + Reports</span>

```yaml
experiment.mutualism:
  iterate:
    scenarios: [mutualism.hidden, mutualism.competition]
    agents: [claude, gpt-4, random]
    seeds: 10
    hyperparameters:
      temperature: [0.0, 0.5, 1.0]

  post:
    - report: summary
    - report: comparison
```

```bash
bio run experiments.mutualism
# → Created: data/experiments/mutualism_2026-01-09_001/
# → Running 180 scenarios (2 × 3 × 10 × 3)
# → Results + reports written to DAT
```

Output structure:
```
data/experiments/mutualism_2026-01-09_001/
├── _manifest_.yaml
├── scenarios/
│   ├── hidden_claude_s0_t0.0/
│   ├── hidden_claude_s0_t0.5/
│   └── ...                        # 180 scenario DATs
├── results.yaml
└── reports/
    ├── summary.md
    └── comparison.png
```

**Python for complex sweeps:**
```yaml
experiment.mutualism_temperature:
  iterate:
    scenarios: [mutualism.hidden]
    agents: [claude]
    seeds: 5
    # temperature will be injected by Python
```

```python
import numpy as np
from alienbio import Bio

for temp in np.logspace(-2, 0, 5):    # [0.01, 0.03, 0.1, 0.3, 1.0]
    Bio.run("experiments.mutualism_temperature",
            hyperparameters={"temperature": temp})
# → Creates: data/experiments/mutualism_temperature_t0.01_.../
# → Creates: data/experiments/mutualism_temperature_t0.03_.../
# → ...
```

*Note: Automatic naming of nested DATs follows DAT conventions. See [[ABIO Features]] for open questions on naming.*

**Query results:**
```python
results = Bio.results.query(experiment="mutualism")
results.mean("score")                       # aggregate stats
results.compare(["claude", "gpt-4"])        # side-by-side
```

| Use case | Approach |
|----------|----------|
| Standard evaluation | Experiment spec (declarative) |
| Custom iteration | Python loop with `Bio.run()` |
| One-off testing | CLI with flags |

---

## See Also

- [[Agent Interface]] — detailed agent protocol
- [[ABIO Scenario|Scenario]] — scenario definition
- [[Core Spec]] — YAML foundations
