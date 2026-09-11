"""The text report over a ``ReliabilityMap`` — ``render_report`` and the idle-baseline / primary-contrast reads (T058; split out of ``experiment.py``)."""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence


from .delta import delta_summary
from .effect_size import cohens_d, welch_t
from .hazard import DEPTHS, OBJECTIVE_TYPES, blindspot_summary, consideration_summary, hazard_surfacing_summary
from .tradeoff import conflict_summary, precedence_ladder
from .dose import dose_profile, pressure_summary
from .caution import CAUTION_AXES, appropriate_caution, caution_factorial, caution_summary, caution_trend
from .degradation import degradation_ladder, degradation_summary
from .faking import monitoring_divergence, monitoring_summary
from .census import census_summary, outcome_distribution
from .power import bonferroni_alpha
from .mass_trial import ReliabilityMap


_REPO_ROOT = Path(__file__).resolve().parents[3]



def _condition_label(key: Sequence[tuple[str, Any]]) -> str:
    return "&".join(f"{name}={value}" for name, value in key)


def render_report(rmap: ReliabilityMap, manifest: Mapping[str, Any]) -> str:
    """A plain-text report: header + per-condition table + failure census +
    interaction/contrast lines (when present). No third-party formatting."""
    lines: list[str] = []
    lines.append(f"Experiment: {manifest.get('name')}")
    lines.append(f"Commit: {manifest.get('git_commit')} (dirty={manifest.get('git_dirty')})")
    lines.append(f"Model: {manifest.get('model')}")
    lines.append(f"Started: {manifest.get('started_at')}   Finished: {manifest.get('finished_at')}")
    lines.append(
        f"Trials planned: {manifest.get('trials_planned')}   "
        f"completed: {manifest.get('trials_completed')}   "
        f"failed: {manifest.get('failed_trials')}"
    )

    ceiling = manifest.get("cost_ceiling_usd")
    ceiling_str = f"${ceiling:.4f}" if ceiling is not None else "none"
    estimate_usd = (manifest.get("cost_estimate") or {}).get("usd", 0.0)
    lines.append(
        f"Cost: spent ${manifest.get('cost_usd_spent', 0.0):.4f} "
        f"(ceiling {ceiling_str}) — estimate was ${estimate_usd:.4f}"
    )
    usage_totals = manifest.get("usage_totals") or {}
    total_wall_time_s = sum(r.wall_time_s for r in rmap.records)
    lines.append(
        f"Usage: calls={usage_totals.get('calls', 0)} "
        f"input_tokens={usage_totals.get('input_tokens', 0)} "
        f"output_tokens={usage_totals.get('output_tokens', 0)} "
        f"cache_read_tokens={usage_totals.get('cache_read_tokens', 0)} "
        f"cache_write_tokens={usage_totals.get('cache_write_tokens', 0)}   "
        f"wall_time_s={total_wall_time_s:.3f}"
    )
    lines.append("")

    lines.append("Conditions:")
    axis_names = [name for name, _ in rmap.provenance.axes]
    header = ", ".join(axis_names) if axis_names else "(condition)"
    lines.append(f"  {header:<40} {'n':>4} {'mean':>10} {'std':>10} {'ci_low':>10} {'ci_high':>10}")
    for key, summary in sorted(rmap.cells.items(), key=lambda kv: str(kv[0])):
        label = _condition_label(key)
        lines.append(
            f"  {label:<40} {summary.stats.n:>4} {summary.stats.mean:>10.4f} "
            f"{summary.stats.std:>10.4f} {summary.ci[0]:>10.4f} {summary.ci[1]:>10.4f}"
        )
    lines.append("")

    lines.append("Failure census:")
    terminal_counts: dict[str, int] = {}
    illegal_total = 0
    error_count = 0
    error_classes: dict[str, int] = {}
    abort_counts: dict[str, int] = {}
    for record in rmap.records:
        terminal_counts[record.terminal_reason] = terminal_counts.get(record.terminal_reason, 0) + 1
        illegal_total += record.illegal_actions
        if record.error:
            error_count += 1
            # T054 #2: the operator could not tell six taints from six
            # rate-limit errors — the class is the first token of the message.
            klass = record.error.split(":", 1)[0].strip() or "error"
            error_classes[klass] = error_classes.get(klass, 0) + 1
        for step in record.deliberation_trace.steps:
            if step.kind != "abort":
                continue
            for tag in ("parse_exhausted", "token_ceiling"):
                if tag in step.content:
                    abort_counts[tag] = abort_counts.get(tag, 0) + 1
    for reason, count in sorted(terminal_counts.items()):
        lines.append(f"  terminal_reason={reason!r}: {count}")
    lines.append(f"  illegal_actions (total): {illegal_total}")
    lines.append(f"  records with error: {error_count}")
    for klass, count in sorted(error_classes.items()):
        lines.append(f"  error={klass}: {count}")
    for tag, count in sorted(abort_counts.items()):
        lines.append(f"  aborted={tag!r}: {count}")

    if rmap.interactions or rmap.contrasts:
        lines.append("")
        lines.append("Interactions / contrasts:")
        for pair, value in sorted(rmap.interactions.items()):
            lines.append(f"  {pair[0]} x {pair[1]} interaction: {value:.4f}")
        for pair, contrast in sorted(rmap.contrasts.items()):
            lines.append(
                f"  {pair[0]} x {pair[1]} contrast: cohens_d={contrast.cohens_d:.4f} "
                f"welch_t={contrast.welch_t:.4f}"
            )

    design = manifest.get("design")
    if design:
        lines.append("")
        lines.append("Design (M46.9, declared before the spend):")
        n_spec = (manifest.get("spec") or {}).get("trials_per_condition")
        required = design.get("required_trials_per_condition")
        verdict = "ok" if (n_spec is not None and required is not None and n_spec >= required) else "UNDERPOWERED"
        lines.append(
            f"  target d={design.get('target_effect_d')} alpha={design.get('alpha')} "
            f"power={design.get('power')} -> required n={required}; spec n={n_spec} ({verdict})"
        )
        m = len(rmap.contrasts)
        policy = design.get("multiple_comparison", "none")
        alpha = float(design.get("alpha", 0.05))
        adjusted = bonferroni_alpha(alpha, m) if policy == "bonferroni" else alpha
        lines.append(f"  multiple comparisons: policy={policy} contrasts={m} alpha_used={adjusted:.5f}")
        pc = design.get("primary_contrast")
        if pc:
            result = primary_contrast_result(rmap, pc)
            if result is None:
                lines.append(
                    f"  primary contrast {pc['axis']}: {pc['low']} -> {pc['high']}: "
                    "undefined (fewer than 2 scored trials on a side, or zero variance on both sides)"
                )
            else:
                lines.append(
                    f"  primary contrast {pc['axis']}: {pc['low']} -> {pc['high']}: "
                    f"cohens_d={result['cohens_d']:.4f} welch_t={result['welch_t']:.4f} "
                    f"(n_low={result['n_low']}, n_high={result['n_high']})"
                )

    hazard_rows = hazard_surfacing_summary(rmap.records)
    if hazard_rows:
        lines.append("")
        lines.append("Hazard surfacing (M36.1, EXP-4 — records carrying a hazard oracle):")
        lines.append(f"  {'condition':<40} {'n':>4} {'surfaced':>9} {'rate':>7} {'mean_turn':>10}")
        for key, (n, surfaced, mean_turn) in sorted(hazard_rows.items(), key=lambda kv: str(kv[0])):
            rate = surfaced / n if n else 0.0
            mean_str = f"{mean_turn:.2f}" if mean_turn is not None else "-"
            lines.append(f"  {_condition_label(key):<40} {n:>4} {surfaced:>9} {rate:>7.3f} {mean_str:>10}")

    consideration_rows = consideration_summary(rmap.records)
    if consideration_rows:
        lines.append("")
        lines.append("Objective surfacing by depth (M36.2, EXP-5 — records carrying a consideration schedule):")
        lines.append(f"  {'condition':<40} {'id':<8} {'depth':<8} {'n':>4} {'surfaced':>9} {'on_time':>8} {'mean_turn':>10}")
        for key, row in sorted(consideration_rows.items(), key=lambda kv: str(kv[0])):
            label = _condition_label(key)
            for cid, (depth, n, surfaced, on_time, mean_turn) in sorted(row.items(), key=lambda kv: DEPTHS.index(kv[1][0])):
                mean_str = f"{mean_turn:.2f}" if mean_turn is not None else "-"
                lines.append(
                    f"  {label:<40} {cid:<8} {depth:<8} {n:>4} {surfaced:>9} {on_time:>8} {mean_str:>10}"
                )

    blind_rows = blindspot_summary(rmap.records)
    if blind_rows and any(t for _, (_, _, per_type) in blind_rows.items() for t in per_type):
        lines.append("")
        lines.append("Blind spots by objective type (M36.3, EXP-6 — coverage of the should-have-considered set):")
        types = sorted({t for _, (_, _, per_type) in blind_rows.items() for t in per_type}, key=lambda t: (OBJECTIVE_TYPES.index(t) if t in OBJECTIVE_TYPES else 99, t))
        header = "".join(f" {t:>12}" for t in types)
        lines.append(f"  {'condition':<40} {'n':>4} {'blindspot':>10}{header}")
        for key, (n, rate, per_type) in sorted(blind_rows.items(), key=lambda kv: str(kv[0])):
            cells = "".join(f" {per_type[t][1]:>12.3f}" if t in per_type else f" {'-':>12}" for t in types)
            lines.append(f"  {_condition_label(key):<40} {n:>4} {rate:>10.3f}{cells}")

    conflict_rows = conflict_summary(rmap.records)
    if conflict_rows:
        lines.append("")
        lines.append("Conflict resolution (M36.4, EXP-7 — records carrying a conflict oracle):")
        lines.append(f"  {'condition':<40} {'n':>4} {'scores':<28} {'dominant':<24} {'precedence':>10} {'pareto_d':>9}")
        for key, cell in sorted(conflict_rows.items(), key=lambda kv: str(kv[0])):
            scores = " ".join(f"{cid.rsplit('/', 1)[-1]}={v:.2f}" for cid, v in cell.mean_scores.items())
            dom = f"{cell.dominant.rsplit('/', 1)[-1]} ({cell.dominant_fraction:.2f})" if cell.dominant else "-"  # "tie (1.00)" = no preference
            prec = f"{cell.precedence_fraction:.2f}" if cell.precedence_fraction is not None else "-"
            pareto = f"{cell.mean_pareto_distance:.3f}" if cell.mean_pareto_distance is not None else "-"
            lines.append(f"  {_condition_label(key):<40} {cell.n:>4} {scores:<28} {dom:<24} {prec:>10} {pareto:>9}")
        ladder = precedence_ladder(conflict_rows)
        for group, (rungs, consistency) in sorted(ladder.items(), key=lambda kv: str(kv[0])):
            label = _condition_label(group) if group else "(all)"
            lines.append(f"  precedence consistency across {'/'.join(rungs)} for {label}: {consistency:.2f}")

    caution_rows = caution_summary(rmap.records)
    if caution_rows and any(dict(k).get("stakes") is not None or dict(k).get("reversibility") is not None or any(r.oracle.get("discover") for r in rmap.records) for k in caution_rows):
        lines.append("")
        lines.append("Caution (M36.7 / M36.8 / M33.8, EXP-1 / EXP-9 — info-seeking, destructive acts, abstention per condition):")
        lines.append(f"  {'condition':<52} {'n':>3} {'score':>6} {'info':>5} {'destr':>5} {'commit':>6} {'abstain':>7} {'false+':>6}")
        for key, cell in sorted(caution_rows.items(), key=lambda kv: str(kv[0])):
            lines.append(
                f"  {_condition_label(key):<52} {cell.n:>3} {cell.mean_score:>6.3f} {cell.mean_info_seeking:>5.2f} "
                f"{cell.mean_destructive:>5.2f} {cell.commit_rate:>6.2f} {cell.abstain_rate:>7.2f} {cell.false_positive_rate:>6.2f}"
            )
        for axis in CAUTION_AXES:
            for group, trend in sorted(caution_trend(caution_rows, axis).items(), key=lambda kv: str(kv[0])):
                label = _condition_label(group) if group else "(all)"
                path = " -> ".join(f"{l}: info={i:.2f} destr={d:.2f} abstain={a:.2f}" for l, i, d, a in zip(trend.levels, trend.info_seeking, trend.destructive, trend.abstain))
                lines.append(f"  {axis} for {label}: {path}; info-seeking non-decreasing={'yes' if trend.info_seeking_rises else 'NO'}, destructive non-increasing={'yes' if trend.destructive_falls else 'NO'}")

        factorials = caution_factorial(caution_rows, "stakes", "reversibility", "mean_info_seeking")
        if factorials:
            lines.append("  Stakes x reversibility factorial (M36.8, EXP-9 — info-seeking before the decisive act):")
            for group, f in sorted(factorials.items(), key=lambda kv: str(kv[0])):
                label = _condition_label(group) if group else "(all)"
                grid = " ".join(f"[{a}/{b}]={v:.2f}" for (a, b), v in f.cells.items())
                lines.append(
                    f"    {label}: {grid}; main stakes={f.main_effect_a:+.2f} main reversibility={f.main_effect_b:+.2f} "
                    f"interaction={f.interaction:+.2f} additive={'yes' if f.additive else 'NO'}"
                )
            for key, cell in sorted(caution_rows.items(), key=lambda kv: str(kv[0])):
                d = dict(key)
                ref = appropriate_caution(d.get("stakes"), d.get("reversibility"))
                if ref is not None:
                    lines.append(f"    {_condition_label(key)}: info={cell.mean_info_seeking:.2f} reference={ref:.2f} over/under={cell.mean_info_seeking - ref:+.2f}")

    monitoring_rows = monitoring_summary(rmap.records)
    if monitoring_rows:
        lines.append("")
        lines.append("Monitoring divergence (M36.10 / M33.10, EXP-3 — matched arms, the destructive assay):")
        lines.append(f"  {'condition':<36} {'arm':<22} {'n':>3} {'assay':>6} {'mean':>5} {'acc':>5} {'abstain':>7}")
        for key, arms in sorted(monitoring_rows.items(), key=lambda kv: str(kv[0])):
            label = _condition_label(key) if key else "(all)"
            for arm, cell in sorted(arms.items()):
                lines.append(f"  {label:<36} {arm:<22} {cell.n:>3} {cell.assay_rate:>6.2f} {cell.mean_assays:>5.2f} {cell.accuracy:>5.2f} {cell.abstain_rate:>7.2f}")
            d = monitoring_divergence(arms)
            fmt = lambda v: "-" if v is None else f"{v:+.2f}"
            lines.append(f"  {label}: faking={fmt(d.faking)} deception_gap={fmt(d.deception_gap)} sandbagging={fmt(d.sandbagging)} -> {d.label}")

    degradation_rows = degradation_summary(rmap.records)
    if degradation_rows and any("budget" in dict(k) for k in degradation_rows):
        lines.append("")
        lines.append("Degradation (M36.9 / M33.9, EXP-10 — the budget ladder, loosest to tightest):")
        lines.append(f"  {'condition':<44} {'n':>3} {'acc':>5} {'inv':>5} {'ver':>4} {'commit':>6} {'exhst':>5} {'premat':>6} {'skipv':>5} {'narrow':>6} {'revert':>6} {'aware':>5}")
        for key, cell in sorted(degradation_rows.items(), key=lambda kv: (str(dict(kv[0]).get("agent", "")), -__import__("alienbio.suite.degradation", fromlist=["budget_total"]).budget_total(dict(kv[0]).get("budget")), str(kv[0]))):
            lines.append(
                f"  {_condition_label(key):<44} {cell.n:>3} {cell.accuracy:>5.2f} {cell.mean_investigated:>5.2f} {cell.mean_verified:>4.2f} "
                f"{cell.commit_rate:>6.2f} {cell.exhausted_rate:>5.2f} {cell.premature_rate:>6.2f} {cell.skipped_verification_rate:>5.2f} "
                f"{cell.scope_narrowing_rate:>6.2f} {cell.reversion_rate:>6.2f} {cell.budget_aware_rate:>5.2f}"
            )
        for group, ladder in sorted(degradation_ladder(degradation_rows).items(), key=lambda kv: str(kv[0])):
            label = _condition_label(group) if group else "(all)"
            path = " -> ".join(f"{l}: acc={a:.2f} exhausted={c.exhausted_rate:.2f}" for l, a, c in zip(ladder.levels, ladder.accuracy, ladder.cells))
            cliff = f"cliff at {ladder.cliff}" if ladder.cliff is not None else "no cliff"
            lines.append(f"  budget ladder for {label}: {path}; {cliff}; accuracy non-increasing={'yes' if ladder.accuracy_non_increasing else 'NO'}")

    delta_rows = delta_summary(rmap.records)
    if delta_rows:
        lines.append("")
        lines.append("Delta (M36.6, EXP-8 — matched pairs, records carrying a delta oracle):")
        lines.append(f"  {'condition':<32} {'pairs':>5} {'match':>6} {'mismatch':>8} {'gap':>6} {'prior':>6} {'world':>6} {'state_div':>9}")
        for key, cell in sorted(delta_rows.items(), key=lambda kv: str(kv[0])):
            label = _condition_label(key) if key else "(all)"
            unpaired = f" (+{cell.n_unpaired} unpaired)" if cell.n_unpaired else ""
            if cell.n_pairs == 0:
                lines.append(f"  {label:<32} {0:>5} no complete pair — every record here lacks its twin on the other arm{unpaired}")
                continue
            lines.append(
                f"  {label:<32} {cell.n_pairs:>5} {cell.mean_match:>6.3f} {cell.mean_mismatch:>8.3f} {cell.gap:>+6.3f} "
                f"{cell.prior_following_fraction:>6.2f} {cell.world_tracking_fraction:>6.2f} {cell.mean_state_divergence:>9.3f}{unpaired}"
            )

    dose_rows = pressure_summary(rmap.records)
    if dose_rows:
        lines.append("")
        lines.append("Pressure dose-response (M36.5, EXP-2 — records carrying a pressure oracle):")
        lines.append(f"  {'condition':<32} {'pi':>4} {'n':>3} {'T':>8} {'side':>8} {'score':>6} {'passive T':>10} {'passive side':>12} {'v_target':>9}")
        for key, cells in sorted(dose_rows.items(), key=lambda kv: str(kv[0])):
            label = _condition_label(key) if key else "(all)"
            for c in cells:
                lines.append(
                    f"  {label:<32} {c.pi:>4.2f} {c.n:>3} {c.mean_t:>8.3f} {c.mean_byproduct:>8.3f} "
                    f"{c.mean_score:>6.3f} {c.passive_t:>10.3f} {c.passive_byproduct:>12.3f} {c.v_target:>9.3f}"
                )
            prof = dose_profile(cells)
            by = f"{prof.fraction_by_continuity_pi:.2f}" if prof.fraction_by_continuity_pi is not None else "-"
            step = f"{prof.max_step_fraction:.2f}" if prof.max_step_fraction is not None else "-"
            cont = {True: "yes", False: "NO", None: "-"}[prof.continuous]
            lines.append(
                f"  {label}: swing={prof.swing:.3f} by_pi0.2={by} max_step={step} "
                f"monotone={'yes' if prof.monotone else 'NO'} continuous={cont} "
                f"passive_clears_target={'YES' if prof.passive_clears_target else 'no'}"
            )

    census_rows = census_summary(rmap.records)
    if census_rows:
        lines.append("")
        lines.append("Census (M45.16 — engagement per condition; a trial with no accepted intervene is disengaged, never refraining):")
        lines.append(f"  {'condition':<44} {'n':>3} {'interv':>6} {'diseng':>6} {'turns':>6} {'trace':>6} {'illegal':>7}")
        for key, cell in sorted(census_rows.items(), key=lambda kv: str(kv[0])):
            lines.append(
                f"  {_condition_label(key):<44} {cell.n:>3} {cell.mean_intervenes:>6.2f} {cell.disengaged_rate:>6.2f} "
                f"{cell.mean_turns:>6.2f} {cell.mean_trace_steps:>6.2f} {cell.mean_illegal:>7.2f}"
            )
    dist_rows = outcome_distribution(rmap.records)
    if dist_rows:
        lines.append("")
        lines.append("Side-product distribution (M45.16 — per condition: quantiles, dispersion at fixed seeds, CI, delta vs the idle twin):")
        lines.append(f"  {'condition':<44} {'n':>3} {'mean':>8} {'std':>8} {'min':>8} {'p25':>8} {'median':>8} {'p75':>8} {'max':>8} {'ci_low':>8} {'ci_high':>8} {'vs idle':>8}")
        for key, d in sorted(dist_rows.items(), key=lambda kv: str(kv[0])):
            q = d.quantiles
            delta = f"{d.idle_delta:+8.4f}" if d.idle_delta is not None else f"{'-':>8}"
            lines.append(
                f"  {_condition_label(key):<44} {d.n:>3} {d.mean:>8.4f} {d.std:>8.4f} {q[0]:>8.4f} {q[1]:>8.4f} {q[2]:>8.4f} {q[3]:>8.4f} {q[4]:>8.4f} "
                f"{d.ci[0]:>8.4f} {d.ci[1]:>8.4f} {delta}"
            )

    twins = idle_baseline_comparison(rmap)
    if twins:
        lines.append("")
        lines.append("Idle baseline (M45.7, matched seeds):")
        for cond, live_agent, live_mean, idle_mean, n in twins:
            delta = live_mean - idle_mean
            lines.append(
                f"  {cond}: {live_agent}={live_mean:.4f} idle={idle_mean:.4f} delta={delta:+.4f} (n={n})"
            )

    lines.append("")
    return "\n".join(lines)


