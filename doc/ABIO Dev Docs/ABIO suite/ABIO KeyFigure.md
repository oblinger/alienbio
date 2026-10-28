---
description: "`plots`: the one key figure of an experiment run — eleven plotters, one per readout (dose, conflict, delta, degradation, monitoring, caution, blindspot, consideration, hazard, trial, cells), `PLOTTERS` in the order they are tried, `key_figure` picks the declared or first drawable readout, `write_key_figure` writes `key.png` and `key.json`. Source: `src/alienbio/suite/plots.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO KeyFigure](ha://p/ABIO%20KeyFigure) 
# ABIO KeyFigure
The figure layer of a run: one plotter per analysis family, each drawing from that family's summary, and a chooser that writes the one figure the run exists for beside `report.txt`.

![ABIO KeyFigure](ABIO%20KeyFigure.svg) 
*Choosing the readout* is the topic behind the dagger on `PLOTTERS` (its order is not the report's, so the first drawable readout is not always the experiment's).

`suite/plots.py` draws from the analysis summaries, never from timelines, so a reloaded run draws the same figure: [ABIO Dose](ABIO%20Dose.md), [ABIO Tradeoff](ABIO%20Tradeoff.md), [ABIO Delta](ABIO%20Delta.md), [ABIO Degradation](ABIO%20Degradation.md), [ABIO Faking](ABIO%20Faking.md), [ABIO Caution](ABIO%20Caution.md), and `hazard.py`'s three summaries; `trial` reads the one record, `cells` the `ReliabilityMap` itself ([ABIO MassTrialRunner](ABIO%20MassTrialRunner.md)). Callers: `run_experiment` after it writes `report.txt`, and `bio suite report` (`commands/suite_cmd.py`); `bio report` embeds the PNG. Matplotlib is imported lazily on the `Agg` backend. The module exports only `KeyFigure`, `PLOTTERS`, `key_figure` and `write_key_figure`; none is re-exported from `alienbio.suite`.



## plots Interface
The chooser, the writer, the plotter table, and eleven plotters with one shape: `(rmap: ReliabilityMap) -> Optional[KeyFigure]`, `None` when the records carry nothing for that readout.

