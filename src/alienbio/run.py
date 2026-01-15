"""Standard runner for Bio DATs.

This module provides the `run` function that DAT uses to execute bio specs.
The runner loads index.yaml from the DAT folder, detects the type
(scenario, suite, report), and executes appropriately.

Usage in _spec_.yaml:
    dat:
      kind: Dat
      do: alienbio.run
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from dvc_dat import Dat


def run(dat: "Dat") -> tuple[bool, dict[str, Any]]:
    """Execute a Bio DAT.

    Loads index.yaml from the DAT folder, detects the bio type,
    and runs the appropriate simulation.

    Args:
        dat: The DAT object being executed

    Returns:
        Tuple of (success, metadata) as expected by DAT.run():
        - success: bool indicating if all verifications passed
        - metadata: Results dict with structure depending on type

    Raises:
        FileNotFoundError: If index.yaml not found in DAT folder
        ValueError: If index.yaml contains unknown type
    """
    from .spec_lang import bio

    # Get the DAT folder path
    dat_path = Path(dat.path)
    index_file = dat_path / "index.yaml"

    if not index_file.exists():
        raise FileNotFoundError(f"No index.yaml found in DAT: {dat_path}")

    # Load the raw expanded data (don't hydrate - we handle dicts directly)
    content = bio.expand(str(index_file))

    # Find the typed object in the content
    scenario_data = None
    type_name = None

    # Check for top-level _type
    if "_type" in content:
        type_name = content["_type"]
        scenario_data = content
    else:
        # Look for typed keys (scenario.name, suite.name, etc.)
        for key, value in content.items():
            if isinstance(value, dict) and "_type" in value:
                type_name = value["_type"]
                scenario_data = value
                break

    if scenario_data is None:
        # Try to run as scenario if it has chemistry
        if "chemistry" in content:
            scenario_data = content
            type_name = "scenario"
        else:
            raise ValueError(f"No typed object found in index.yaml")

    if type_name == "scenario":
        result = _run_scenario(scenario_data, dat)
    elif type_name == "suite":
        result = _run_suite(scenario_data, dat)
    elif type_name == "report":
        result = _run_report(scenario_data, dat)
    else:
        # Default to scenario
        result = _run_scenario(scenario_data, dat)

    success = result.get("success", False)
    return success, result


class SimulationTrace:
    """Trace of a simulation run, passed to scoring functions."""

    def __init__(self, final: dict[str, float], timeline: list[dict[str, float]], steps: int):
        self.final = final
        self.timeline = timeline
        self.steps = steps


def _run_scenario(scenario: Any, dat: "Dat") -> dict[str, Any]:
    """Run a single scenario and return results.

    Args:
        scenario: Scenario object or dict
        dat: The DAT context

    Returns:
        {final_state, timeline, scores, verify_results, success}
    """
    from .spec_lang import bio, eval_node, make_context
    from .bio import ChemistryImpl, StateImpl

    # Evaluate the scenario to convert Evaluable objects to values
    # This turns !ev "lambda x: ..." into actual lambda functions
    ctx = make_context()
    scenario = eval_node(scenario, ctx)

    # Extract config from scenario
    if isinstance(scenario, dict):
        sim_config = scenario.get("sim", {})
        verify = scenario.get("verify", [])
        scoring_fns = scenario.get("scoring", {})
        passing_score = scenario.get("passing_score", 0.5)
    else:
        sim_config = getattr(scenario, "sim", {})
        verify = getattr(scenario, "verify", [])
        scoring_fns = getattr(scenario, "scoring", {})
        passing_score = getattr(scenario, "passing_score", 0.5)

    steps = sim_config.get("steps", 100) if isinstance(sim_config, dict) else 100
    dt = sim_config.get("dt", 1.0) if isinstance(sim_config, dict) else 1.0
    # Build typed Chemistry and State using class-based hydration
    chemistry_data = scenario.get("chemistry", scenario)
    chemistry = ChemistryImpl.hydrate(chemistry_data, local_name="scenario_chemistry")
    initial_state_dict = scenario.get("initial_state", {})
    state = StateImpl(chemistry, initial=initial_state_dict)

    # Create simulator via Bio pegboard
    sim = bio._simulator_factory(chemistry, dt=dt)

    # Run simulation
    timeline_states = sim.run(state, steps=steps)

    # Convert StateImpl timeline to dict timeline for scoring/verify
    timeline = [dict(s.items()) for s in timeline_states]
    final_state = timeline[-1]

    # Create trace for scoring functions
    trace = SimulationTrace(final=final_state, timeline=timeline, steps=steps)

    # Compute scores - pass trace to scoring functions
    scores = {}
    for name, fn in scoring_fns.items():
        if callable(fn):
            scores[name] = fn(trace)

    # Run verifications
    verify_results = []
    verify_passed = True
    for v in verify:
        assertion = v.get("assert", "") if isinstance(v, dict) else ""
        message = v.get("message", "") if isinstance(v, dict) else ""
        try:
            # Evaluate assertion with state in scope
            passed = eval(assertion, {"state": final_state})
            verify_results.append({"assert": assertion, "passed": passed, "message": message})
            if not passed:
                verify_passed = False
        except Exception as e:
            verify_results.append({"assert": assertion, "passed": False, "error": str(e)})
            verify_passed = False

    # Determine success:
    # - If 'score' exists in scores, use score >= passing_score
    # - Otherwise fall back to verify assertions
    if "score" in scores:
        success = scores["score"] >= passing_score
    else:
        success = verify_passed

    # Write timeline to separate file (can be large)
    import yaml
    dat_path = Path(dat.path)
    timeline_file = dat_path / "timeline.yaml"
    with open(timeline_file, "w") as f:
        yaml.dump(timeline, f, default_flow_style=False)

    # Result dict (slim - no timeline)
    result = {
        "final_state": final_state,
        "scores": scores,
        "passing_score": passing_score,
        "verify_results": verify_results,
        "success": success,
    }

    # Print summary
    print(f"=== Scenario Results ===")
    print(f"Final state: {final_state}")
    print(f"Scores: {scores}")
    if "score" in scores:
        print(f"Score: {scores['score']:.3f} (passing: {passing_score}) -> {'PASSED' if success else 'FAILED'}")
    else:
        print(f"Verifications: {'PASSED' if verify_passed else 'FAILED'}")
    for v in verify_results:
        status = "✓" if v.get("passed") else "✗"
        print(f"  {status} {v.get('assert')}: {v.get('message', '')}")

    return result


def _run_suite(suite: Any, dat: "Dat") -> dict[str, Any]:
    """Run all scenarios in a suite.

    Args:
        suite: Suite object or dict
        dat: The DAT context

    Returns:
        {scenario_name: scenario_result, ...}
    """
    results = {}

    # Get scenarios from suite
    if isinstance(suite, dict):
        scenarios = {k: v for k, v in suite.items()
                    if isinstance(v, dict) and v.get("_type") == "scenario"}
    else:
        scenarios = getattr(suite, "scenarios", {})

    for name, scenario in scenarios.items():
        print(f"\n--- Running scenario: {name} ---")
        results[name] = _run_scenario(scenario, dat)

    # Summary
    passed = sum(1 for r in results.values() if r.get("success"))
    total = len(results)
    print(f"\n=== Suite Summary: {passed}/{total} passed ===")

    return results


def _run_report(report: Any, dat: "Dat") -> dict[str, Any]:
    """Run a report with iteration variables.

    Args:
        report: Report object or dict
        dat: The DAT context

    Returns:
        Report structure with computed sections
    """
    # Placeholder for report functionality
    print("Report execution not yet implemented")
    return {"status": "not_implemented"}
