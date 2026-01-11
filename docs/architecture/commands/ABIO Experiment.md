 [[Architecture Docs]] → [[ABIO Commands|Commands]]

# Experiment

Experiment spec format for multi-run experiments. Run with `bio run experiments.<name>`.

---

## Running Experiments

Experiments are just specs—run them with `bio run`:

```bash
bio run experiments.mutualism
```

---

## Spec Format

```yaml
experiment.mutualism:
  scenario: !ref baseline
  path: data/experiments/mutualism_{date}_{seq}/
  name: "{agent}_s{seed}"

  axes:
    agents: [claude, gpt-4, random]
    seeds: 10
  mode: iterate

  post_actions:
    - report --show
```

---

## Fields

### `scenario:`
The scenario to run. Reference a scenario defined elsewhere in the spec.

### `path:`
Output folder for the experiment. Supports template variables:
- `{date}` — current date (YYYY-MM-DD)
- `{seq}` — sequence number if folder exists

### `name:`
Naming pattern for child DATs. Can reference any axis variable:
- `{agent}` — agent name
- `{seed}` — seed value

### `axes:`
Dimensions to iterate or sample over.

| Field | Description |
|-------|-------------|
| `agents:` | List of agents to test |
| `seeds:` | Number of random seeds (or explicit list) |

### `mode:`
How to traverse the axes.

| Mode | Description |
|------|-------------|
| `iterate` | Full cross-product of all axes (default) |
| `sample` | Random sample from the cross-product |

For `sample` mode, specify how many points:
```yaml
mode: sample
samples: 50
```

### `post_actions:`
Commands executed after the experiment completes. These run in the experiment's DAT context.

```yaml
post_actions:
  - report --show              # generate Excel and open
  - shell: python analyze.py   # run custom script
```

---

## Examples

### Full Iteration
```yaml
experiment.baseline_eval:
  scenario: !ref baseline
  path: data/experiments/baseline_{date}/
  name: "{agent}_s{seed}"

  axes:
    agents: [claude, gpt-4, gemini, random]
    seeds: 20
  mode: iterate

  post_actions:
    - report --show
```

Total runs: 4 × 20 = 80 runs

### Random Sampling
```yaml
experiment.hyperparameter_search:
  scenario: !ref baseline
  path: data/experiments/hypersearch_{date}/
  name: "{agent}_t{temperature}_p{top_p}_s{seed}"

  axes:
    agents: [claude]
    seeds: [0, 1, 2]
    temperature: [0.0, 0.25, 0.5, 0.75, 1.0]
    top_p: [0.8, 0.9, 0.95, 1.0]
  mode: sample
  samples: 30

  post_actions:
    - report --show
```

Samples 30 points from 1 × 3 × 5 × 4 = 60 possible combinations

---

## Result Structure

An experiment runs the referenced scenario across all axis combinations. Each run produces a result dictionary collected into a list.

**Running in Python:**

```python
results = bio.run("experiments/mutualism")
# returns a list of dictionaries, one per run
```

Each dictionary contains:
- **Axis values** — the agent, seed, etc. for this run
- **Scenario results** — scores, success, final_state, timeline
- **sim** — (optional) pointer to the simulation object

```python
results[0]
# {
#     "agent": "claude",
#     "seed": 0,
#     "scores": {"score": 0.72, "efficiency": 0.85},
#     "success": True,
#     "final_state": {...},
#     "timeline": [...],
#     "sim": <Simulator object>    # optional
# }
```

This list of dictionaries is:
- Returned when running an experiment in Python
- Passed to report functions in `post_actions:`
- Stored in the DAT as `results.yaml`

---

## Output Structure

```
data/experiments/mutualism_2026-01-09_001/
├── _spec_.yaml                   # copy of experiment spec
├── runs/
│   ├── claude_s0/                # child DAT
│   ├── claude_s1/                # child DAT
│   ├── gpt-4_s0/                 # child DAT
│   └── ...
├── results.yaml                  # aggregated results
└── reports/
    ├── summary.md
    └── comparison.png
```

---

## See Also

- [[Execution Guide#Experiments]] — high-level overview
- [[ABIO Run|run]] — running experiments
- [[ABIO Report|report]] — generating reports
