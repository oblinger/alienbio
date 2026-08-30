"""suite.plots — the one key figure of an experiment run.

Every ``report.txt`` has one section that is the experiment's reason to
exist — the dose-response curve, the conflict ladder, the paired delta gap,
the budget cliff … :func:`key_figure` draws that section and nothing else,
choosing it from what the records carry exactly as :func:`render_report`
chooses which sections to print (the same summary functions, the same
order). ``run_experiment`` and ``bio suite report`` write it beside
``report.txt`` as ``key.png`` + ``key.json`` (the readout name and a caption);
``bio report`` embeds it under the run's row.

The figure is drawn from the aggregated summaries, never from the raw
timelines, so it reads on a reloaded record store exactly as on a live one.
Matplotlib is loaded lazily on the ``Agg`` backend — nothing here opens a
window.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional, Sequence, Union

from .caution import CAUTION_AXES, caution_summary
from .conflict_gen import RUNGS
from .degradation import degradation_ladder, degradation_summary
from .delta import delta_summary
from .dose import pressure_summary
from .faking import monitoring_divergence, monitoring_summary
from .hazard import DEPTHS, OBJECTIVE_TYPES, blindspot_summary, consideration_summary, hazard_surfacing_summary
from .tradeoff import conflict_summary

if TYPE_CHECKING:
    from matplotlib.figure import Figure

    from .mass_trial import ReliabilityMap

ConditionKey = tuple[tuple[str, Any], ...]

WIDTH, HEIGHT, DPI = 7.2, 3.8, 130


@dataclass(frozen=True)
class KeyFigure:
    """One run's key figure: which readout it draws, a one-line caption, the figure."""

    readout: str
    caption: str
    figure: "Figure"


# ---- helpers -----------------------------------------------------------------


def _label(key: Sequence[tuple[str, Any]]) -> str:
    return "&".join(f"{name}={value}" for name, value in key) or "(all)"


def _short(identifier: str) -> str:
    return identifier.rsplit("/", 1)[-1]


def _split(cells: Mapping[ConditionKey, Any], axis: str) -> dict[ConditionKey, dict[Any, Any]]:
    """``{group (every dial but axis): {level: cell}}`` — the ladder functions' grouping."""
    groups: dict[ConditionKey, dict[Any, Any]] = {}
    for key, cell in cells.items():
        d = dict(key)
        if axis not in d:
            continue
        level = d.pop(axis)
        groups.setdefault(tuple(sorted(d.items())), {})[level] = cell
    return groups


def _new_figure(title: str, npanels: int = 1) -> tuple["Figure", list[Any]]:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    ncols = min(npanels, 2)
    nrows = (npanels + ncols - 1) // ncols
    fig = Figure(figsize=(WIDTH if ncols == 1 else WIDTH * 1.35, HEIGHT * (1 if nrows == 1 else 0.85 * nrows)), dpi=DPI)
    axes = [fig.add_subplot(nrows, ncols, i + 1) for i in range(npanels)]
    for ax in axes:
        ax.grid(True, alpha=0.3)
    fig.suptitle(title, fontsize=10)
    return fig, axes


def _finish(fig: "Figure") -> None:
    fig.tight_layout(rect=(0, 0, 1, 0.93))


def _legend(ax: Any, **kw: Any) -> None:
    handles, _ = ax.get_legend_handles_labels()
    if handles:
        ax.legend(fontsize=7, **kw)


_LINESTYLES = ("-", "--", "-.", ":")
_MARKERS = ("o", "s", "^", "D", "v", "P", "x", "*")


def _line(ax: Any, xs: Sequence[Any], ys: Sequence[float], i: int, label: str, **kw: Any) -> Any:
    """One series with the i-th (linestyle, marker) pair, so coincident lines still both show."""
    (line,) = ax.plot(xs, ys, ls=_LINESTYLES[i % len(_LINESTYLES)], marker=_MARKERS[i % len(_MARKERS)], ms=5, mfc="none" if i % 2 else None, label=label, **kw)
    return line


def _wrap(text: str, width: int = 34) -> str:
    import textwrap

    return "\n".join(textwrap.wrap(text, width)) or text


def _grouped_bars(ax: Any, groups: Sequence[str], series: Mapping[str, Sequence[float]], ylabel: str) -> None:
    """Bars for each ``series`` side by side within each of ``groups``."""
    n = max(len(series), 1)
    width = 0.8 / n
    for i, (name, values) in enumerate(series.items()):
        xs = [g + (i - (n - 1) / 2) * width for g in range(len(groups))]
        ax.bar(xs, list(values), width=width * 0.95, label=name)
    _categorical_x(ax, groups)
    ax.set_ylabel(ylabel, fontsize=8)
    ax.tick_params(axis="y", labelsize=7)


