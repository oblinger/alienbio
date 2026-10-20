---
layout: cayman
title: Alien Biology
description: A framework for testing agentic AI reasoning through procedurally generated biological systems
permalink: /gitproj/AlienBiology/
---

<style>
.ab-list { list-style: none; padding-left: 0; margin: 0.8em 0; }
.ab-list li { margin-bottom: 0.5em; }
</style>

<div style="display: flex; gap: 14px; margin: 20px 0; align-items: flex-start;">

<div style="flex: 1; min-width: 0;" markdown="1">

**Alien Biology** is a framework for measuring complex, agentic AI reasoning and learning. It constructs procedurally generated biological universes — complete with novel chemistry, multi-compartment organisms, diseases, and diagnostic challenges — that are:

<ul class="ab-list">
<li><strong>1. Untainted</strong> — Entirely synthetic "alien" biology avoids training-set contamination. Agents cannot memorize answers; they must reason from scratch.</li>
<li><strong>2. Controllable</strong> — Parametric generation enables fine-grained difficulty scaling across multiple dimensions (chemistry complexity, information disclosure, diagnostic ambiguity).</li>
<li><strong>3. Real-world structured</strong> — Multi-level systems (atoms &rarr; molecules &rarr; reactions &rarr; organisms &rarr; diseases) mirror the hierarchical complexity of real biological reasoning.</li>
<li><strong>4. Generative</strong> — Unlimited unique test instances prevent overfitting and enable smooth performance curves rather than binary pass/fail.</li>
</ul>

</div>

<div style="flex: 0 0 auto; padding-top: 6px; white-space: nowrap;">
<div style="display: flex; flex-direction: column; gap: 12px;">
<a href="https://github.com/oblinger/alienbio" style="color: #606878; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; font-size: 0.85em;"><svg width="18" height="18" viewBox="0 0 16 16" fill="none"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z" fill="#606878"/></svg> repository</a>
<a href="/gitproj/AlienBiology/AlienBiologyWhitepaper.pdf" style="color: #606878; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; font-size: 0.85em;"><svg width="16" height="19" viewBox="0 0 28 32" fill="none"><path d="M2 0C0.9 0 0 0.9 0 2v28c0 1.1 0.9 2 2 2h24c1.1 0 2-0.9 2-2V10L18 0H2z" fill="#dde1e8"/><path d="M18 0v8c0 1.1 0.9 2 2 2h8L18 0z" fill="#4a9eff" opacity="0.5"/><path d="M2 0C0.9 0 0 0.9 0 2v28c0 1.1 0.9 2 2 2h24c1.1 0 2-0.9 2-2V10L18 0H2z" stroke="#4a9eff" stroke-width="1" fill="none"/></svg> white paper</a>
<a href="https://oblinger.github.io/abio-docs/demos/index.html" style="color: #606878; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; font-size: 0.85em;"><svg width="18" height="18" viewBox="0 0 16 16" fill="none"><rect x="0.5" y="1" width="15" height="12" rx="2" fill="#dde1e8" stroke="#4a9eff" stroke-width="0.8"/><polygon points="6,4.5 6,10.5 11.5,7.5" fill="#4a9eff"/></svg> demos</a>
<a href="https://oblinger.github.io/abio-docs/" style="color: #606878; text-decoration: none; display: inline-flex; align-items: center; gap: 6px; font-size: 0.85em;"><svg width="18" height="18" viewBox="0 0 16 16" fill="none"><path d="M2 1h12a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H2a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1z" fill="#dde1e8" stroke="#4a9eff" stroke-width="0.8"/><path d="M4 4h8M4 7h8M4 10h5" stroke="#4a9eff" stroke-width="1" stroke-linecap="round"/></svg> user docs</a>
</div>
</div>

</div>

## Framework Capabilities

- **Simulation** — Mass-action kinetics with configurable reaction networks, multi-compartment organisms with transport flows, and equilibrium/stability analysis
- **Disease & Diagnosis** — Perturbation generation, symptom detection, baseline comparison, and multi-candidate diagnostic tasks
- **Skinning** — Replace all molecule/reaction names with opaque alien terminology at configurable detail levels, forcing agents to reason without training-data shortcuts
- **Agent Evaluation** — Test suite framework with difficulty scaling, oracle/random/zero baselines, and comparative scoring
- **JAX Acceleration** — JIT-compiled simulator via XLA for GPU-accelerated large-scale simulations

<br>

**Example Biological Processes** — Executable examples of terrestrial biological processes:
- [5 Interrelated Cell Respiration Processes](/gitproj/AlienBiology/CellMetabolism5.pdf) 
- [Photosynthesis](/gitproj/AlienBiology/Photosynthesis.pdf) 

<!--
## Artifacts relevant for Alien Biology construction

Below are some samples from the data artifacts being used as the statistical basis for the Alien Biology generator.

**[Example Reactions](/gitproj/AlienBiology/CellReactions.pdf)**. The Alien Biology generator is based on terrestrial Cell Biology statistics. Below is a sample list of chemical reactions central to Cell Biology. Each entry indicates the reactants, products, and catalysts for the reaction.

**Biological Processes**. Executable examples of terrestrial behavior processes. Examples of energy transport processes, anabolic and catabolic behavioral systems, used as a statistical basis for corresponding alien processes:
- [Photosynthesis](/gitproj/AlienBiology/Photosynthesis.pdf) 
- [5 Interrelated Cell Respiration Processes](/gitproj/AlienBiology/CellMetabolism5.pdf) 
-->

&copy; 2025 Dan Oblinger
