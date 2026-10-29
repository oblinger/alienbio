---
description: "`observation`: the `Observation` type (one `{id: value}` dict per compartment) and the pure pipeline from a ground-truth `WorldState` to what the agent sees — `full_observation`, `choose_hidden`, `project_observation`, `add_measurement_noise`, composed by `narrow_observation` under the `observability` and `observation_noise` dials. Source: `src/alienbio/suite/observation.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Observation](ha://p/ABIO%20Observation) 
# ABIO Observation
The pipeline that turns the exact world state into the agent's view each turn: read every value, hide a seeded fraction of molecule ids, multiply the rest by seeded relative noise.

![ABIO Observation](ABIO%20Observation.svg) 
*Seeds per turn* is the topic behind the two seed arrows (the hidden set is drawn once per trial, noise per turn; ‡ the noise is clamped at zero, which biases it upward).

`suite/observation.py` is called by [ABIO Runner](ABIO%20Runner.md): once for the turn-0 observation the brief is built from, then each later turn with the turn-0 seed for the hidden set and a per-turn `noise_seed`. The runner then removes the drafter's structural `setup["hidden_ids"]` with `project_observation` and, under the C4 monitor, appends the auditor block ([ABIO Monitor](ABIO%20Monitor.md)). The `Observation` type is what every agent's `act` takes ([ABIO Agent](ABIO%20Agent.md), [ABIO LLMAgent](ABIO%20LLMAgent.md)) and what [ABIO NameMap](ABIO%20NameMap.md) renames at the boundary. The state it reads is [ABIO WorldStateImpl](../ABIO%20bio/ABIO%20WorldStateImpl.md). `narrow_observation` and the four steps are re-exported from `alienbio.suite`. The subsystem view is [ABIO-Runtime](../../ABIO%20Architecture/ABIO-Runtime.md).



## observation Interface
One type alias and five functions; every random draw comes from a `Seed`'s own generator.

| observation | |
| --- | --- |
| [Observation](#^observation) | One `{id: value}` dict per compartment |
| [full_observation](#^full-observation) | Every value of a state, no loss |
| [choose_hidden](#^choose-hidden) | A seeded subset of ids to hide |
| [project_observation](#^project-observation) | Drop the hidden ids |
| [add_measurement_noise](#^add-measurement-noise) | Seeded relative Gaussian noise |
| [narrow_observation](#^narrow-observation) | The dial-driven composition |

**Observation**` = tuple[dict[str, float], ...]`
    In compartment order; a compartment with every id hidden is an empty dict, never dropped, so positions stay aligned. ^observation

**full_observation**`(state: WorldState) -> Observation`
    Reads `as_array()` into one dict per compartment keyed by `molecule_ids`. Raises `ValueError` when either id axis is `None` (a pure-int state). ^full-observation

**choose_hidden**`(ids: Sequence[str], fraction: float, seed: Seed) -> frozenset[str]`
    Hides `round(fraction · len(ids))` ids, drawn without replacement by `seed.rng()`; `0` hides none, all hides every id without a draw. Raises `ValueError` outside `[0, 1]`. Python's `round` is half-to-even: with four ids, `0.125` hides none and `0.375` hides two. ^choose-hidden

**project_observation**`(obs: Observation, hidden: Collection[str]) -> Observation`
    Removes every hidden id from every compartment; unknown ids are ignored. ^project-observation

**add_measurement_noise**`(obs: Observation, rel_sigma: float, seed: Seed) -> Observation`
    Each value becomes `v · max(0, 1 + N(0, rel_sigma))`, one draw per value in dict order across compartments. `rel_sigma = 0` is the identity. Raises `ValueError` on a negative sigma. § [Noise](#noise). ^add-measurement-noise

**narrow_observation**`(state, dials: Mapping[str, Any], seed: Seed, *, noise_seed: Optional[Seed] = None) -> Observation`
    `full_observation`, then, when `dials["observability"]` is set and below 1, hides `1 − observability` of the molecule ids with `seed.child("observability")`, then, when `dials["observation_noise"]` is truthy, adds noise with `(noise_seed or seed).child("noise")`. Other dials are ignored. An `observability` above 1 is the identity; below 0 raises from `choose_hidden`. ^narrow-observation




# Observation Semantics

## Seeds per turn
The runner passes the same `seed.child("turn/0/observe")` every turn, so the hidden set is fixed for the trial and the brief's probe list stays the legal set (M36.1: a per-turn redraw leaked the whole world over a dozen turns and made later-visible probes illegal). Noise is redrawn each turn from `seed.child(f"turn/{turn}/observe")`; turn 0 reuses the brief's observation rather than drawing again.

The hidden set is drawn over all molecule ids, including the drafter's structural `hidden_ids`, which the runner removes afterwards; with those present, the visible share is below the dial. The noise for an id depends on its position among the ids still present, so changing `observability` changes the noise on every surviving id, so a grid crossing the two dials reads their coupling as an interaction between cells (the `conditions.NON_ORTHOGONAL_PAIRS` refusal went with `ConditionSpec`, T093).



## Noise
The multiplier `max(0, 1 + N(0, σ))` keeps values non-negative at the cost of zero mean. Measured over 20 000 draws on a value of 1: σ = 0.1 reads mean 1.0002 and never 0; σ = 0.5 reads 1.0052 and 0 in 2.1 % of draws; σ = 1.0 reads 1.083 and 0 in 15.7 %. A true zero stays zero at every σ. Kept as drawn (T088 observation 1, the docstring now states the bias): `observation_noise` is a dial AUP's registrations license, and their records were taken on this draw.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and the runner's call sites (`runner.py` ~538, ~822); the noise bias and zero mass measured with `add_measurement_noise` on the HEAD export, no spend. Left out: the auditor block and the name map, on their own docs.
- 2026-10-28 — refreshed against `0377846`: the bias is now stated in the source docstring and kept as drawn; no behaviour change.
