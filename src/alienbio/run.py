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
    from .spec_lang import Bio

    # Get the DAT folder path
    dat_path = Path(dat.path)
    index_file = dat_path / "index.yaml"

    if not index_file.exists():
        raise FileNotFoundError(f"No index.yaml found in DAT: {dat_path}")

    # Load the raw expanded data (don't hydrate - we handle dicts directly)
    content = Bio.expand(str(index_file))

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


def _run_scenario(scenario: Any, dat: "Dat") -> dict[str, Any]:
    """Run a single scenario and return results.

    Args:
        scenario: Scenario object or dict
        dat: The DAT context

    Returns:
        {final_state, timeline, scores, verify_results, success}
    """
    # Extract fields from scenario (handle both object and dict)
    if isinstance(scenario, dict):
        initial_state = scenario.get("initial_state", {})
        run_config = scenario.get("run", {})
        verify = scenario.get("verify", [])
        scoring_fns = scenario.get("scoring", {})
        chemistry = scenario.get("chemistry", {})
    else:
        initial_state = getattr(scenario, "initial_state", {})
        run_config = getattr(scenario, "run", {})
        verify = getattr(scenario, "verify", [])
        scoring_fns = getattr(scenario, "scoring", {})
        chemistry = getattr(scenario, "chemistry", {})

    steps = run_config.get("steps", 100) if isinstance(run_config, dict) else 100

    # Run simulation
    state = dict(initial_state)
    timeline = [dict(state)]
    reactions = chemistry.get("reactions", {}) if isinstance(chemistry, dict) else {}

    for _ in range(steps):
        # Apply each reaction
        for rxn_name, rxn in reactions.items():
            rate_fn = rxn.get("rate") if isinstance(rxn, dict) else getattr(rxn, "rate", None)
            if callable(rate_fn):
                rate = rate_fn(state)
                reactants = rxn.get("reactants", []) if isinstance(rxn, dict) else []
                products = rxn.get("products", []) if isinstance(rxn, dict) else []

                # Apply reaction: decrease reactants, increase products
                for r in reactants:
                    if r in state:
                        state[r] = max(0, state[r] - rate)
                for p in products:
                    state[p] = state.get(p, 0) + rate

        timeline.append(dict(state))

    # Compute scores
    scores = {}
    for name, fn in scoring_fns.items():
        if callable(fn):
            scores[name] = fn(state)

    # Run verifications
    verify_results = []
    all_passed = True
    for v in verify:
        assertion = v.get("assert", "") if isinstance(v, dict) else ""
        message = v.get("message", "") if isinstance(v, dict) else ""
        try:
            # Evaluate assertion with state in scope
            passed = eval(assertion, {"state": state})
            verify_results.append({"assert": assertion, "passed": passed, "message": message})
            if not passed:
                all_passed = False
        except Exception as e:
            verify_results.append({"assert": assertion, "passed": False, "error": str(e)})
            all_passed = False

    result = {
        "final_state": state,
        "timeline": timeline,
        "scores": scores,
        "verify_results": verify_results,
        "success": all_passed,
    }

    # Print summary
    print(f"=== Scenario Results ===")
    print(f"Final state: {state}")
    print(f"Scores: {scores}")
    print(f"Verifications: {'PASSED' if all_passed else 'FAILED'}")
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
