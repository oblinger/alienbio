#!/usr/bin/env python3
"""Optional: LLM Agent Demo — Run Claude on a skinned diagnosis task.

Requires ANTHROPIC_API_KEY in .env file. Skips gracefully if not available.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env file if present
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def main():
    print("=" * 60)
    print("Optional: LLM Agent Demo")
    print("=" * 60)

    if not API_KEY:
        print("\nSkipping: ANTHROPIC_API_KEY not found.")
        print("Set it in the .env file at the repo root to run this demo.")
        return True

    try:
        import anthropic
    except ImportError:
        print("\nSkipping: anthropic package not installed.")
        print("Run: pip install anthropic")
        return True

    from _shared import make_disease_system, oracle_agent, random_agent
    from alienbio.bio import AgentInterface, DiagnoseTask
    from alienbio.scenarios.skinning import generate_name_map, generate_description

    # Build skinned diagnosis task
    system, baseline, perturbs = make_disease_system(seed=42)
    name_map = generate_name_map(system, seed=42)
    desc = generate_description(system, detail_level=2, name_map=name_map, seed=42)

    task = DiagnoseTask(perturbs[:4], applied_index=0)
    iface = AgentInterface(system)

    # Describe the task for Claude
    candidate_descs = []
    for i, p in enumerate(task.candidates):
        skinned_name = name_map.get(p.target_reaction, p.target_reaction)
        candidate_descs.append(f"  {i}: {p.kind} affecting process '{skinned_name}'")

    prompt = f"""You are diagnosing an alien biological system.

{desc}

The system is currently diseased. One of the following perturbations was applied:
{chr(10).join(candidate_descs)}

Based on the system description, which perturbation (0-{len(task.candidates)-1}) is most likely?
Reply with ONLY the number."""

    print(f"\nSending diagnosis task to Claude...")
    client = anthropic.Anthropic(api_key=API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    llm_answer = response.content[0].text.strip()

    try:
        llm_pred = int(llm_answer)
    except ValueError:
        llm_pred = 0
        print(f"  Claude said '{llm_answer}' — parsing as 0")

    # Score all agents
    llm_result = task.score(iface, llm_pred)
    oracle_result = task.score(iface, oracle_agent(iface, task))
    random_result = task.score(iface, random_agent(iface, task))

    print(f"\n--- Results ---")
    print(f"  Claude:  predicted={llm_pred}, score={llm_result.score:.2f}")
    print(f"  Oracle:  predicted={task.correct_index}, score={oracle_result.score:.2f}")
    print(f"  Random:  score={random_result.score:.2f}")

    return True


if __name__ == "__main__":
    main()
