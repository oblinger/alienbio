---
description: "`reliability_grid`: the M34.4 reliability-map primitive — `aggregate_cells` bins `(condition_key, value)` pairs into one `CellStats` (n, mean, sample std) per key `two_way_interaction` returns a 2×2 design's additive-interaction contrast. Source: `src/alienbio/suite/reliability_grid.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO CellStats](ha://p/ABIO%20CellStats) 
# ABIO CellStats
The binning primitive under the reliability map: group scores by condition key into count, mean and spread, and read a 2×2 interaction off four cell means.

![ABIO CellStats](ABIO%20CellStats.svg) 
*Keys and levels* is the topic behind the two inputs (‡: keys equal under `==` but of different leaf types, `True` / `1` / `1.0`, refuse rather than merge).

`suite/reliability_grid.py` holds no notion of trials or dials. Its caller is `mass_trial._aggregate` ([ABIO MassTrialRunner](ABIO%20MassTrialRunner.md)), which drops error records, feeds `(bucket_key, objective_score)` pairs to `aggregate_cells`, wraps each `CellStats` in a `CellSummary` with a confidence interval ([ABIO Stats](ABIO%20Stats.md)), and, for every pair of two-level axes, ranks the levels and passes the marginal means to `two_way_interaction`. [ABIO Caution](ABIO%20Caution.md)'s stakes × reversibility factorial calls `two_way_interaction` the same way. Every name is re-exported from `alienbio.suite`. The subsystem view is [ABIO-Analysis](../../ABIO%20Architecture/ABIO-Analysis.md).



## CellStats Interface
A frozen dataclass: one condition cell.

| CellStats | |
| --- | --- |
| [n](#^n) | Observations in the cell |
| [mean](#^mean) | Their arithmetic mean |
| [std](#^std) | Sample standard deviation |

**n**`: int`
    At least 1; an empty cell is never built. ^n

**mean**`: float`
    `sum / n`. ^mean

**std**`: float`
    `statistics.stdev` (`n − 1`), and `0.0` when `n = 1`, so a singleton and a cell of identical scores both read 0; read `n` to tell them apart. ^std



## reliability_grid Interface
Two functions.

| reliability_grid | |
| --- | --- |
| [aggregate_cells](#^aggregate-cells) | Bin pairs by key |
| [two_way_interaction](#^two-way-interaction) | The 2×2 interaction contrast |

**aggregate_cells**`(observations: Sequence[tuple[object, float]]) -> dict[object, CellStats]`
    Groups by key in first-seen order and reduces each group; empty input gives `{}`. Raises `ValueError` ("compare equal but differ in type") on two keys equal under `==` whose leaf types differ (T088 CellStats 1). Keys must be hashable, which is why callers pass `bucket_key` rather than the raw `condition_key`. ^aggregate-cells

**two_way_interaction**`(cells: Mapping[tuple[object, object], float]) -> float`
    Sorts each factor's two levels, calls the smaller `0` and the larger `1`, and returns `m[1,1] − m[1,0] − m[0,1] + m[0,0]`; 0 means additive. Raises `ValueError` unless there are exactly two levels per factor and all four combinations. Levels must be mutually orderable, so both callers pass ranks `0`/`1` instead of raw levels. ^two-way-interaction




# CellStats Semantics

## Keys and levels
A cell is a dict key, so keys that hash and compare equal could only be one cell: `(("flag", True),)`, `(("flag", 1),)` and `(("flag", 1.0),)` once aggregated into a single `CellStats(n=3)`. `aggregate_cells` now compares each key's leaf types (nested tuples walked) against the first equal key's and refuses on a mismatch, so an axis whose levels mix booleans and numbers (`[false, 0]`, `[true, 1]`) raises instead of reporting one row where the grid ran two arms. The interaction's sign follows the sort: with levels ranked by the caller, `1` is whichever level the caller put second.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and `mass_trial._aggregate`; the `True`/`1`/`1.0` merge confirmed with `aggregate_cells` on the HEAD export, no spend. Not determined: whether any catalog axis mixes booleans and numbers (none seen in `catalog/experiments/`).
- 2026-10-28 — refreshed against `9db219f`: `aggregate_cells` refuses type-differing equal keys (`True` / `1` / `1.0`) instead of merging them into one cell.
- 2026-10-29 — T093: `cell_mean` retired (no caller in `src/`, `catalog/`, `demos/` or AUP); its tests and figure node went with it.
