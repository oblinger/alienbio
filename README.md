[Main Page](https://oblinger.github.io/gitproj/AlienBiology/) · [White Paper](https://oblinger.github.io/gitproj/AlienBiology/AlienBiologyWhitepaper.pdf)

# Alien Biology

A framework for testing agentic AI reasoning through procedurally generated biological systems untainted by training data. Alien Biology provides a way to measure complex, agentic reasoning/learning that is:

- **REAL-WORLD** - measures performance on practical, complex, real-world-relevant agentic reasoning/learning tasks
- **UNTAINTED** - avoids confounding connections to LLM training corpora by drawing tests from an "Alien" universe
- **CONTROLLABLE** - is parametrically constructed in ways that allow fine-grained analysis of the limits of agentic reasoning

## Documentation

- **[User Guide](https://oblinger.github.io/abio-docs/ABIO%20Guides/ABIO%20Alienbio%20User%20Guide.html)** - The Expr spec language, its Python API, running experiments, and testing
- **[Architecture](https://oblinger.github.io/abio-docs/ABIO%20Architecture/ABIO%20Architecture%20Docs.html)** - System architecture, data model, and protocols
- **[API Reference](https://oblinger.github.io/abio-docs/ABIO%20Ref/ABIO%20API/ABIO%20API.html)** - Auto-generated Python API docs
- **[Demos](https://oblinger.github.io/abio-docs/ABIO%20Demos/ABIO%20Demo%20Gallery.html)** - The M1-era demo gallery (rendered notebooks and figures, kept as history)

## Installation

`uv sync` installs the package, its dependencies (`dvc-dat` comes from its git repository, pinned in `pyproject.toml`) and the dev group (pytest, hypothesis, pyright, ruff, mkdocs). The `jax` extra adds the JAX simulator, the `llm` extra the Anthropic SDK for live-model runs.

```bash
git clone https://github.com/oblinger/alienbio.git
cd alienbio
uv sync
# optional extras
uv sync --extra jax --extra llm
# or with pip (>= 25.1 for --group)
pip install -e . --group dev
```

## Development

```bash
just test     # the test suite
just check    # pyright over src/
just docs     # build the docs site into site/
just report   # what the tests test, and whether they passed
```

## License

MIT License - see [LICENSE](LICENSE) for details.