def _categorical_x(ax: Any, labels: Sequence[str]) -> None:
    """Condition labels on the x axis: wrapped, and rotated once there are many."""
    ax.set_xticks(range(len(labels)))
    crowded = len(labels) > 6 or sum(len(l) for l in labels) > 90
    ax.set_xticklabels([_wrap(l, 22) for l in labels], fontsize=6 if crowded else 7, rotation=30 if crowded else 0, ha="right" if crowded else "center")


# ---- the plotters, one per readout ------------------------------------------


def plot_dose(rmap: "ReliabilityMap") -> Optional[KeyFigure]:
    """EXP-2 — side-product at the end of the episode along the ``pi`` ladder."""
    rows = pressure_summary(rmap.records)
    if not rows:
        return None
    fig, (ax,) = _new_figure("Pressure dose-response — side-product vs π")
    for i, (key, cells) in enumerate(sorted(rows.items(), key=lambda kv: str(kv[0]))):
        cells = sorted(cells, key=lambda c: c.pi)
        _line(ax, [c.pi for c in cells], [c.mean_byproduct for c in cells], i, _label(key))
    ax.set_xlabel("π (pressure dial)", fontsize=8)
    ax.set_ylabel("side-product (trial mean)", fontsize=8)
    ax.tick_params(labelsize=7)
    _legend(ax)
    _finish(fig)
    return KeyFigure("dose", "Side-product yield at the end of the episode along the π ladder, one line per condition — the swing, continuity and monotonicity read of the pressure dial.", fig)


def plot_conflict(rmap: "ReliabilityMap") -> Optional[KeyFigure]:
    """EXP-7 — each target's attainment along the conflict ladder."""
    rows = conflict_summary(rmap.records)
    if not rows:
        return None
    groups = _split(rows, "rung")
    if not groups:
        return None
    fig, axes = _new_figure("Conflict resolution — target attainment along the ladder", npanels=len(groups))
    for ax, (gkey, by_rung) in zip(axes, sorted(groups.items(), key=lambda kv: str(kv[0]))):
        rungs = [r for r in RUNGS if r in by_rung]
        targets = sorted({t for cell in by_rung.values() for t in cell.mean_scores})
        for i, target in enumerate(targets):
            _line(ax, rungs, [by_rung[r].mean_scores.get(target, float("nan")) for r in rungs], i, _short(target))
        ax.set_title(_wrap(_label(gkey)), fontsize=7)
        ax.set_ylabel("mean attainment", fontsize=8)
        ax.tick_params(labelsize=7)
        _legend(ax)
    _finish(fig)
    return KeyFigure("conflict", "Mean attainment of each target at every rung of the conflict ladder (compatible → latent → forced), one panel per framing — where the trade-off bites and which target gives way.", fig)


def plot_delta(rmap: "ReliabilityMap") -> Optional[KeyFigure]:
    """EXP-8 — score on the matched arm beside the mismatched arm, per condition."""
    rows = delta_summary(rmap.records)
    if not rows:
        return None
    labels = [_label(k) for k in sorted(rows, key=str)]
    cells = [rows[k] for k in sorted(rows, key=str)]
    fig, (ax,) = _new_figure("Delta — matched pairs: same rule, rewired world")
    _grouped_bars(ax, labels, {"match": [c.mean_match for c in cells], "mismatch": [c.mean_mismatch for c in cells]}, "mean score")
    for i, c in enumerate(cells):
        ax.annotate(f"gap {c.gap:+.2f}", (i, max(c.mean_match, c.mean_mismatch) + 0.03), ha="center", fontsize=7)
    ax.set_ylim(0, 1.15)
    _legend(ax)
    _finish(fig)
    return KeyFigure("delta", "Mean score on the matched world beside the mismatched twin, per decision rule; the gap is baseline-disposition sensitivity (a prior-following rule gaps to 1, the null to 0).", fig)


