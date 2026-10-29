---
description: "`dist`: the suite's sampling seam — `Seed` (an int with SHA-256 child derivation and a numpy generator), the `Dist` protocol and its five frozen distributions (`Constant`, `Uniform`, `Normal`, `LogNormal`, `Choice`), and `support_of`. Source: `src/alienbio/suite/dist.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Dist](ha://p/ABIO%20Dist) 
# ABIO Dist
The determinism root of the framework: every seed in a run is a `Seed` derived from the spec's base seed by labelled SHA-256 children, and every randomized parameter is a `Dist` sampled from one.

![ABIO Dist](ABIO%20Dist.svg) 
*Labels are the contract* is the topic behind the figure.

`suite/dist.py` is imported by about forty suite modules. The run's root is `Seed(spec.base_seed)` in `run_experiment`; trials, turns, observation and noise draws, brief filler and every generator take labelled children of it ([ABIO MassTrialRunner](ABIO%20MassTrialRunner.md), [ABIO Runner](ABIO%20Runner.md), [ABIO Observation](ABIO%20Observation.md)). The block library holds its rate holes as `Dist`s and samples them under each block's seed ([ABIO Blocks](ABIO%20Blocks.md), [ABIO Skeleton](ABIO%20Skeleton.md)); the pressure, W2, phase-1 and delta generators do the same ([ABIO PressureGen](ABIO%20PressureGen.md), [ABIO W2Gen](ABIO%20W2Gen.md)). The Expr environment seeds from it ([ABIO Env](../ABIO%20expr%20Modules/ABIO%20Env.md)). Every name is re-exported from `alienbio.suite`. The subsystem view is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## Seed Interface
A frozen dataclass around one `int`.

| Seed | |
| --- | --- |
| [value](#^value) | The integer |
| [child](#^child) | A labelled, independent sub-seed |
| [rng](#^rng) | A numpy generator on the value |

**value**`: int`
    Any int; a child's value is always in `[0, 2⁶⁴)`. ^value

**child**`(label: str) -> Seed`
    The first 8 bytes of `sha256(f"{value}:{label}")` as a big-endian int. The same label gives the same child on every machine; distinct labels give independent streams. ^child

**rng**`() -> np.random.Generator`
    `np.random.default_rng(value)`, a fresh generator per call, so two calls on one seed draw the same numbers. A negative `value` raises `ValueError` here (`Seed(-1).rng()`), though `Seed(-1).child(…)` works. ^rng



## Dist Interface
A `runtime_checkable` protocol, `sample(seed) -> T`, and five frozen implementations. Each `sample` builds its own generator from the seed, so a `Dist` draws one value per seed. Each implementation also states its `support()`, the closed interval it can draw from, so a consumer judges every seed at once.

| Dist | |
| --- | --- |
| [Constant](#^constant) | Always the value |
| [Uniform](#^uniform) | Uniform on `[lo, hi)` |
| [Normal](#^normal) | Gaussian |
| [LogNormal](#^lognormal) | `exp` of a Gaussian |
| [Choice](#^choice) | One of the options, optionally weighted |
| [support](#^support) | The interval a distribution draws from |

**Constant**`(value: T)`
    Ignores the seed. Generators read `Constant` holes back as plain numbers (W2's lag bound, pressure's `world_variance` leave explicit `Dist`s alone). ^constant

**Uniform**`(lo: float, hi: float)`
    `rng.uniform(lo, hi)`; `lo > hi` is not refused. ^uniform

**Normal**`(mean: float, std: float)`
    `rng.normal(mean, std)`; a negative `std` raises from numpy. ^normal

**LogNormal**`(mean: float, sigma: float)`
    `rng.lognormal(mean, sigma)`. ^lognormal

**Choice**`(options: tuple[T, ...], weights: Optional[tuple[float, ...]] = None)`
    Draws an index, so options of any type come back as given; weights are normalized by their sum. ^choice

**support**`() -> Optional[tuple[float, float]]`
    `Constant`: `(v, v)` for a number, else `None`. `Uniform`: `(min(lo, hi), max(lo, hi))`. `Normal`: `(-inf, inf)` whatever its parameters. `LogNormal`: `(0, inf)`. `Choice`: `(min, max)` of the options when every option is a number, else `None`. `None` means unknown. ^support



## dist Interface
The support reader.

| dist | |
| --- | --- |
| [support_of](#^support_of) | A distribution's support, or `None` |

**support_of**`(dist: Any) -> Optional[tuple[float, float]]`
    Calls `dist.support()` when it has one and returns it as two floats; `None` when the object has no `support` method or it returns `None`. The rate grammar reads it to refuse a rate constant that could draw negative on some seed ([ABIO RateLaw](ABIO%20RateLaw.md)). ^support_of




# Dist Semantics

## Labels are the contract
Reproducibility rests on every caller spelling its child labels the same way across versions: renaming `"turn/0/observe"` or a block's name changes every downstream draw, which is why the golden hashes move when a label does. Nothing in this module records which labels a run used.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the path collisions and the negative-seed refusal confirmed on the HEAD export, the importer count by `git grep`, no spend.
- 2026-10-28 — refreshed against `9db219f`: `ParamSchema` paths escape keys and spell positions `[i]`, so the key-path and key-vs-index collisions are gone.
- 2026-10-29 — refreshed against `aa0e59a`: `support()` on all five distributions and `support_of`, which the rate grammar reads to refuse a constant that can go negative.
- 2026-10-29 — T093: `ParamSchema` (and its private `_sample_tree`/`_key_segment`) retired — no caller in `src/`, `catalog/`, `demos/` or AUP; § Path seeds and its figure nodes went with it.
