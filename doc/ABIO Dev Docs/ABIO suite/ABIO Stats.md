---
description: "`effect_size` + `stats_summary`: M34.3's closed-form statistics, one page because they are one family — single-sample `sample_mean`/`_variance`/`_std`, `standard_error`, `mean_confidence_interval` (normal z), and two-sample `mean_difference`, `cohens_d`, `welch_t`. Sources: `src/alienbio/suite/effect_size.py`, `src/alienbio/suite/stats_summary.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Stats](ha://p/ABIO%20Stats) 
# ABIO Stats
The suite's descriptive and two-sample statistics: means, variances and a confidence interval over one sample, and the mean difference, Cohen's d and Welch's t between two.

![ABIO Stats](ABIO%20Stats.svg) 
*The critical value* is the topic behind `mean_confidence_interval` (‡: every caller takes the default normal z, so the interval is narrow at the n a run has).

The two modules are documented together: both are M34.3, both are pure closed-form arithmetic with `n − 1` variances and no randomness, and their callers are the same few analysis modules. `mean_confidence_interval` gives every interval the report prints: the per-cell CIs of the reliability map ([ABIO MassTrialRunner](ABIO%20MassTrialRunner.md)), the side-product distribution ([ABIO Census](ABIO%20Census.md)) and the dose figure's error bars ([ABIO KeyFigure](ABIO%20KeyFigure.md)). `cohens_d` and `welch_t` give the map's pairwise contrasts and the primary contrast ([ABIO ReportText](ABIO%20ReportText.md)); [ABIO PowerDesign](ABIO%20PowerDesign.md) sizes runs for them. Every function is re-exported from `alienbio.suite`. The subsystem view is [ABIO-Analysis](../../ABIO%20Architecture/ABIO-Analysis.md).



## stats_summary Interface
Five functions over one `Sequence[float]`.

| stats_summary | |
| --- | --- |
| [sample_mean](#^sample-mean) | Arithmetic mean |
| [sample_variance](#^sample-variance) | Unbiased variance |
| [sample_std](#^sample-std) | Its square root |
| [standard_error](#^standard-error) | Standard deviation over √n |
| [mean_confidence_interval](#^mean-confidence-interval) | Mean ± z · SE |

**sample_mean**`(values) -> float`
    `sum / len`; `ValueError` when empty. ^sample-mean

**sample_variance**`(values) -> float`
    `Σ(x − mean)² / (n − 1)`; `ValueError` for fewer than 2 values. ^sample-variance

**sample_std**`(values) -> float`
    `sqrt(sample_variance)`. ^sample-std

**standard_error**`(values) -> float`
    `sample_std / sqrt(n)`. ^standard-error

**mean_confidence_interval**`(values, z: float = 1.959963984540054) -> tuple[float, float]`
    `(mean − z·se, mean + z·se)`. `z` is the caller's critical value and is never looked up; a negative `z` raises. Fewer than 2 values raise, so every caller guards `n ≥ 2` and substitutes `(mean, mean)`. § [The critical value](#the-critical-value). ^mean-confidence-interval



## effect_size Interface
Three functions over two samples `a`, `b`; each reads `a − b`.

| effect_size | |
| --- | --- |
| [mean_difference](#^mean-difference) | `mean(a) − mean(b)` |
| [cohens_d](#^cohens-d) | Difference over pooled SD |
| [welch_t](#^welch-t) | Unequal-variance t statistic |

**mean_difference**`(a, b) -> float`
    `ValueError` when either is empty. No caller in `src/` outside the re-export. ^mean-difference

**cohens_d**`(a, b) -> float`
    `(mean(a) − mean(b)) / sqrt(((n₁−1)s₁² + (n₂−1)s₂²) / (n₁+n₂−2))`. `ValueError` for fewer than 2 values on a side or a pooled SD of exactly 0. ^cohens-d

**welch_t**`(a, b) -> float`
    `(mean(a) − mean(b)) / sqrt(s₁²/n₁ + s₂²/n₂)`. `ValueError` for fewer than 2 values on a side or a zero denominator. A statistic only: no degrees of freedom or p-value is computed. ^welch-t




# Stats Semantics

## The critical value
The default `z = 1.96` is the large-sample normal value. No caller passes another, and the catalog's specs run 3 trials per condition. Over 20 000 normal samples the nominal 95 % interval covered the true mean 81.2 % of the time at n = 3, 89.3 % at n = 6, 92.2 % at n = 12 and 94.1 % at n = 30. Student's t quantile at `n − 1` degrees of freedom (4.30 at n = 3) is the value that gives 95 %.



## Two samples
`cohens_d` raises on zero pooled variance, so two groups of identical scores (every scripted zero, where each arm scores the same) give no effect size at all, and the callers turn the raise into an absent contrast. The pooled SD of `cohens_d` assumes equal variances while `welch_t` does not; the report prints both side by side for the same pair.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the sources at alienbio HEAD `64988be`; the CI coverage measured by Monte Carlo on the HEAD export (20 000 draws per n, seed 0), the catalog's `trials_per_condition` by `git grep`, no spend. Consumer census: `mass_trial`, `census`, `plots`, `report_text`; `mean_difference` and the three single-sample helpers other than the CI have no caller in `src/`.
