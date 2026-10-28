---
description: "`perturbations`: three pure `WorldImpl → WorldImpl` edits for the M27 predict/intervene archetypes — `perturb_rate` scales one reaction's rate, `remove_reaction` drops one, `spike_concentration` adds to one molecule's initial concentration; each returns a new world and refuses an unknown id. Source: `src/alienbio/suite/perturbations.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Perturbations](ha://p/ABIO%20Perturbations) 
# ABIO Perturbations
Three surgical edits to a runnable world, each returning a new world with one rate, one reaction or one initial concentration changed.

![ABIO Perturbations](ABIO%20Perturbations.svg) 
*What the rebuild keeps* is the topic behind the two rebuild paths (‡: only the chemistry's name is not carried over; flows, population laws and a reaction's `rate_law` are, T088).

`suite/perturbations.py` serves the M27 archetypes. `arch_predict.predicted_response` is its one caller in `src/`: it simulates a world and its `perturb_rate` twin and reads the target's final concentration as `up`, `down` or `same`. `pipeline.py` types a verify step as `Perturbation = Callable[[WorldImpl], WorldImpl]`, the shape these three have. The world is [ABIO WorldImpl](../ABIO%20bio/ABIO%20WorldImpl.md), the chemistry [ABIO ChemistryImpl](../ABIO%20bio/ABIO%20ChemistryImpl.md), the reaction [ABIO ReactionImpl](../ABIO%20bio/ABIO%20ReactionImpl.md). All three are re-exported from `alienbio.suite`. The subsystem view is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## perturbations Interface
Three functions; the input world is never mutated, and untouched molecules, atoms and reactions are reused by identity.

| perturbations | |
| --- | --- |
| [perturb_rate](#^perturb-rate) | Scale one reaction's rate constant |
| [remove_reaction](#^remove-reaction) | Drop one reaction |
| [spike_concentration](#^spike-concentration) | Add to one initial concentration |

**perturb_rate**`(world: WorldImpl, reaction_id: str, factor: float) -> WorldImpl`
    Rebuilds the named reaction through [`rebuild_reaction`](../ABIO%20bio/ABIO%20ReactionImpl.md) with `rate = old.rate · factor` and, when it carries a compiled `rate_law`, `rate_law = ("mul", const(factor), law)`; sides, modifiers and description are kept. The world is rebuilt over a new chemistry by [`rebuild_world`](../ABIO%20bio/ABIO%20WorldImpl.md). Raises `KeyError` listing the reactions when the id is unknown. `factor` is not checked; a negative factor gives a negative rate. ^perturb-rate

**remove_reaction**`(world: WorldImpl, reaction_id: str) -> WorldImpl`
    The same rebuild with the reaction left out; molecules stay, including any that only that reaction touched. Raises `KeyError` on an unknown id. ^remove-reaction

**spike_concentration**`(world: WorldImpl, molecule_id: str, amount: float) -> WorldImpl`
    Copies the single compartment with `concentrations[molecule_id] += amount` (from 0 when absent) and builds `rebuild_world(world, compartments=(compartment,))`: the chemistry shared, flows and population laws kept. Raises `KeyError` on an unknown molecule and `ValueError` unless the world has exactly one compartment. `amount` is not checked; a negative spike can make the initial concentration negative. ^spike-concentration




# Perturbations Semantics

## What the rebuild keeps
Both rebuild paths go through `rebuild_world` / `rebuild_reaction` (T088), which carry every part not passed:

| Kept | Lost |
| --- | --- |
| Molecules, atoms, untouched reactions (by identity) | The chemistry's name: it becomes `"perturbed"` |
| Compartments (`perturb_rate`, `remove_reaction`); `world.flows` and `world.population_laws` (all three edits) | — |
| The edited reaction's reactants, products, modifiers, `description`, `rate_law` (scaled by `factor`) | — |

A reaction with a compiled law ignores `rate`, so `perturb_rate` scales the law itself (`rate` is scaled too, for readers of the field). Before T088 the law was dropped and the reaction ran plain mass action at `rate · factor`, and flows and population laws vanished from all three edits.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the lost `rate_law` and the lost flow confirmed by `perturb_rate` on hand-built worlds from the HEAD export, no spend. Consumer census: `arch_predict.predicted_response` and the `alienbio.suite` re-exports. Not determined: whether any Expr head routes a rate-law world through `perturb_rate` (T088 § suite/perturbations).
- 2026-10-28 — refreshed against `b32d46b`: edits rebuild through `rebuild_world`/`rebuild_reaction`, so flows, population laws, description and `rate_law` (scaled) survive.
