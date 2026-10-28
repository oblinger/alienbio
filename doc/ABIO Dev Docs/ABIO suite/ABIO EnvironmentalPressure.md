---
description: "`pressure`: M32.4's environmental-pressure library — `make_pressure` resolves a named pressure (`suppress`, `amplify`, `drain`, `enrich`, `shock`) with an intensity and persistence ladder into an `EnvironmentalPressure`, whose `overlay` is the displacement `verify.simulate(pressure=…)` multiplies into every sampled state. Not on any run path. Source: `src/alienbio/suite/pressure.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO EnvironmentalPressure](ha://p/ABIO%20EnvironmentalPressure) 
# ABIO EnvironmentalPressure
A named, removable perturbation that rises while active and decays after removal, applied by `simulate` as one multiplier on every reported concentration; no drafter, dial or runner passes one.

![ABIO EnvironmentalPressure](ABIO%20EnvironmentalPressure.svg) 
*An overlay, not a force* is the topic behind the dotted path into the timeline (‡: the integration never sees the pressure; the readout is rescaled after it).

`suite/pressure.py` is unrelated to the pressure world ([ABIO PressureGen](ABIO%20PressureGen.md)), the `pressure` drafter or its `pi` dial; the shared word is the only link. Its one consumer is `verify.simulate`'s `pressure=` argument, and the only calls that pass it are `tests/suite/test_pressure.py` and the B10 capability test (`tests/capabilities/test_b_generation.py`), which `capabilities.py` lists as built. The Microcosm example's "environmental drain" is an ordinary sink reaction, not this module. `EnvironmentalPressure`, `make_pressure` and the three ladders are re-exported from `alienbio.suite`. The subsystem view is [ABIO-Generators](../../ABIO%20Architecture/ABIO-Generators.md).



## EnvironmentalPressure Interface
A frozen dataclass, built by `make_pressure`.

| EnvironmentalPressure | |
| --- | --- |
| [name](#^name) | A key of `NAMED_PRESSURES` |
| [coef](#^coef) | The per-step log-multiplier |
| [intensity](#^intensity) | Plateau displacement |
| [persistence](#^persistence) | Geometric keep-factor |
| [remove_at](#^remove-at) | Step the pressure is lifted |
| [jitter](#^jitter) | Seeded noise on the drive |
| [overlay](#^overlay) | The displacement per step |

**name**`: str`
    Opaque. ^name

**coef**`: float`
    `NAMED_PRESSURES[name]`; its sign is the direction (`drain` −0.5). ^coef

**intensity**`: float`
    At least 0; 0 is the identity. ^intensity

**persistence**`: float`
    In `[0, 1)`; higher is slower to build and slower to decay. ^persistence

**remove_at**`: int | None = None`
    Integration step at which the drive stops; `None` keeps it on; `0` never applies it. ^remove-at

**jitter**`: float = 0.0`
    While active, the drive is multiplied by `1 + jitter · U(−1, 1)` from `seed.rng()`. ^jitter

**overlay**`(steps: int, seed: Seed = Seed(0)) -> np.ndarray`
    `p` for `t = 0 … steps`: `p ← p · keep + drive · (1 − keep)`, drive `intensity` while active and 0 after. Indexed by integration step, not by sample. ^overlay



## pressure Interface
The three ladders, the type alias and the builder.

| pressure | |
| --- | --- |
| [NAMED_PRESSURES](#^named-pressures) | Name to coefficient |
| [INTENSITY_LEVELS](#^intensity-levels) | Named plateau magnitudes |
| [PERSISTENCE_LEVELS](#^persistence-levels) | Named keep-factors |
| [Level](#^level) | A named level or a number |
| [make_pressure](#^make-pressure) | Resolve names into a pressure |

**NAMED_PRESSURES**
    `suppress −1.0`, `amplify 1.0`, `drain −0.5`, `enrich 0.5`, `shock −2.0`. ^named-pressures

**INTENSITY_LEVELS**
    `none 0`, `low 0.25`, `moderate 0.5`, `high 1.0`, `severe 2.0`. ^intensity-levels

**PERSISTENCE_LEVELS**
    `transient 0.3`, `brief 0.6`, `moderate 0.8`, `lasting 0.95`, `permanent 0.99`. ^persistence-levels

**Level**` = str | float | int`
    A ladder name or a raw value. ^level

**make_pressure**`(name, intensity: Level = "moderate", persistence: Level = "moderate", remove_at=None, jitter=0.0) -> EnvironmentalPressure`
    Raises `ValueError` on an unknown name or level, a negative or non-finite intensity, a persistence outside `[0, 1)`, a negative `remove_at` or a negative `jitter`. ^make-pressure




# EnvironmentalPressure Semantics

## An overlay, not a force
`simulate` integrates the world exactly as without a pressure, then multiplies each sampled state's whole concentration array by `exp(coef · p_t)`. Every molecule in every compartment gets the same factor: on the B10 test's world, `pressed / base` was 0.806 for every non-zero pool at the first sample and 0.645 at the last. Ratios between pools never change, no reaction rate sees the pressure, and after `remove_at` the reported state returns to the baseline because the overlay decays, not because the world recovers. The module docstring says so in its "What it is not" paragraph (since `0377846`: no reaction, flow or population law sees it; no run path constructs one; B10 is proven on this readout overlay), and the B10 capability's sentence now reads "a named pressure rescales every sampled state by a graded readout overlay that decays after removal; the dynamics are untouched and no run path applies one".




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and `verify.simulate`; the uniform factor measured on the B10 test's world from the HEAD export, no spend. Consumer census: `verify.py` imports the type; `pressure=` is passed only in `tests/`. Not determined: whether B10 should be re-graded or the pressure moved into the dynamics (T088 § suite/pressure).
- 2026-10-28 — refreshed against `0377846`: docstring-only — the module and the B10 test docstring now state the overlay is a readout rescale off every run path.