| plots | |
| --- | --- |
| [PLOTTERS](#^plotters) | `(name, plotter)` in the order tried |
| [key_figure](#^key-figure) | The declared or first drawable readout |
| [write_key_figure](#^write-key-figure) | Write `key.png` and `key.json` |
| [plot_dose](#^plot-dose) | Side-product along `pi`, with CIs |
| [plot_conflict](#^plot-conflict) | Target attainment along the rungs |
| [plot_delta](#^plot-delta) | Match beside mismatch, gap annotated |
| [plot_degradation](#^plot-degradation) | Accuracy and exhaustion down the budget |
| [plot_monitoring](#^plot-monitoring) | Assay rate per monitoring arm |
| [plot_caution](#^plot-caution) | Info-seeking and destructive acts |
| [plot_blindspot](#^plot-blindspot) | Coverage by objective type |
| [plot_consideration](#^plot-consideration) | Surfacing by depth along the ladder |
| [plot_hazard](#^plot-hazard) | Hazard surfacing rate |
| [plot_trial](#^plot-trial) | A one-trial run's actions by turn |
| [plot_cells](#^plot-cells) | Mean score per condition, any run |

**PLOTTERS**`: tuple[tuple[str, Callable[[ReliabilityMap], Optional[KeyFigure]]], ...]`
    `dose, conflict, delta, degradation, monitoring, caution, blindspot, consideration, hazard, trial, cells`. Specific-first by design, not the report's print order; the comment above it and the module docstring say so (§ [Choosing the readout](#choosing-the-readout)). ^plotters

**key_figure**`(rmap: ReliabilityMap, readout: Optional[str] = None) -> Optional[KeyFigure]`
    With `readout` (the spec's `key_readout`): that plotter's figure, raising `ValueError` for an unknown name or when it draws nothing. Without: the first plotter in `PLOTTERS` that draws; `None` only for an empty run, since `cells` draws whenever the map has cells. ^key-figure

**write_key_figure**`(rmap: ReliabilityMap, out_dir: str | Path, readout: Optional[str] = None) -> Optional[Path]`
    `key_figure`, then `key.png` at `DPI` 130 and `key.json` (`readout`, `caption`) in `out_dir`; returns the PNG path or `None`. A declared readout that draws nothing does not raise here: `key.json` names the readout with a "nothing to draw" caption and the call returns `None`; an unknown readout name still raises `ValueError`. ^write-key-figure

**plot_dose**`(rmap) -> Optional[KeyFigure]`
    `pressure_summary`: mean side-product per `pi`, one line per condition, normal-approximation 95 % intervals (`z = 1.96`) from `byproduct_values`, narrow at three trials. ^plot-dose

**plot_conflict**`(rmap) -> Optional[KeyFigure]`
    `conflict_summary` split by `rung`: each target's mean attainment along `RUNGS`, one panel per group. ^plot-conflict

**plot_delta**`(rmap) -> Optional[KeyFigure]`
    `delta_summary` cells with `n_pairs > 0`: grouped match/mismatch bars, the gap annotated; unpaired conditions are dropped. ^plot-delta

**plot_degradation**`(rmap) -> Optional[KeyFigure]`
    `degradation_ladder`: accuracy and exhaustion per rung, the cliff rung shaded. Needs a `budget` axis. ^plot-degradation

**plot_monitoring**`(rmap) -> Optional[KeyFigure]`
    `monitoring_summary`: assay rate per arm per condition, `monitoring_divergence(...).label` above each group. A missing arm draws no bar (`NaN`), never a `0.0` bar that would read as an arm that never assayed. ^plot-monitoring

**plot_caution**`(rmap) -> Optional[KeyFigure]`
    `caution_summary` along `reversibility` if swept, else `stakes`: info-seeking and destructive acts, two panels. ^plot-caution

**plot_blindspot**`(rmap) -> Optional[KeyFigure]`
    `blindspot_summary`: coverage per objective type, one panel per agent, the blind-spot rate as a tick. ^plot-blindspot

**plot_consideration**`(rmap) -> Optional[KeyFigure]`
    `consideration_summary`: fraction surfaced per depth, along the one swept axis other than `agent`/`model` when there is exactly one, else per condition. ^plot-consideration

**plot_hazard**`(rmap) -> Optional[KeyFigure]`
    `hazard_surfacing_summary`: surfacing rate per condition, grouped by the first axis when there are two or more; mean surfacing turn in the title. ^plot-hazard

**plot_trial**`(rmap) -> Optional[KeyFigure]`
    Only when exactly one non-error record: its action kinds by turn, rejected actions as crosses, destructive ones red, targets annotated. ^plot-trial

**plot_cells**`(rmap) -> Optional[KeyFigure]`
    Any run with cells: mean objective score per condition with its CI. ^plot-cells



## KeyFigure Interface
A frozen dataclass: one run's figure.

| KeyFigure | |
| --- | --- |
| [readout](#^readout) | The `PLOTTERS` name that drew it |
| [caption](#^caption) | One-line caption |
| [figure](#^figure) | The matplotlib `Figure` |

**readout**`: str`
    Written to `key.json`. ^readout

**caption**`: str`
    Fixed per plotter (only `trial`'s carries the score and call count); written to `key.json`. ^caption

**figure**`: Figure`
    A `matplotlib.figure.Figure`, never attached to pyplot. ^figure




# KeyFigure Semantics

## Choosing the readout
`key_figure` reads the same summary functions `render_report` does, but tries them in `PLOTTERS`' order, not the report's: the oracle-gated families (dose, conflict, delta, degradation) come before the ones any swept `monitoring` or `stakes` axis feeds, so a run feeding two families draws the more specific one. The module docstring and the comment on `PLOTTERS` say so since `343d166`; `key_figure`'s own docstring still says "in report order". `report_text.py` prints hazard, consideration, blindspot, conflict, caution, monitoring, degradation, delta, dose; `PLOTTERS` tries dose, conflict, delta, degradation, monitoring, caution, blindspot, consideration, hazard. The difference matters whenever one run feeds two summaries, because several summaries have no oracle filter: `caution_summary` reads every record, `monitoring_summary` any record whose key carries `monitoring`. An EXP-4 hazard run sweeping `monitoring` draws the monitoring figure unless the spec declares `key_readout: hazard`, which is what `exp04.yaml` does. The declared readout is the dependable path; the fallback order is a heuristic.

`run_experiment` calls `write_key_figure` after it has written `records.jsonl`, the manifest and `report.txt`. A declared readout the records cannot feed (every trial errored, say) used to raise there, turning a paid, recorded run into a crash; since `343d166` `write_key_figure` writes a `key.json` saying nothing was drawn and returns `None`. `key_figure` called directly still raises for that case.



## Rendering
Each figure is `7.2 × 3.8` in at 130 dpi, two columns when it has more than one panel. `_line` cycles four line styles and eight markers so coincident series stay visible; `_categorical_x` wraps condition labels and rotates them past six. Labels are `name=value` joined by `&`; target ids are shortened to their last path segment. `matplotlib.use("Agg")` runs on every figure, switching the process-wide backend, which a notebook or GUI host importing the module would notice.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `0b77270`, by reading `plots.py`, the section order in `report_text.py`, and the two `write_key_figure` call sites; no figure was drawn. Left out: `hazard.py`'s three summaries (their own page when written), the `bio report` page that embeds the PNG, and each plot's styling beyond what changes what it shows.
- 2026-10-28 — refreshed against 0eb23e5 (`343d166`): `PLOTTERS`' order is documented as specific-first by design, `write_key_figure` no longer raises when a declared readout draws nothing, a missing monitoring arm draws no bar.