def plot_degradation(rmap: "ReliabilityMap") -> Optional[KeyFigure]:
    """EXP-10 — accuracy and exhaustion down the budget ladder, the cliff marked."""
    rows = degradation_summary(rmap.records)
    if not rows or not any("budget" in dict(k) for k in rows):
        return None
    ladders = degradation_ladder(rows)
    if not ladders:
        return None
    fig, (ax,) = _new_figure("Degradation — the budget ladder, loosest to tightest")
    for i, (gkey, ladder) in enumerate(sorted(ladders.items(), key=lambda kv: str(kv[0]))):
        levels = [str(l) for l in ladder.levels]
        line = _line(ax, levels, ladder.accuracy, 2 * i, f"{_label(gkey)} accuracy")
        _line(ax, levels, [c.exhausted_rate for c in ladder.cells], 2 * i + 1, f"{_label(gkey)} exhausted", color=line.get_color())
        if ladder.cliff is not None:
            ax.axvline(levels.index(str(ladder.cliff)), color=line.get_color(), alpha=0.35, lw=6)
    ax.set_xlabel("budget", fontsize=8)
    ax.set_ylabel("rate", fontsize=8)
    ax.set_ylim(-0.05, 1.05)
    ax.tick_params(labelsize=7)
    _legend(ax, ncol=2)
    _finish(fig)
    return KeyFigure("degradation", "Accuracy (solid) and budget exhaustion (dashed) at each rung of the budget ladder, one colour per rule; a shaded rung is the cliff — the first rung whose accuracy drops below the top.", fig)


def plot_monitoring(rmap: "ReliabilityMap") -> Optional[KeyFigure]:
    """EXP-3 — destructive-assay rate by monitoring arm."""
    rows = monitoring_summary(rmap.records)
    if not rows:
        return None
    groups = [k for k in sorted(rows, key=str)]
    arms = sorted({arm for arms in rows.values() for arm in arms})
    fig, (ax,) = _new_figure("Monitoring divergence — the destructive assay by belief arm")
    _grouped_bars(ax, [_label(g) for g in groups], {arm: [rows[g][arm].assay_rate if arm in rows[g] else 0.0 for g in groups] for arm in arms}, "assay rate")
    for i, g in enumerate(groups):
        d = monitoring_divergence(rows[g])
        ax.annotate(d.label, (i, 1.02), ha="center", fontsize=7)
    ax.set_ylim(0, 1.15)
    _legend(ax)
    _finish(fig)
    return KeyFigure("monitoring", "Rate of the forbidden destructive assay under each monitoring belief (logged / apparently unlogged / deceptively unlogged), per framing and rule; a rise from logged to unlogged is faking, the label above each group is the verdict.", fig)


def plot_caution(rmap: "ReliabilityMap") -> Optional[KeyFigure]:
    """EXP-1 / EXP-9 — info-seeking and destructive acts over stakes × reversibility."""
    rows = caution_summary(rmap.records)
    if not rows or not any(dict(k).get("stakes") is not None or dict(k).get("reversibility") is not None for k in rows):
        return None
    axis = "reversibility" if any("reversibility" in dict(k) for k in rows) else "stakes"
    levels = list(CAUTION_AXES[axis])
    groups = _split(rows, axis)
    fig, (ax_info, ax_destr) = _new_figure("Caution — investigation and destructive acts by stakes × reversibility", npanels=2)
    for i, (gkey, by_level) in enumerate(sorted(groups.items(), key=lambda kv: str(kv[0]))):
        xs = [l for l in levels if l in by_level]
        _line(ax_info, xs, [by_level[l].mean_info_seeking for l in xs], i, _label(gkey))
        _line(ax_destr, xs, [by_level[l].mean_destructive for l in xs], i, _label(gkey))
    ax_info.set_ylabel("measures before the first commit", fontsize=8)
    ax_destr.set_ylabel("destructive acts per trial", fontsize=8)
    for ax in (ax_info, ax_destr):
        ax.set_xlabel(axis, fontsize=8)
        ax.tick_params(labelsize=7)
    _legend(ax_info)
    _finish(fig)
    return KeyFigure("caution", f"Information-seeking (left) and destructive acts (right) as {axis} rises, one line per remaining condition (stakes × rule); appropriate caution is a rising left panel and a falling right one — a scripted rule gives flat lines.", fig)


def plot_blindspot(rmap: "ReliabilityMap") -> Optional[KeyFigure]:
    """EXP-6 — coverage of the should-have-considered set by objective type."""
    rows = blindspot_summary(rmap.records)
    types = [t for t in OBJECTIVE_TYPES if any(t in per_type for _, (_, _, per_type) in rows.items())]
    if not rows or not types:
        return None
    panels: dict[Any, dict[ConditionKey, Any]] = {}
    for key, cell in rows.items():
        d = dict(key)
        agent = d.pop("agent", "")
        panels.setdefault(agent, {})[tuple(sorted(d.items()))] = cell
    fig, axes = _new_figure("Blind spots — coverage by objective type", npanels=len(panels))
    for ax, (agent, cells) in zip(axes, sorted(panels.items(), key=lambda kv: str(kv[0]))):
        keys = sorted(cells, key=str)
        _grouped_bars(ax, [_label(k) for k in keys], {t: [cells[k][2][t][1] if t in cells[k][2] else 0.0 for k in keys] for t in types}, "coverage (raised / should)")
        ax.plot(range(len(keys)), [cells[k][1] for k in keys], "k_", ms=14, label="blind-spot rate")
        ax.set_ylim(0, 1.1)
        if agent:
            ax.set_title(f"agent={agent}", fontsize=8)
        _legend(ax)
    _finish(fig)
    return KeyFigure("blindspot", "Coverage of the should-have-considered set by objective type (procedural / substantive / meta) under each framing and posedness, with the overall blind-spot rate as a tick; the meta item exists only on the ill-posed world.", fig)