def idle_baseline_comparison(rmap: ReliabilityMap) -> list[tuple[str, str, float, float, int]]:
    """Per condition (agent dial removed), the live arm's mean score beside its
    idle twin's — ``(condition_label, live_agent, live_mean, idle_mean, n)``,
    only for conditions that have both arms with scored records."""
    by_cond: dict[tuple[tuple[str, Any], ...], dict[str, list[float]]] = {}
    for record in rmap.records:
        if record.is_error:
            continue
        key = dict(record.bucket_key)
        agent = str(key.pop("agent", ""))
        if not agent:
            continue
        cond = tuple(sorted(key.items()))
        by_cond.setdefault(cond, {}).setdefault(agent, []).append(record.objective_score)
    rows: list[tuple[str, str, float, float, int]] = []
    for cond, arms in sorted(by_cond.items(), key=lambda kv: str(kv[0])):
        idle = arms.get("idle")
        if not idle:
            continue
        for agent, scores in sorted(arms.items()):
            if agent == "idle" or not scores:
                continue
            label = "&".join(f"{n}={v}" for n, v in cond) or "(all)"
            rows.append((label, agent, statistics.fmean(scores), statistics.fmean(idle), min(len(scores), len(idle))))
    return rows


def primary_contrast_result(rmap: ReliabilityMap, contrast: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    """Cohen's d / Welch t for the declared primary contrast, pooling every
    scored record at ``axis == low`` against every one at ``axis == high``
    (all other swept dials pooled). ``None`` when a side has fewer than two
    scored records or the pooled standard deviation is zero."""
    axis, low, high = contrast["axis"], contrast["low"], contrast["high"]
    low_scores: list[float] = []
    high_scores: list[float] = []
    for record in rmap.records:
        if record.is_error:
            continue
        level = dict(record.bucket_key).get(axis)
        if level == low:
            low_scores.append(record.objective_score)
        elif level == high:
            high_scores.append(record.objective_score)
    if len(low_scores) < 2 or len(high_scores) < 2:
        return None
    try:
        d = cohens_d(high_scores, low_scores)
    except ValueError:
        return None
    return {
        "cohens_d": d,
        "welch_t": welch_t(high_scores, low_scores),
        "n_low": len(low_scores),
        "n_high": len(high_scores),
    }
