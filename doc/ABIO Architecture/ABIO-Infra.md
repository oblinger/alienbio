---
description: "cross-cutting and light — Entity and the mk pegboard every bio object stands on, and the Protocols that keep the substrate's surface declared (checked by pyright since T057). Source: infra/, protocols/, 1.9k LOC."
---
:>> [ABIO](../ABIO.md) → [ABIO Architecture](ABIO%20Architecture.md) → [ABIO-Infra](ha://p/ABIO-Infra) 
# ABIO-Infra
Two mutually independent packages: `infra` is what the entities are made of, `protocols` is what they promise and, since T057, what `pyright src/` checks (`protocols/_conformance.py`; the `viz` leftover went with T056).

![[ABIO-Infra.svg|2400]] 

`Entity` is the base class of every chemistry object: a local name, a bidirectional parent/child tree, a `_top` slot that is either a DAT anchor (root) or the root entity (so `root()` and `dat()` are O(1)), a `head` registered by `__init_subclass__` for serialization round-trips, and `to_dict`/`hydrate`/`save`. The pegboard erases the anchoring boilerplate: families register a one-letter maker (`bio/makers.py` registers `M`/`R`/`C` with prefixes `mol`/`rxn`/`chem`), `mk.M("A")` resolves its anchor from a `with mk.anchor(target)` block or mints a `MockDat` outside one, so a bare unit test and a production catalog share call sites. `protocols/bio.py` states the substrate's surface as `runtime_checkable` Protocols and `bio/__init__.py` re-exports each beside its `*Impl`. `bio.io` is a declared attachment point: `entity.py` reads it lazily through `_bio_io()` and raises rather than inventing one, and no production path assigns it. The vendored `src/dvc_dat` is reached from `infra/io.py` alone; everywhere else the anchor is duck-typed.

## Modules

| MODULE | LOC | Role |
| --- | --- | --- |
| `infra/entity.py` | 478 | `Entity`, `MockDat`, the head registry, `DatLike`, `_bio_io()`. |
| `infra/io.py` | 555 | `IO`: prefix binding, ref rendering and parsing, DAT load/save;<br>the tree loader that hydrates by head. |
| `infra/mk.py` | 124 | `Pegboard`, the `mk` singleton, `mk.anchor`, `Maker`. |
| `infra/graph_ops.py` | 174 | `GraphView`, `neighbors`, `paths`, `subgraph_selection`, `match` (backtracking subgraph isomorphism) for `ChemistryImpl`. |
| `protocols/bio.py` | 415 | `Atom`, `Molecule`, `Reaction`, `Flow`, `GeneralFlow`, `Chemistry`, `CompartmentTree`, `WorldState`, `Simulator` — stated on the substrate's one state class and one tree class. |
| `protocols/_conformance.py` | 62 | Under `TYPE_CHECKING`, every `*Impl` assigned to its Protocol, so a drift in either is a red `pyright src/` (T057). |

Inbound: `infra` has 24 import sites (12 in `bio`, 9 in `suite`, none in `expr`/`commands`), led by `mk` (11), `Entity` (7), `MockDat` (6). `protocols` has three (`bio/__init__`, two `TYPE_CHECKING` uses of `WorldState` in `suite/`) plus the conformance file.

## Where the declared surface and the code could drift

Box 4 hypotheses (2026-09-10), each now answered: the `Flow` shadow, the `__all__` ghosts and the Protocol drift are fixed (T056/T057 — `bio/__init__` exports the ABC only, `_conformance.py` makes the contracts live), the pegboard and `bio.io` rows were confirmed as designed (T054 discarded them), and the viz branch went with `viz/` (T056).

Hypotheses for the latent-bug pass ([[ABIO051 - Deep Scan|T051]] box 4).

| HYPOTHESIS | Why it would be quiet | Where |
| --- | --- | --- |
| A Protocol shadowed by its implementation | `bio/__init__.py` imports `Flow` from `protocols` then rebinds it from `.flow`; `isinstance(x, bio.Flow)` tests the ABC, and `__all__` exports the winners | `bio/__init__.py` ~42, ~63, ~172 |
| `__all__` names three symbols that do not exist | `Scenario`, `Region`, `Organism`; `from alienbio.protocols import *` raises | `protocols/__init__.py` ~46 |
| Simulator drift | the Protocol's `run(state, steps, sample_every)` vs `ReferenceSimulatorImpl.run(state, steps)`; `MembraneFlow.stoichiometry` keyed by `str` in the Protocol, by `int` in `TransportFlux` | `protocols/bio.py` ~220, ~489; `bio/simulator.py` ~64; `bio/flow.py` ~482 |
| Pegboard re-registration is identity-based | `importlib.reload` of `makers.py` raises on `M`; a different prefix under the same build is accepted; the key space is flat and single-letter | `infra/mk.py` ~60 |
| `bio.io` is attached only by tests | `Entity.detach()` and ref rendering raise outside tests; `__str__` swallows it and falls back to `full_name` | `infra/entity.py` ~59, ~445 |
| A dead branch in viz | the `isinstance(snapshot, dict)` arm and its `else` are identical; `demos/_core.py` imports `agent_comparison_chart`, which does not exist | `viz/helpers.py` ~34 |
