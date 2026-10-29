:>> [ABIO](../ABIO.md) → [ABIO Demos](ABIO%20Demos.md) → [ABIO Demo Gallery](ha://p/ABIO%20Demo%20Gallery) 
# Demo Gallery
The M1-era demo suite's figures and rendered notebooks, kept as history.

The notebooks and the figures below ran the M1 single-compartment runtime (`BioSystem`, `AgentInterface`, `generate_organism`), deleted in M47.7 and T056 (2026-09-10); the demo scripts went with it, and the notebooks' `_core`/`_shared` imports no longer exist, so nothing here re-runs. `demos/` holds only these notebooks (`.ipynb`, rendered here) and their pre-generated figures. The shipped runtime is `bio suite run` over `catalog/experiments/` and the runnable examples under `catalog/examples/` — see the [User Guide](../ABIO%20Guides/ABIO%20Alienbio%20User%20Guide.md).

---

## Core Demos

### 01: Quick Start

A 3-molecule homeostatic system (zynol↔brevix↔corthan) converging to equilibrium.

![Trajectories](output/01_quick_start/trajectories.png){ width="45%" }
![Convergence](output/01_quick_start/convergence.png){ width="45%" }

[:material-notebook: Notebook](notebooks/01_quick_start.ipynb) 

---

### 03: Perturbation & Recovery

Spike recovery and reaction-removal drift experiments.

![Spike Recovery](output/03_perturbation/spike_recovery.png){ width="45%" }
![Drift](output/03_perturbation/drift.png){ width="45%" }

[:material-notebook: Notebook](notebooks/03_perturbation.ipynb) 

---

### 04: Disease Investigation

Apply a perturbation, observe the diseased system, and detect symptoms.

![Diseased Trajectories](output/04_disease/diseased_trajectories.png){ width="45%" }
![Symptoms](output/04_disease/symptoms.png){ width="45%" }

[:material-notebook: Notebook](notebooks/04_disease.ipynb) 

---

### 05: Multi-Compartment Organism

Generate a 3-organ organism and visualize molecule transport across compartments.

![Heatmap](output/05_organism/heatmap_mol0.png){ width="60%" }

[:material-notebook: Notebook](notebooks/05_organism.ipynb) 

---

### 06: Life & Survival

Population dynamics and concentration envelopes.

![Population](output/06_features/population.png){ width="45%" }
![Envelope](output/06_features/envelope.png){ width="45%" }

[:material-notebook: Notebook](notebooks/06_features.ipynb) 

---

### 07: Generating & Skinning

Replace real molecule/reaction names with opaque alien terminology at 3 detail levels.

[:material-notebook: Notebook](notebooks/07_skinning.ipynb) 

---

### 08: Agent Evaluation

Oracle, random, and zero agents evaluated across difficulty levels.

![Difficulty Curves](output/08_evaluation/difficulty_curves.png){ width="45%" }
![Comparison](output/08_evaluation/comparison.png){ width="45%" }

[:material-notebook: Notebook](notebooks/08_evaluation.ipynb) 

---

## Combo Demos

### Disease Investigation (4-Panel)

End-to-end: healthy equilibrium → disease → symptoms → diagnosis.

![Four Panel](output/combo_disease_investigation/four_panel.png){ width="80%" }

[:material-notebook: Notebook](notebooks/combo_disease_investigation.ipynb) 

---

### Alien Exam

Agents evaluated on skinned (opaque) diagnosis tasks at multiple difficulty levels.

![Difficulty Curves](output/combo_alien_exam/difficulty_curves.png){ width="45%" }
![Leaderboard](output/combo_alien_exam/leaderboard.png){ width="45%" }

[:material-notebook: Notebook](notebooks/combo_alien_exam.ipynb) 

---

### Ecosystem

Multi-compartment organism heatmap and concentration envelope violations.

![Heatmap](output/combo_ecosystem/heatmap.png){ width="45%" }
![Envelope](output/combo_ecosystem/envelope.png){ width="45%" }

[:material-notebook: Notebook](notebooks/combo_ecosystem.ipynb) 
