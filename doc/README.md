 [[ABIO]] 

# Alien Biology — Documentation

A framework for testing agentic AI reasoning through procedurally generated biological systems untainted by training data. Alien Biology measures complex, agentic reasoning/learning that is:

- **REAL-WORLD** — practical, complex, real-world-relevant agentic reasoning tasks.
- **UNTAINTED** — draws its tests from an "Alien" universe, avoiding confounds with LLM training corpora.
- **CONTROLLABLE** — parametrically constructed for fine-grained analysis of the limits of agentic reasoning.

## How this documentation is organized
This tree is the repository's `doc/` folder, published by mkdocs; the design, track and dev-doc folders beside it are excluded from the site.

| Folder | Contents |
|--------|----------|
| [Architecture](ABIO%20Architecture/ABIO%20Architecture%20Docs.md) | System design — subsystem overviews, PRDs, the suite runtime and its data model. |
| [Guides](ABIO%20Guides/ABIO%20Guides.md) | How to use the system — the Expr spec language, its Python API, testing. |
| [Reference](ABIO%20Ref/ABIO%20Ref.md) | Commands, files, protocols, classes, and the auto-generated [API reference](ABIO%20Ref/ABIO%20API/ABIO%20API.md). |
| [Demos](ABIO%20Demos/ABIO%20Demo%20Gallery.md) | The M1-era demo gallery, kept as history. |

## Start here
- **[Architecture Docs](ABIO%20Architecture/ABIO%20Architecture%20Docs.md)** — the architecture index: subsystems, data model, protocols, and the benchmark-generation design ([Suite Construction](ABIO%20Architecture/ABIO%20Suite%20Construction.md), [Scenario Generator PRD](ABIO%20Architecture/ABIO%20PRD%20Docs.md)).
- **[User Guide](ABIO%20Guides/ABIO%20Alienbio%20User%20Guide.md)** — usage: [Expr Spec](ABIO%20Guides/ABIO%20Expr%20Spec.md), [Expr Python API](ABIO%20Guides/ABIO%20Expr%20Python%20API.md).
- **[API Reference](ABIO%20Ref/ABIO%20API/ABIO%20API.md)** — auto-generated class and function docs.

## Quick start
```bash
git clone https://github.com/oblinger/alienbio.git
cd alienbio
uv sync
just test
```
