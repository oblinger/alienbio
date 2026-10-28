---
description: "`conditions`: the M34.1 orthogonal dial sampler — `DialAxis` declares one dial's levels or quantized range, `ConditionSpec` a product space over named dials with a refused non-orthogonal pair, `sample` draws one point with a child seed per dial, `apply` pins overrides. Not on any run path. Source: `src/alienbio/suite/conditions.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO ConditionSpec](ha://p/ABIO%20ConditionSpec) 
# ABIO ConditionSpec
The older dial-composition sampler, which picks one point of a declared dial product space under a seed; nothing in a run calls it today.

![ABIO ConditionSpec](ABIO%20ConditionSpec.svg) 
*Quantization* is the topic behind the continuous axis (‡: the nearest listed edge wins, ties to the first listed, and an edge need not lie in the range).

`suite/conditions.py` predates the experiment grid. A run's conditions come from [ABIO ExperimentSpec](ABIO%20ExperimentSpec.md)'s `axes` (a full cross product, not a sample), so `ConditionSpec` is reached only from `tests/suite/test_conditions.py` and the `alienbio.suite` re-exports (`ConditionSpec`, `DialAxis`, `NON_ORTHOGONAL_PAIRS`, `apply_condition`, `condition_key_of`, `sample_condition`); [ABIO-Experiment](../../ABIO%20Architecture/ABIO-Experiment.md) lists it as "not on the run path". Its seeds and draws are `suite/dist.py`'s `Seed`, `Choice` and `Uniform`; its key is `trial.condition_key` ([ABIO TrialRecord](ABIO%20TrialRecord.md)). The dicts it returns are the `dials` shape [ABIO Runner](ABIO%20Runner.md) and [ABIO MassTrialRunner](ABIO%20MassTrialRunner.md) take.



## DialAxis Interface
A frozen dataclass: one dial's sampling range, either discrete `levels` or a continuous `[lo, hi)` snapped to `bin_edges`. Exactly one shape is set; `__post_init__` raises `ValueError` on neither, both, an empty `levels`, or a continuous axis missing `lo`, `hi` or `bin_edges`.

| DialAxis | |
| --- | --- |
| [levels](#^levels) | Discrete levels, sampled uniformly |
| [lo](#^lo) | Continuous lower bound |
| [hi](#^hi) | Continuous upper bound |
| [bin_edges](#^bin-edges) | The values a continuous draw snaps to |
| [discrete](#^discrete) | Build a discrete axis |
| [continuous](#^continuous) | Build a continuous quantized axis |

**levels**`: Optional[tuple[Any, ...]] = None`
    The discrete levels; `sample` draws one by index with `Choice`, so any value, hashable or not, is returned as given. ^levels

**lo**`: Optional[float] = None`
    The low end of the uniform draw. Not checked against `hi`. ^lo

**hi**`: Optional[float] = None`
    The high end. `lo > hi` constructs and draws on `[hi, lo)`. ^hi

**bin_edges**`: Optional[tuple[float, ...]] = None`
    The levels a continuous draw is snapped to; not required to be sorted or to lie in `[lo, hi)`. § [Quantization](#quantization). ^bin-edges

**discrete**`(*levels: Any) -> DialAxis` (static)
    `DialAxis(levels=tuple(levels))`. ^discrete

**continuous**`(lo: float, hi: float, bin_edges: Sequence[float]) -> DialAxis` (static)
    `DialAxis(lo=lo, hi=hi, bin_edges=tuple(bin_edges))`. ^continuous



## ConditionSpec Interface
A frozen dataclass: a `{dial_name: DialAxis}` product space over any subset of dials. Axis-agnostic: nothing reads a dial name except the orthogonality check.

| ConditionSpec | |
| --- | --- |
| [axes](#^axes) | One axis per dial |
| [non_orthogonal](#^non-orthogonal) | Pairs that may not both be axes |

**axes**`: Mapping[str, DialAxis]`
    The dials to draw, in iteration order. ^axes

**non_orthogonal**`: tuple[tuple[str, str], ...] = NON_ORTHOGONAL_PAIRS`
    Checked at construction: when `axes` names both members of a pair, `__post_init__` raises `ValueError`. `()` opts out. § [Orthogonality](#orthogonality). ^non-orthogonal



## conditions Interface
One constant and three functions.

| conditions | |
| --- | --- |
| [NON_ORTHOGONAL_PAIRS](#^non-orthogonal-pairs) | The declared interacting pairs |
| [sample](#^sample) | Draw one level per axis |
| [condition_key_of](#^condition-key-of) | The sorted key of a dials dict |
| [apply](#^apply) | Layer pinned overrides on a draw |

**NON_ORTHOGONAL_PAIRS**` = (("observability", "observation_noise"),)`
    Noise is applied only to the ids observability left visible, so the two dials share one seam. ^non-orthogonal-pairs

**sample**`(spec: ConditionSpec, seed: Seed) -> dict[str, Any]`
    For each axis, draws from `seed.child(dial_name)`: a discrete axis with `Choice(levels)`, a continuous one with `Uniform(lo, hi)` then `_quantize`. Only named dials appear in the result. Deterministic in `(spec, seed)`; one dial's draw does not move when another axis is added, removed or changed. ^sample

**condition_key_of**`(dials: Mapping[str, Any]) -> tuple[tuple[str, Any], ...]`
    `trial.condition_key(dials)`: the items sorted by dial name. It does not make list values hashable; that is `hashable_condition_key`'s job. ^condition-key-of

**apply**`(dials: Mapping[str, Any], overrides: Optional[Mapping[str, Any]] = None) -> dict[str, Any]`
    A copy of `dials` updated with `overrides`; the override wins on a shared key. Re-exported as `apply_condition`. ^apply




# Conditions Semantics

## Quantization
`_quantize(value, bin_edges)` returns `min(bin_edges, key=|edge − value|)`: the nearest edge, and on a tie the one listed first (the docstring says "the smallest", which holds only for sorted edges). The edges are points, not bins: `continuous(0, 1, (0.5, 1.0))` returns `0.5` for every draw below 0.75. An edge outside `[lo, hi)` is accepted and returned (`continuous(0, 1, (5.0,))` always yields `5.0`).



## Orthogonality
The pair check is the module's only cross-dial rule and lives only here. The experiment grid has no such check: an [ABIO ExperimentSpec](ABIO%20ExperimentSpec.md) that sweeps `observability` and `observation_noise` as two axes runs without a refusal.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the tie rule, the out-of-range edge and `lo > hi` confirmed by calling `_quantize`, `sample` and `DialAxis.continuous` on the HEAD export, no spend. Consumer census (`git grep` over `src/` and `tests/`): the `alienbio.suite` re-exports and `tests/suite/test_conditions.py` only. Not determined: whether the grid should adopt the pair check (four hypotheses in T088 § suite/conditions).
