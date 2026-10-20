:>> [[ABIO]] → [[ABIO Docs]] → [ABIO alienbio](ha://p/ABIO%20alienbio) 
# alienbio
**Topic**: ~~[[ABIO Topics]]~~ 
The top-level package: what `import alienbio` gives you.

## Public API

```python
from alienbio import (
    Dat, Entity, IO, mk, Pegboard,
    biotype, get_biotype,
    Atom, Molecule, Reaction, Chemistry, Simulator,
    AtomImpl, MoleculeImpl, ReactionImpl, ChemistryImpl,
    WorldStateImpl, WorldSimulatorImpl,
    COMMON_ATOMS, get_atom, config,
)
```

The first line is infrastructure, the second the `@biotype` registry, the third the Protocols, then the substrate. The instrument lives in `alienbio.suite` (`load_spec`, `run_experiment`, `DRAFTERS`, `AGENTS`, `render_report`) and the language in `alienbio.expr` (`Env`, `X`, `evaluate`, `fn`, `expander`, `guard`). The `bio` CLI fronts both — see [[ABIO Commands]].

## Entities and the anchor

Every chemistry object is an `Entity` with a local name and a parent; `mk.M("A")` / `mk.R(...)` / `mk.C(...)` build them, minting a `MockDat` anchor outside a `with mk.anchor(target):` block. `alienbio.bio.io` is the IO attachment point: `None` until one is attached, and an entity that needs it before then raises rather than inventing one.

## What is not here

The M1 scenario runtime (`bio.fetch / run / build` over `catalog/scenarios`, `Scenario`, the single-compartment `StateImpl` / `ReferenceSimulatorImpl`) was deleted in M47.7 and T056. There is one runtime — `run_experiment` over `catalog/experiments` — and one physics, the world simulator.
