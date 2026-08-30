 [[ABIO]] 

# Alien Biology — Documentation

A framework for testing agentic AI reasoning through procedurally generated biological systems untainted by training data. Alien Biology measures complex, agentic reasoning/learning that is:

- **REAL-WORLD** — practical, complex, real-world-relevant agentic reasoning tasks.
- **UNTAINTED** — draws its tests from an "Alien" universe, avoiding confounds with LLM training corpora.
- **CONTROLLABLE** — parametrically constructed for fine-grained analysis of the limits of agentic reasoning.

## How this documentation is organized
This tree is **mirrored between the code repository (`docs/`) and the vault (`ABIO Docs/`)** — the folders and paths are identical on both sides. Hand-authored folders sync both directions; generated folders flow one way from the code.

| Folder | Contents | Sync |
|--------|----------|------|
| **[[ABIO Architecture Docs\|Architecture/]]** | System design — subsystem overviews, PRDs, spec language, per-class and per-command reference. | bidirectional |
| **[[ABIO Alienbio User Guide\|Guide/]]** | How to use the system — core specs, generators, execution, the agent interface. | bidirectional |
| **Modules/** | Auto-generated Python API reference (from docstrings). | one-way (code → vault) |
| **diagrams/** | Diagram assets (svg/dot). | one-way (code → vault) |

## Start here
- **[[ABIO Architecture Docs]]** — the architecture index: subsystems, data model, protocols, and the benchmark-generation design ([[ABIO Suite Construction]], [[ABIO PRD Docs|Scenario Generator PRD]]).
- **[[ABIO Alienbio User Guide]]** — usage tutorials: [[ABIO Expr Spec]], [[ABIO Expr Python API]].
- **[API Reference](Modules/index.md)** — auto-generated class and function docs.

## Quick start
```bash
git clone https://github.com/oblinger/alienbio.git
cd alienbio
uv sync
just test
```
