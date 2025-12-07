# Alien Biology

A framework for testing agentic AI reasoning through procedurally generated biological systems untainted by training data.

## Overview

Alien Biology provides a way to measure complex, agentic reasoning/learning that is:

- **REAL-WORLD** - measures performance on practical, complex, real-world-relevant agentic reasoning/learning tasks
- **UNTAINTED** - avoids confounding connections to LLM training corpora by drawing tests from an "Alien" universe
- **CONTROLLABLE** - is parametrically constructed in ways that allow fine-grained analysis of the limits of agentic reasoning

## Installation

```bash
# Clone the repository
git clone https://github.com/oblinger/alienbio.git
cd alienbio

# Install with uv
uv sync

# Or install with pip
pip install -e .
```

## Development

```bash
# Run tests
just test

# Type check
just check

# Format code
just fmt

# Generate documentation diagrams
just docs
```

## Architecture

See [docs/architecture/](docs/architecture/) for detailed architecture documentation.

## License

MIT License - see [LICENSE](LICENSE) for details.
