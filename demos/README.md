# Alien Biology Demo Gallery

Pre-computed results from the full demo suite. All images below are checked into the repo — no local execution needed to browse.

To re-run all demos locally:

```bash
uv run python demos/scripts/run_all.py
```

---

## 01 — Quick Start

A 3-molecule homeostatic system (A↔B↔C) run for 500 steps, showing concentrations converging to steady state.

![Trajectories](output/01_quick_start/trajectories.png)

![Convergence](output/01_quick_start/convergence.png)

---

## 02 — Equilibrium & Stability

Stability analysis: the system reaches equilibrium as variance drops below threshold.

![Trajectories](output/02_equilibrium/trajectories.png)

![Convergence](output/02_equilibrium/convergence.png)

---

## 03 — Perturbation & Recovery

**Spike recovery**: inject a +20 concentration spike into molecule A, observe the system recovering to baseline.

![Spike Recovery](output/03_perturbation/spike_recovery.png)

**Reaction removal drift**: remove the B→C reaction, observe the system drifting to a new equilibrium.

![Drift](output/03_perturbation/drift.png)

---

## 04 — Disease Investigation

Apply a perturbation (disease) to the system. Detect which molecules have moved outside healthy ranges.

![Diseased Trajectories](output/04_disease/diseased_trajectories.png)

![Symptoms](output/04_disease/symptoms.png)

---

## 05 — Multi-Compartment Organism

A 3-organ organism generated from the homeostatic chemistry. Heatmap shows molecule 0 concentration across compartments over time.

![Compartment Heatmap](output/05_organism/heatmap_mol0.png)

---

## 06 — Life & Survival

**Population dynamics**: molecule concentrations treated as species populations.

![Population](output/06_features/population.png)

**Concentration envelope**: trajectory of molecule A with the viable range (1.0–8.0) shaded in green.

![Envelope](output/06_features/envelope.png)

---

## 07 — Generating & Skinning

Alien terminology replaces real molecule/reaction names at 3 detail levels.

**Level 1** (minimal):
```
System contains 3 substances and 4 processes.
Substances: nyx.ax, kth'el, ule'em
```

**Level 2** (moderate):
```
System contains 3 substances and 4 processes.
Substances: nyx.ax, kth'el, ule'em

Processes:
  myr.ix: nyx.ax -> kth'el
  fraum: kth'el -> nyx.ax
  myris: kth'el -> ule'em
  kthyl: ule'em -> kth'el
```

**Level 3** (full):
```
System contains 3 substances and 4 processes.
Substances: nyx.ax, kth'el, ule'em

Processes:
  myr.ix: nyx.ax -> kth'el
  fraum: kth'el -> nyx.ax
  myris: kth'el -> ule'em
  kthyl: ule'em -> kth'el

Current state:
  nyx.ax: 10.00
  kth'el: 0.00
  ule'em: 0.00
```

---

## 08 — Agent Evaluation

Oracle, random, and zero agents evaluated across difficulty levels 1–3.

![Difficulty Curves](output/08_evaluation/difficulty_curves.png)

![Agent Comparison](output/08_evaluation/comparison.png)

---

## Combo: Disease Investigation

4-panel figure: healthy equilibrium → disease applied → symptoms detected → diagnosis scored.

![Four Panel](output/combo_disease_investigation/four_panel.png)

---

## Combo: Alien Exam

Agents evaluated on skinned (opaque) diagnosis tasks across difficulty levels 1–4.

![Difficulty Curves](output/combo_alien_exam/difficulty_curves.png)

![Leaderboard](output/combo_alien_exam/leaderboard.png)

---

## Combo: Ecosystem

Multi-compartment organism heatmap and concentration envelope violations.

![Heatmap](output/combo_ecosystem/heatmap.png)

![Envelope](output/combo_ecosystem/envelope.png)

---

## Notebooks

Interactive Jupyter notebooks with inline plots and commentary. Each notebook is pre-executed — outputs render on GitHub without running anything.

| Notebook | Description |
|----------|-------------|
| [`01_quick_start.ipynb`](notebooks/01_quick_start.ipynb) | Basic trajectory + convergence |
| [`02_equilibrium.ipynb`](notebooks/02_equilibrium.ipynb) | Stability analysis |
| [`03_perturbation.ipynb`](notebooks/03_perturbation.ipynb) | Spike recovery + drift |
| [`04_disease.ipynb`](notebooks/04_disease.ipynb) | Disease + symptom detection |
| [`05_organism.ipynb`](notebooks/05_organism.ipynb) | Multi-compartment heatmap |
| [`06_features.ipynb`](notebooks/06_features.ipynb) | Population + envelope |
| [`07_skinning.ipynb`](notebooks/07_skinning.ipynb) | Alien terminology generation |
| [`08_evaluation.ipynb`](notebooks/08_evaluation.ipynb) | Difficulty curves + comparison |
| [`combo_disease_investigation.ipynb`](notebooks/combo_disease_investigation.ipynb) | 4-panel investigation |
| [`combo_alien_exam.ipynb`](notebooks/combo_alien_exam.ipynb) | Skinned exam + leaderboard |
| [`combo_ecosystem.ipynb`](notebooks/combo_ecosystem.ipynb) | Organism + envelope |

## Scripts

| Script | Description |
|--------|-------------|
| `scripts/demo_01_quick_start.py` | Basic trajectory + convergence |
| `scripts/demo_02_equilibrium.py` | Stability analysis |
| `scripts/demo_03_perturbation.py` | Spike recovery + drift |
| `scripts/demo_04_disease.py` | Disease + symptom detection |
| `scripts/demo_05_organism.py` | Multi-compartment heatmap |
| `scripts/demo_06_features.py` | Population + envelope |
| `scripts/demo_07_skinning.py` | Alien terminology generation |
| `scripts/demo_08_evaluation.py` | Difficulty curves + comparison |
| `scripts/combo_disease_investigation.py` | 4-panel investigation |
| `scripts/combo_alien_exam.py` | Skinned exam + leaderboard |
| `scripts/combo_ecosystem.py` | Organism + envelope |
| `scripts/optional_llm_agent.py` | Claude agent (needs API key) |
| `scripts/run_all.py` | Batch runner |

See [architecture docs](docs/architecture/) for deeper context on the framework.
