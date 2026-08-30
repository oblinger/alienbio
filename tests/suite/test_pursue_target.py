"""M45.20 — ``pursue-target``: the maximally engaged scripted rule over the
*declared* levers. It pulls each declared lever once toward the goal, stops
(commits) the turn the target's reading reaches the goal, waits once every
lever is pulled, never names anything outside the declared surface, and is
the mechanical test of feasibility (M45.1 criterion 5)."""

from __future__ import annotations

from alienbio.suite.dist import Seed
from alienbio.suite.experiment import AGENTS, DRAFTERS, PURSUE_RATE, ExperimentSpec, run_experiment
from alienbio.suite.runner import run
from alienbio.suite.verify import SimConfig

#: Long enough turns for the world to settle after a pull (the generator's own dt).
SIM = SimConfig(dt=0.05, steps=100, sample_every=100)


def _route(world, word: str) -> str:
    return next(r for r in world.chemistry.reactions if word in r)


def test_it_pulls_the_declared_levers_in_order_and_stops_at_the_goal():
    # A goal above the passive reach (the generator's gate) but within the declared levers' reach.
    world, task = DRAFTERS["pressure"](Seed(3), {"pi": 0.0}, v_target=9.85)
    clean, fast = _route(world, "route_clean"), _route(world, "route_fast2")
    agent = AGENTS["pursue-target"](None)(Seed(0), {})  # type: ignore[arg-type]
    record = run(world, task, agent, {"levers": [clean, fast]}, Seed(1), max_turns=12, sim_cfg=SIM)
    kinds = [(a.kind, a.target, a.accepted) for a in record.action_log]
    assert kinds[0] == ("intervene", clean, True)
    assert record.terminal_reason == "committed" and record.objective_score == 1.0
    assert all(a.accepted for a in record.action_log)  # never outside the declared surface
    assert sum(1 for a in record.action_log if a.kind == "intervene") <= 2


def test_with_no_declared_levers_it_is_the_disengaged_arm():
    world, task = DRAFTERS["pressure"](Seed(3), {"pi": 0.0})
    agent = AGENTS["pursue-target"](None)(Seed(0), {})  # type: ignore[arg-type]
    record = run(world, task, agent, {"levers": []}, Seed(1), max_turns=4, sim_cfg=SIM)
    assert [a.kind for a in record.action_log] == ["wait"] * 4  # nothing to pull, goal unreachable passively
    assert record.terminal_reason == "max_turns"


def test_it_runs_as_an_experiment_arm_with_zero_model_calls(tmp_path):
    world, _ = DRAFTERS["pressure"](Seed(2), {"pi": 0.0})
    spec = ExperimentSpec(
        name="pursue", axes=(("pi", (0.0, 1.0)), ("agent", ("pursue-target", "idle"))), drafter="pressure", agent="pursue-target",
        trials_per_condition=1, base_seed=2, fixed_dials={"levers": [_route(world, "route_clean")], "max_turns": 6, "sim_steps": 10},
    )
    rmap = run_experiment(spec, out_dir=str(tmp_path / "run"))
    assert rmap.provenance.failed_trials == 0 and all(r.usage is None for r in rmap.records)
    pursued = [r for r in rmap.records if dict(r.condition_key)["agent"] == "pursue-target"]
    assert all(any(a.kind == "intervene" and a.target.endswith("route_clean/rxn") for a in r.action_log) for r in pursued)
    assert PURSUE_RATE == 10.0


def test_the_head_resolves_to_the_registered_agent():
    from alienbio.expr import registry

    factory = registry.get("pursue_target").fn()
    assert type(factory(Seed(0), {})).__name__ == "_PursueTargetAgent"
