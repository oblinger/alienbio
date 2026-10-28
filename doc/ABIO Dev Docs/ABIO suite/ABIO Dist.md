---
description: "`dist`: the suite's sampling seam — `Seed` (an int with SHA-256 child derivation and a numpy generator), the `Dist` protocol and its five frozen distributions (`Constant`, `Uniform`, `Normal`, `LogNormal`, `Choice`), and `ParamSchema`, which samples every `Dist` leaf of a nested tree by its path. Source: `src/alienbio/suite/dist.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Dist](ha://p/ABIO%20Dist) 
# ABIO Dist
The determinism root of the framework: every seed in a run is a `Seed` derived from the spec's base seed by labelled SHA-256 children, and every randomized parameter is a `Dist` sampled from one.

![ABIO Dist](ABIO%20Dist.svg) 
*Path seeds* is the topic behind `ParamSchema` (‡: two leaves whose paths spell the same string draw the same value).

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
A `runtime_checkable` protocol, `sample(seed) -> T`, and five frozen implementations. Each `sample` builds its own generator from the seed, so a `Dist` draws one value per seed.

| Dist | |
| --- | --- |
| [Constant](#^constant) | Always the value |
| [Uniform](#^uniform) | Uniform on `[lo, hi)` |
| [Normal](#^normal) | Gaussian |
| [LogNormal](#^lognormal) | `exp` of a Gaussian |
| [Choice](#^choice) | One of the options, optionally weighted |

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



## dist Interface
The tree sampler.

| dist | |
| --- | --- |
| [ParamSchema](#^paramschema) | A nested tree sampled by path |

**ParamSchema**`(tree: Any)` with `sample(seed) -> Any`
    Walks dicts, lists and tuples; each `Dist` leaf is sampled with `seed.child(path)`, the path being `/key` and `/index` segments joined from the root; other leaves pass through. Order-independent. No caller in `src/` outside the re-export. ^paramschema




# Dist Semantics

## Path seeds
A leaf's seed depends only on its path string, so leaves whose paths spell the same string are the same draw: `{"a/b": Uniform(0, 1), "a": {"b": Uniform(0, 1)}}` sampled both as 0.4437, and a dict key `"0"` collides with list index `0` (`{"0": U}` and `[U]` both read 0.1159). The `Dist` test is the runtime protocol, which only checks for a `sample` attribute, so any object with one (a nested `ParamSchema`, or a pandas DataFrame) is sampled rather than passed through.



## Labels are the contract
Reproducibility rests on every caller spelling its child labels the same way across versions: renaming `"turn/0/observe"` or a block's name changes every downstream draw, which is why the golden hashes move when a label does. Nothing in this module records which labels a run used.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the path collisions and the negative-seed refusal confirmed on the HEAD export, the importer count by `git grep`, no spend.
