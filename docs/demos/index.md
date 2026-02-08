# Demo Gallery

Interactive demonstrations of AlienBio's core capabilities. Each demo is available in three formats:

- **Notebook** — rendered inline below (also downloadable as `.ipynb`)
- **Script** — standalone Python script (`.py`)
- **Output** — pre-generated figures (`.png`)

---

## Core Demos

### 01: Quick Start

A 3-molecule homeostatic system (A↔B↔C) converging to equilibrium.

![Trajectories](output/01_quick_start/trajectories.png){ width="45%" }
![Convergence](output/01_quick_start/convergence.png){ width="45%" }

[:material-notebook: Notebook](notebooks/01_quick_start.ipynb) ·
[:material-language-python: Script](scripts/demo_01_quick_start.py)

---

### 02: Equilibrium & Stability

Run to equilibrium and analyze stability using variance over a trailing window.

![Trajectories](output/02_equilibrium/trajectories.png){ width="45%" }
![Convergence](output/02_equilibrium/convergence.png){ width="45%" }

[:material-notebook: Notebook](notebooks/02_equilibrium.ipynb) ·
[:material-language-python: Script](scripts/demo_02_equilibrium.py)

---

### 03: Perturbation & Recovery

Spike recovery and reaction-removal drift experiments.

![Spike Recovery](output/03_perturbation/spike_recovery.png){ width="45%" }
![Drift](output/03_perturbation/drift.png){ width="45%" }

[:material-notebook: Notebook](notebooks/03_perturbation.ipynb) ·
[:material-language-python: Script](scripts/demo_03_perturbation.py)

---

### 04: Disease Investigation

Apply a perturbation, observe the diseased system, and detect symptoms.

![Diseased Trajectories](output/04_disease/diseased_trajectories.png){ width="45%" }
![Symptoms](output/04_disease/symptoms.png){ width="45%" }

[:material-notebook: Notebook](notebooks/04_disease.ipynb) ·
[:material-language-python: Script](scripts/demo_04_disease.py)

---

### 05: Multi-Compartment Organism

Generate a 3-organ organism and visualize molecule transport across compartments.

![Heatmap](output/05_organism/heatmap_mol0.png){ width="60%" }

[:material-notebook: Notebook](notebooks/05_organism.ipynb) ·
[:material-language-python: Script](scripts/demo_05_organism.py)

---

### 06: Life & Survival

Population dynamics and concentration envelopes.

![Population](output/06_features/population.png){ width="45%" }
![Envelope](output/06_features/envelope.png){ width="45%" }

[:material-notebook: Notebook](notebooks/06_features.ipynb) ·
[:material-language-python: Script](scripts/demo_06_features.py)

---

### 07: Generating & Skinning

Replace real molecule/reaction names with opaque alien terminology at 3 detail levels.

[:material-notebook: Notebook](notebooks/07_skinning.ipynb) ·
[:material-language-python: Script](scripts/demo_07_skinning.py)

---

### 08: Agent Evaluation

Oracle, random, and zero agents evaluated across difficulty levels.

![Difficulty Curves](output/08_evaluation/difficulty_curves.png){ width="45%" }
![Comparison](output/08_evaluation/comparison.png){ width="45%" }

[:material-notebook: Notebook](notebooks/08_evaluation.ipynb) ·
[:material-language-python: Script](scripts/demo_08_evaluation.py)

---

## Combo Demos

### Disease Investigation (4-Panel)

End-to-end: healthy equilibrium → disease → symptoms → diagnosis.

![Four Panel](output/combo_disease_investigation/four_panel.png){ width="80%" }

[:material-notebook: Notebook](notebooks/combo_disease_investigation.ipynb) ·
[:material-language-python: Script](scripts/combo_disease_investigation.py)

---

### Alien Exam

Agents evaluated on skinned (opaque) diagnosis tasks at multiple difficulty levels.

![Difficulty Curves](output/combo_alien_exam/difficulty_curves.png){ width="45%" }
![Leaderboard](output/combo_alien_exam/leaderboard.png){ width="45%" }

[:material-notebook: Notebook](notebooks/combo_alien_exam.ipynb) ·
[:material-language-python: Script](scripts/combo_alien_exam.py)

---

### Ecosystem

Multi-compartment organism heatmap and concentration envelope violations.

![Heatmap](output/combo_ecosystem/heatmap.png){ width="45%" }
![Envelope](output/combo_ecosystem/envelope.png){ width="45%" }

[:material-notebook: Notebook](notebooks/combo_ecosystem.ipynb) ·
[:material-language-python: Script](scripts/combo_ecosystem.py)
