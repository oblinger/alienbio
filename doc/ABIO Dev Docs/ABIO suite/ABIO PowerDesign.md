---
description: "`power`: M46.9's statistical design fixed before the spend — `PowerDesign` (target d, alpha, power, primary contrast, multiple-comparison policy) with `required_trials_per_condition` from the normal-approximation `trials_for_effect`; `bonferroni_alpha` divides alpha. Source: `src/alienbio/suite/power.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO PowerDesign](ha://p/ABIO%20PowerDesign) 
# ABIO PowerDesign
The power arithmetic a spec commits to before any trial runs: how many trials per condition detect a stated Cohen's d at a stated alpha and power, and the design record the manifest carries.

![ABIO PowerDesign](ABIO%20PowerDesign.svg) 
*The sizing formula* is the topic behind `trials_for_effect` (‡: the per-condition n assumes two groups of single conditions; the report's primary contrast pools several).

`suite/power.py` is dependency-free (`statistics.NormalDist`). A spec's `design:` key is parsed by `spec._validate_design` ([ABIO ExperimentSpec](ABIO%20ExperimentSpec.md)), which builds a `PowerDesign`, checks that the primary contrast names a swept axis and two of its levels, and refuses a spec whose `trials_per_condition` is below `required_trials_per_condition`; the Expr form builds one through the `power(...)` constructor head ([ABIO ExprExperiment](ABIO%20ExprExperiment.md)). `to_dict` lands in `manifest.json` ([ABIO Store](ABIO%20Store.md)), and [ABIO ReportText](ABIO%20ReportText.md)'s design block reads it back with `bonferroni_alpha`. The two-sample statistics the design is sized for are [ABIO Stats](ABIO%20Stats.md). `PowerDesign`, `bonferroni_alpha`, `detectable_effect` and `trials_for_effect` are re-exported from `alienbio.suite`. The subsystem view is [ABIO-Experiment](../../ABIO%20Architecture/ABIO-Experiment.md).



## PowerDesign Interface
A frozen dataclass; `__post_init__` validates by sizing the design once.

| PowerDesign | |
| --- | --- |
| [target_effect_d](#^target-effect-d) | The Cohen's d the run must detect |
| [alpha](#^alpha) | Two-sided significance level |
| [power](#^power) | Probability of detecting `d` |
| [primary_contrast](#^primary-contrast) | The one comparison the run exists for |
| [multiple_comparison](#^multiple-comparison) | `none` or `bonferroni` |
| [required_trials_per_condition](#^required-trials-per-condition) | The sized n |
| [to_dict](#^to-dict) | The manifest's design record |
| [from_dict](#^from-dict) | Parse a `design:` mapping |

**target_effect_d**`: float`
    Positive and finite, or `ValueError`. ^target-effect-d

**alpha**`: float = 0.05`
    In `(0, 1)`. ^alpha

**power**`: float = 0.8`
    In `(0, 1)`. ^power

**primary_contrast**`: Optional[Mapping[str, Any]] = None`
    `{"axis", "low", "high"}`; a mapping missing a key raises. Here only the keys are checked; `spec._validate_design` checks the axis and levels, and nothing refuses `low == high`. ^primary-contrast

**multiple_comparison**`: str = "none"`
    One of `MULTIPLE_COMPARISON_POLICIES = {"none", "bonferroni"}`. ^multiple-comparison

**required_trials_per_condition**`: int` (property)
    `trials_for_effect(target_effect_d, alpha=alpha, power=power)`, always two-sided. ^required-trials-per-condition

**to_dict**`() -> dict[str, Any]`
    The five fields plus `required_trials_per_condition`. ^to-dict

**from_dict**`(d: Mapping[str, Any]) -> PowerDesign` (static)
    Refuses an unknown key and a missing `target_effect_d`; accepts `required_trials_per_condition` and ignores it (it is recomputed), so a manifest round-trips. ^from-dict



## power Interface
Three functions.

| power | |
| --- | --- |
| [z_quantile](#^z-quantile) | Standard-normal inverse CDF |
| [trials_for_effect](#^trials-for-effect) | n per condition for a given d |
| [bonferroni_alpha](#^bonferroni-alpha) | Alpha over the comparison count |

**z_quantile**`(p: float) -> float`
    `NormalDist().inv_cdf(p)`; `ValueError` outside `(0, 1)`. ^z-quantile

**trials_for_effect**`(d: float, *, alpha=0.05, power=0.8, two_sided=True) -> int`
    `max(2, ceil(2 · ((z_alpha + z_power) / d)²) + 1)`. `d = 0.5` → 64, `d = 1.0` → 17, `d = 10` → 2. § [The sizing formula](#the-sizing-formula). ^trials-for-effect

**bonferroni_alpha**`(alpha: float, comparisons: int) -> float`
    `alpha / comparisons`, or `alpha` when there is at most one. ^bonferroni-alpha




# Power Semantics

## The sizing formula
The normal approximation for a two-sided two-sample test on means with equal groups, rounded up and padded by one to cover the non-central-t shortfall at small n; never below 2, the least a variance needs. It sizes each group as one condition's trials. The report's primary contrast instead pools every record at the low level against every record at the high level, across the other swept dials and the idle twin ([ABIO ReportText](ABIO%20ReportText.md) § The design block), so the groups it compares are larger than the n sized here and not the population the design describes.



## Multiple comparisons
`bonferroni` divides alpha by the number of pairwise contrasts the reliability map computed (every two-level pair of axes, `mass_trial._aggregate`), not by a count of declared hypotheses. No p-value is computed anywhere, so the adjusted alpha is reported and compared with nothing.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and `spec._validate_design`; the three sized ns and the non-inverse confirmed on the HEAD export, no spend. Not determined: whether the sized n should match how the primary contrast pools (T088 § suite/power).
- 2026-10-29 — T093: `detectable_effect` retired (no caller in `src/`, `catalog/`, `demos/` or AUP; not an exact inverse of `trials_for_effect`); its test and figure node went with it.
