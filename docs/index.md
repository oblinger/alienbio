# Alien Biology

A framework for testing agentic AI reasoning through procedurally generated biological systems untainted by training data.

## Overview

Alien Biology provides a way to measure complex, agentic reasoning/learning that is:

- **REAL-WORLD** - measures performance on practical, complex, real-world-relevant agentic reasoning/learning tasks
- **UNTAINTED** - avoids confounding connections to LLM training corpora by drawing tests from an "Alien" universe
- **CONTROLLABLE** - is parametrically constructed in ways that allow fine-grained analysis of the limits of agentic reasoning

## Documentation

### User Guide

Getting started with AlienBio: core spec format, generator specs, execution, and agent interface.

- [User Guide Overview](Alienbio User Guide/Alienbio User Guide.md)
- [Core Spec](Alienbio User Guide/Core Spec.md) - Scenario specification format
- [Generator Spec](Alienbio User Guide/Generator Spec.md) - Template-based generation
- [Execution Guide](Alienbio User Guide/Execution Guide.md) - Running experiments
- [Agent Interface](Alienbio User Guide/Agent Interface.md) - Agent API

### Architecture

System architecture, data model, protocols, and design decisions.

- [Architecture Overview](architecture/Architecture Docs.md)
- [Data Model](architecture/ABIO Data.md)
- [Protocols](architecture/ABIO Protocols.md)

### API Reference

Auto-generated Python API documentation from source code.

- [API Reference](api/index.md)

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
