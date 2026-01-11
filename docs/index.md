# Alien Biology

A framework for testing agentic AI reasoning through procedurally generated biological systems untainted by training data.

## Overview

Alien Biology provides a way to measure complex, agentic reasoning/learning that is:

- **REAL-WORLD** - measures performance on practical, complex, real-world-relevant agentic reasoning/learning tasks
- **UNTAINTED** - avoids confounding connections to LLM training corpora by drawing tests from an "Alien" universe
- **CONTROLLABLE** - is parametrically constructed in ways that allow fine-grained analysis of the limits of agentic reasoning

## Documentation

- [Architecture](architecture/ABIO Sys.md) - System architecture and design
- [Topics](topics/Spec Language.md) - Deep dives on specific topics
- [API Reference](api/index.md) - Auto-generated Python API docs

## Quick Start

```bash
# Clone the repository
git clone https://github.com/oblinger/alienbio.git
cd alienbio

# Install with uv
uv sync

# Run tests
just test
```

## API Reference

See the [Architecture](architecture/) section for class and module documentation.
