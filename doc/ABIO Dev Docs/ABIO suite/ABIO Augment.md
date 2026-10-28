---
description: "`augment`: the FT04 distribution-matching augmenter — `augment` adds anonymous filler molecules, reactions and filler-only edges to a world until `graph_stats` (`n_species`, `n_reactions`, `mean_degree`) are within tolerance of targets, never touching an existing node. Not on any run path. Source: `src/alienbio/suite/augment.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Augment](ha://p/ABIO%20Augment) 
# ABIO Augment
A graph padder that grows a world's chemistry with inert filler until three summary statistics hit their targets; nothing in a run calls it.

![ABIO Augment](ABIO%20Augment.svg) 
*The fill loop* is the topic behind the priority chain (counts first, then degree; ‡ an unknown statistic name is skipped and an unreachable target only logs).

`suite/augment.py` is pure graph work over a `ChemistryImpl` ([ABIO ChemistryImpl](../ABIO%20bio/ABIO%20ChemistryImpl.md)). Existing molecules and reactions are reused by identity, and filler edges join only a filler molecule to a filler reaction, so every pre-existing node, protected or not, keeps its incidence byte for byte. Its callers are `tests/suite/test_augment.py` and the `alienbio.suite` re-export; no drafter, Expr head or pipeline step uses it. The sibling rebuilders are [ABIO Carve](ABIO%20Carve.md)'s `splice` and [ABIO Perturbations](ABIO%20Perturbations.md). The design is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## augment Interface
One alias and two functions.

| augment | |
| --- | --- |
| [TargetStats](#^targetstats) | Statistic to (target, tolerance) |
| [graph_stats](#^graph-stats) | The three statistics of a chemistry |
| [augment](#^augment) | Add filler until targets are met |

**TargetStats**` = Mapping[str, tuple[float, float]]`
    Keys from the vocabulary of `graph_stats`. ^targetstats

**graph_stats**`(chem: ChemistryImpl) -> dict[str, float]`
    `n_species`, `n_reactions`, and `mean_degree` — the mean over molecules and reactions of `len(chem.neighbors(node))` (0 for an empty chemistry). ^graph-stats

**augment**`(world: WorldImpl, target_stats: TargetStats, protected: set[NodeId], seed: Seed = Seed(0), max_iters: int = 10_000) -> WorldImpl`
    Runs the fill loop, logs a warning naming every statistic still off target, and returns `rebuild_world(world, augmented_chemistry)`; filler molecules start at 0. `protected` only keeps fresh ids from colliding with it; no existing node is touched either way. ^augment




# Augment Semantics

## The fill loop
Each iteration recomputes the statistics over a fresh `ChemistryImpl` and takes at most one action, in priority order: add a filler molecule `fill_s<k>` while `n_species` is below target; else a filler reaction `fill_r<k>` (rate 1.0, no reactants or products) while `n_reactions` is below; else, for `mean_degree` below target, make a random unused filler molecule a reactant of a random filler reaction; for `mean_degree` above target, add a node of whichever count is not pinned. No action possible ends the loop. The loop only adds, so a target below the current value is unreachable: `n_species: (1, 0)` on a two-molecule world returned it unchanged with a warning. A statistic name outside the vocabulary is skipped as met: `n_specie: (10, 0)` returned the world unchanged and silent. Neither case raises.



## What the returned world keeps
The result is [`rebuild_world`](../ABIO%20bio/ABIO%20WorldImpl.md)`(world, augmented_chemistry)` (T088): compartments, `world.flows` and `world.population_laws` are kept, as in [ABIO Perturbations](ABIO%20Perturbations.md); a filler edge rebuilds its reaction through `rebuild_reaction`, keeping `rate_law` and description. The chemistry is renamed `"augmented"`.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the silent typo and the unreachable lower target confirmed on a two-molecule world from the HEAD export, no spend. Consumer census: `tests/suite/test_augment.py` and the re-export only.
- 2026-10-28 — refreshed against `b32d46b`: the returned world comes from `rebuild_world`, so flows and population laws survive; filler edges rebuild via `rebuild_reaction`.