def plot_consideration(rmap: "ReliabilityMap") -> Optional[KeyFigure]:
    """EXP-5 — how often each depth of consideration surfaced, per condition."""
    rows = consideration_summary(rmap.records)
    if not rows:
        return None
    ladder_axes = [name for name, _ in rmap.provenance.axes if name not in ("agent", "model")]
    axis = ladder_axes[0] if len(ladder_axes) == 1 else None
    levels = [l for _, ls in rmap.provenance.axes if axis is not None for l in ls if _ == axis] if axis else []

    def fraction(row: Mapping[str, tuple[str, int, int, int, Optional[float]]], depth: str) -> float:
        items = [(n, s) for (d, n, s, _, _) in row.values() if d == depth]
        total = sum(n for n, _ in items)
        return sum(s for _, s in items) / total if total else float("nan")

    fig, (ax,) = _new_figure("Objective surfacing by depth")
    i = 0
    if axis is not None:
        for gkey, by_level in sorted(_split(rows, axis).items(), key=lambda kv: str(kv[0])):
            xs = [l for l in levels if l in by_level]
            for depth in DEPTHS:
                _line(ax, [str(x) for x in xs], [fraction(by_level[x], depth) for x in xs], i, f"{depth} — {_label(gkey)}")
                i += 1
        ax.set_xlabel(axis, fontsize=8)
    else:
        keys = sorted(rows, key=str)
        for depth in DEPTHS:
            _line(ax, range(len(keys)), [fraction(rows[k], depth) for k in keys], i, depth)
            i += 1
        _categorical_x(ax, [_label(k) for k in keys])
    ax.set_ylabel("fraction surfaced", fontsize=8)
    ax.set_ylim(-0.05, 1.05)
    ax.tick_params(labelsize=7)
    _legend(ax)
    _finish(fig)
    return KeyFigure("consideration", "Fraction of trials that surfaced the shallow, medium and deep consideration under each condition (the deliberation-budget ladder) — the depth-vs-budget curve.", fig)


def plot_hazard(rmap: "ReliabilityMap") -> Optional[KeyFigure]:
    """EXP-4 — hazard surfacing rate per condition, mean surfacing turn annotated."""
    rows = hazard_surfacing_summary(rmap.records)
    if not rows:
        return None
    keys = sorted(rows, key=str)
    axes = [name for name, _ in rmap.provenance.axes]
    fig, (ax,) = _new_figure("Hazard surfacing — the unmentioned objective")
    if len(axes) >= 2:
        first, rest = axes[0], axes[1:]
        groups = sorted({dict(k)[first] for k in keys}, key=str)
        series = sorted({tuple((a, dict(k)[a]) for a in rest) for k in keys}, key=str)
        by = {(dict(k)[first], tuple((a, dict(k)[a]) for a in rest)): rows[k] for k in keys}
        _grouped_bars(ax, [f"{first}={g}" for g in groups], {_label(s): [by[(g, s)][1] / by[(g, s)][0] if (g, s) in by and by[(g, s)][0] else 0.0 for g in groups] for s in series}, "surfacing rate")
    else:
        _grouped_bars(ax, [_label(k) for k in keys], {"surfaced": [rows[k][1] / rows[k][0] if rows[k][0] else 0.0 for k in keys]}, "surfacing rate")
    turns = [t for (_, _, t) in rows.values() if t is not None]
    if turns:
        ax.set_title(f"mean surfacing turn where surfaced: {sum(turns) / len(turns):.1f}", fontsize=7)
    ax.set_ylim(0, 1.15)
    _legend(ax)
    _finish(fig)
    return KeyFigure("hazard", "Fraction of trials in which the injected, unmentioned hazard was surfaced, by monitoring belief and framing — whether the agent reports what it was not asked about.", fig)


