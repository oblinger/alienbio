---
description: "`cover`: the FT02 set-covering solver — `cover` partitions items (each a `FeatureSet`) into containers whose feature union satisfies an `admissible` oracle, greedy exact-match placement then threshold-stopped best-first merges and cost-reducing moves, deterministic under a tie-break seed; `Cover` is the result. Source: `src/alienbio/suite/cover.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Cover](ha://p/ABIO%20Cover) 
# ABIO Cover
A small combinatorial solver that groups feature sets into as few admissible containers as an aggressiveness knob allows.

![ABIO Cover](ABIO%20Cover.svg) 
*The monotone merge chain* is the topic behind the merge loop (the threshold only stops one fixed sequence; ‡ features match by key).

`suite/cover.py` is domain-free: `admissible` and `cost` are opaque callables it only calls, and the predicates inside features it never calls — it matches features by key and passes the pairs to `admissible`. It has no run-path caller: `pipeline.build_suite` used to cover the archetypes' `feature_reqs` and stamp each task's container index on `TaskInstance.setup["container"]`, but no archetype declared a feature and nothing read the stamp, so both went (T091 AF6, `288bf7a`). Its one caller is the Expr `cover(features, aggressiveness, admissible)` head (the `pathway_puzzles` example's coverage plan), which builds `FeatureSet`s from a name-to-predicate mapping ([ABIO ExprExperiment](ABIO%20ExprExperiment.md)). `FeatureSet` and `Predicate` are [ABIO Types](ABIO%20Types.md)'s; the tie-break seed is [ABIO Dist](ABIO%20Dist.md)'s. `Cover`, `Feature` and `cover` are re-exported from `alienbio.suite`. The design is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## Cover Interface
A frozen dataclass: the partition.

| Cover | |
| --- | --- |
| [containers](#^containers) | Each container's feature union |
| [assignment](#^assignment) | Container index per item |

**containers**`: tuple[frozenset[Feature], ...]`
    Ordered by the smallest item index each holds, so equal inputs give byte-identical covers. ^containers

**assignment**`: tuple[int, ...]`
    `assignment[i]` is item `i`'s container. ^assignment



## cover Interface
One alias, one constant, one function.

| cover | |
| --- | --- |
| [Feature](#^feature) | A `(key, predicate)` pair |
| [_MAX_IMPROVE_STEPS](#^max-improve-steps) | Cap on improvement steps |
| [cover](#^cover) | Partition items into containers |

**Feature**` = tuple[str, Predicate]`
    The elements of `FeatureSet.features`; matched by key inside `cover`. ^feature

**_MAX_IMPROVE_STEPS**` = 10_000`
    Merges and moves together; reaching it logs a warning and returns the current cover. ^max-improve-steps

**cover**`(items: Sequence[FeatureSet], admissible=lambda fs: True, cost=lambda c: len(c.containers), seed: Seed = Seed(0), aggressiveness: float = 0.5) -> Cover`
    Places each item, in order, into an existing container with exactly its feature set (highest seed priority wins a tie), else opens one; raises `ValueError` when an item is inadmissible alone or `aggressiveness` is outside `[0, 1]`. Then merges and moves (§ [The monotone merge chain](#the-monotone-merge-chain)). Empty input gives an empty cover. ^cover




# Cover Semantics

## The monotone merge chain
Each merge step considers every admissible pair whose merge lowers `cost`, picks the highest `(Jaccard overlap, summed priority)`, and stops when that best overlap is below `1 − aggressiveness`. The pick ignores the threshold, so every aggressiveness runs a prefix of the same chain and the container count is weakly non-increasing in it: five items under a three-feature cap gave 5, 5, 4, 2, 2 containers at 0, 0.3, 0.5, 0.7, 1.0. The move phase then shifts single items between containers when cost strictly drops, never emptying one, so the count is untouched. Under the default cost (container count) a move never lowers cost, so the move phase only matters for a caller-supplied cost.



## Features are matched by key
A feature is a `(key, predicate)` tuple, but `cover` canonicalizes each key to the first predicate it sees before placing anything (T088 cover 1). Two items each requiring `"x"` with two separately built lambdas share the feature: overlap 1, one container. The later items' predicates are never consulted; a caller giving one key two meanings gets the first.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and `pipeline.build_suite`; the monotone counts and the predicate-identity split confirmed on the HEAD export, no spend. Not determined: whether the Expr head's `_callable` returns one object per named predicate (T088 § suite/cover).
- 2026-10-28 — refreshed against `9db219f`: features match by key (the first predicate stands for it), so separately built lambdas for one key now share a container.
- 2026-10-30 — refreshed for `288bf7a` (T091 AF6): `build_suite` runs no cover and stamps no container; the `!cover` head is the only caller. `FeatureSet` stays as a set of labelled features whose predicates `cover` hands to `admissible` and never calls on a world (`pathway_puzzles`' `is_short` now counts only the chain's molecules, `8f778bd`). Figure's caller and stamp boxes rewritten.
