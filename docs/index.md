# Alien Biology

A framework for testing agentic AI reasoning through procedurally generated biological systems untainted by training data. Alien Biology provides a way to measure complex, agentic reasoning/learning that is:

- **REAL-WORLD** - measures performance on practical, complex, real-world-relevant agentic reasoning/learning tasks
- **UNTAINTED** - avoids confounding connections to LLM training corpora by drawing tests from an "Alien" universe
- **CONTROLLABLE** - is parametrically constructed in ways that allow fine-grained analysis of the limits of agentic reasoning

## Documentation

- **[Demos](demos/index.md)** - Interactive demonstrations with notebooks, scripts, and output
- **[User Guide](Alienbio User Guide/Alienbio User Guide.md)** - Core specs, generators, execution, and agent interface
- **[Architecture](architecture/Architecture Docs.md)** - System architecture, data model, and protocols
- **[API Reference](api/index.md)** - Auto-generated Python API docs

## Quick Start

```bash
# Clone the repository
git clone https://github.com/oblinger/alienbio.git
cd alienbio

# Install with uv
uv sync

# Run tests
just test

# Run a scenario
bio run catalog/jobs/hardcoded_test
```