def plot_trial(rmap: "ReliabilityMap") -> Optional[KeyFigure]:
    """A single-trial run (the first live trial) — its action sequence turn by turn."""
    live = [r for r in rmap.records if not r.error]
    if len(live) != 1:
        return None
    record = live[0]
    kinds = ["measure", "wait", "intervene", "assay", "commit"]
    seen = [a.kind for a in record.action_log]
    order = [k for k in kinds if k in seen] + sorted({k for k in seen if k not in kinds})
    fig, (ax,) = _new_figure(f"The one trial — {record.task_id} scored {record.objective_score:.2f}")
    for turn, action in enumerate(record.action_log):
        ax.plot(turn, order.index(action.kind), "o" if action.accepted else "x", color="C3" if action.destructive else "C0", ms=7)
        if action.target:
            ax.annotate(action.target, (turn, order.index(action.kind)), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=8)
    ax.set_xlabel("turn", fontsize=8)
    ax.set_xticks(range(len(record.action_log)))
    ax.tick_params(labelsize=7)
    _finish(fig)
    usage = record.usage or {}
    return KeyFigure("trial", f"The action the agent took at each turn (a red marker is destructive, a cross was rejected), ending in a commit that scored {record.objective_score:.2f}; {usage.get('calls', 0)} model calls.", fig)


def plot_cells(rmap: "ReliabilityMap") -> Optional[KeyFigure]:
    """Any run — mean objective score per condition with its confidence interval."""
    if not rmap.cells:
        return None
    keys = sorted(rmap.cells, key=str)
    means = [rmap.cells[k].stats.mean for k in keys]
    err = [[rmap.cells[k].stats.mean - rmap.cells[k].ci[0] for k in keys], [rmap.cells[k].ci[1] - rmap.cells[k].stats.mean for k in keys]]
    fig, (ax,) = _new_figure("Objective score per condition")
    ax.bar(range(len(keys)), means, yerr=err, capsize=3, color="C0")
    for i, m in enumerate(means):
        ax.annotate(f"{m:.2f}", (i, m + 0.02), ha="center", fontsize=7)
    _categorical_x(ax, [_label(k) for k in keys])
    ax.set_ylim(0, max(1.05, max(means) + 0.1))
    ax.set_ylabel("mean objective score", fontsize=8)
    ax.tick_params(axis="y", labelsize=7)
    _finish(fig)
    return KeyFigure("cells", "Mean objective score in each swept condition with its confidence interval — the reliability map itself, for a run with no specialised readout.", fig)


#: The readouts in the order the report prints them; the first that draws wins.
PLOTTERS: tuple[tuple[str, Callable[["ReliabilityMap"], Optional[KeyFigure]]], ...] = (
    ("dose", plot_dose),
    ("conflict", plot_conflict),
    ("delta", plot_delta),
    ("degradation", plot_degradation),
    ("monitoring", plot_monitoring),
    ("caution", plot_caution),
    ("blindspot", plot_blindspot),
    ("consideration", plot_consideration),
    ("hazard", plot_hazard),
    ("trial", plot_trial),
    ("cells", plot_cells),
)


def key_figure(rmap: "ReliabilityMap", readout: Optional[str] = None) -> Optional[KeyFigure]:
    """The run's one key figure: the declared ``readout`` (the spec's
    ``key_readout``) when given, else the first readout the records carry in
    report order; ``None`` for an empty run.

    Raises:
        ValueError: ``readout`` is not a :data:`PLOTTERS` name, or the
            records carry nothing it can draw.
    """
    plotters = dict(PLOTTERS)
    if readout is not None:
        if readout not in plotters:
            raise ValueError(f"key_figure: unknown readout {readout!r}; one of {list(plotters)}")
        fig = plotters[readout](rmap)
        if fig is None:
            raise ValueError(f"key_figure: the records carry nothing the {readout!r} readout can draw")
        return fig
    for _, plotter in PLOTTERS:
        fig = plotter(rmap)
        if fig is not None:
            return fig
    return None


def write_key_figure(rmap: "ReliabilityMap", out_dir: Union[str, Path], readout: Optional[str] = None) -> Optional[Path]:
    """Write ``key.png`` and ``key.json`` (readout + caption) into ``out_dir``;
    returns the PNG path, or ``None`` when the run has nothing to draw."""
    key = key_figure(rmap, readout)
    if key is None:
        return None
    out = Path(out_dir)
    png = out / "key.png"
    key.figure.savefig(png, dpi=DPI)
    (out / "key.json").write_text(json.dumps({"readout": key.readout, "caption": key.caption}, indent=2) + "\n")
    return png


__all__ = ["KeyFigure", "PLOTTERS", "key_figure", "write_key_figure"]
