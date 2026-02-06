"""Hello World scenario definitions for M5.1 system validation.

These scenarios define the H1-H5 tests for validating the full pipeline
with LLM agents. Each scenario has ground truth that enables automated
scoring.

H1: Representation Comprehension — structural questions about the world
H2: Single-Step Dynamics Prediction — predict what happens next
H3: Control Interface Exercise — follow explicit tool instructions
H4: Goal-Directed Single Intervention — achieve a stated goal
H5: Hypothesis Formation from Observation — discover hidden reactions
"""

from typing import Any


def h1_representation_comprehension() -> dict[str, Any]:
    """H1: Simple world with structural questions.

    The agent must answer questions about molecules, compartments,
    and reactions by reading the briefing and using measurements.
    """
    return {
        "name": "h1_representation",
        "briefing": (
            "You are observing an alien organism with 2 compartments: "
            "cytoplasm and membrane. The cytoplasm contains molecules "
            "Alpha (concentration 10.0) and Beta (concentration 5.0). "
            "The membrane contains Gamma (concentration 3.0). "
            "There is one reaction: Alpha + Beta → Gamma (rate 0.1). "
            "Your task: answer the questions by submitting answers."
        ),
        "constitution": "Answer accurately based on the information provided.",
        "interface": {
            "actions": {
                "submit_answer": {
                    "description": "Submit an answer to a question",
                    "params": {"question_id": "str", "answer": "str"},
                    "cost": 0.0,
                },
            },
            "measurements": {
                "sample_substrate": {
                    "description": "Measure concentrations in a compartment",
                    "params": {"region": "str"},
                    "cost": 0,
                },
            },
            "budget": 50,
        },
        "sim": {"max_agent_steps": 20, "steps_per_action": 0},
        "containers": {
            "regions": {
                "cytoplasm": {"substrate": {"Alpha": 10.0, "Beta": 5.0}},
                "membrane": {"substrate": {"Gamma": 3.0}},
            },
        },
        "scoring": {},
        "passing_score": 0.8,
        "_ground_truth_": {
            "questions": [
                {"id": "q1", "question": "What molecules are in the cytoplasm?",
                 "answer": ["Alpha", "Beta"]},
                {"id": "q2", "question": "What molecules are in the membrane?",
                 "answer": ["Gamma"]},
                {"id": "q3", "question": "What are the products of the reaction?",
                 "answer": ["Gamma"]},
                {"id": "q4", "question": "How many compartments are there?",
                 "answer": "2"},
                {"id": "q5", "question": "What is the concentration of Alpha?",
                 "answer": "10.0"},
            ],
        },
    }


def h2_dynamics_prediction() -> dict[str, Any]:
    """H2: Predict dynamics after observing state changes.

    Agent observes state at t=0 and t=1, must predict what happens at t=2.
    """
    return {
        "name": "h2_dynamics",
        "briefing": (
            "You are observing a reaction system. Observe the state, "
            "advance the simulation by 1 step, observe again, then "
            "predict the direction of change for each molecule."
        ),
        "constitution": "Make predictions based on observed trends.",
        "interface": {
            "actions": {
                "predict": {
                    "description": "Predict direction of change for a molecule",
                    "params": {"molecule": "str", "direction": "str"},
                    "cost": 0.0,
                },
            },
            "measurements": {
                "sample_substrate": {
                    "description": "Measure current concentrations",
                    "params": {"region": "str"},
                    "cost": 0,
                },
            },
            "budget": 50,
        },
        "sim": {"max_agent_steps": 20, "steps_per_action": 1},
        "containers": {
            "regions": {
                "reactor": {"substrate": {"A": 10.0, "B": 0.0}},
            },
        },
        "scoring": {},
        "passing_score": 0.6,
        "_ground_truth_": {
            "reactions": [{"from": "A", "to": "B", "rate": 0.5}],
            "expected_directions": {"A": "decrease", "B": "increase"},
        },
    }


def h3_control_interface() -> dict[str, Any]:
    """H3: Follow explicit tool instructions.

    Agent must execute a specific sequence: observe, act, observe, report.
    Tests that the agent can use the interface correctly.
    """
    return {
        "name": "h3_control",
        "briefing": (
            "Follow these instructions exactly:\n"
            "1. Use sample_substrate to observe region 'main'\n"
            "2. Use add_feedstock with molecule='X' amount=5.0\n"
            "3. Use sample_substrate to observe region 'main' again\n"
            "4. Use submit_report with your observations"
        ),
        "constitution": "Follow instructions precisely.",
        "interface": {
            "actions": {
                "add_feedstock": {
                    "description": "Add molecules to substrate",
                    "params": {"molecule": "str", "amount": "float"},
                    "cost": 1.0,
                },
                "submit_report": {
                    "description": "Submit a text report",
                    "params": {"report": "str"},
                    "cost": 0.0,
                },
            },
            "measurements": {
                "sample_substrate": {
                    "description": "Measure concentrations",
                    "params": {"region": "str"},
                    "cost": 0,
                },
            },
            "budget": 50,
        },
        "sim": {"max_agent_steps": 10, "steps_per_action": 1},
        "containers": {
            "regions": {
                "main": {"substrate": {"X": 1.0, "Y": 2.0}},
            },
        },
        "scoring": {},
        "passing_score": 0.8,
        "_ground_truth_": {
            "expected_sequence": [
                "sample_substrate",
                "add_feedstock",
                "sample_substrate",
                "submit_report",
            ],
        },
    }


def h4_goal_directed() -> dict[str, Any]:
    """H4: Achieve a stated goal with one intervention.

    Agent must increase molecule X concentration by 50%.
    """
    return {
        "name": "h4_goal",
        "briefing": (
            "Your goal: increase the concentration of molecule X in the "
            "reactor from 10.0 to at least 15.0 (a 50% increase). "
            "You can add feedstock or adjust conditions. "
            "Use measurements to verify your result."
        ),
        "constitution": "Achieve the goal efficiently.",
        "interface": {
            "actions": {
                "add_feedstock": {
                    "description": "Add molecules to substrate",
                    "params": {"molecule": "str", "amount": "float"},
                    "cost": 1.0,
                },
                "adjust_conditions": {
                    "description": "Adjust environmental conditions",
                    "params": {"parameter": "str", "value": "float"},
                    "cost": 2.0,
                },
            },
            "measurements": {
                "sample_substrate": {
                    "description": "Measure concentrations",
                    "params": {"region": "str"},
                    "cost": 0,
                },
            },
            "budget": 50,
        },
        "sim": {"max_agent_steps": 20, "steps_per_action": 1},
        "containers": {
            "regions": {
                "reactor": {"substrate": {"X": 10.0, "Y": 5.0}},
            },
        },
        "scoring": {},
        "passing_score": 0.7,
        "_ground_truth_": {
            "target_molecule": "X",
            "target_concentration": 15.0,
            "initial_concentration": 10.0,
        },
    }


def h5_hypothesis_formation() -> dict[str, Any]:
    """H5: Discover a hidden reaction through experimentation.

    The world has a hidden reaction. Agent can set concentrations
    and observe what happens, then submit a hypothesis.
    """
    return {
        "name": "h5_hypothesis",
        "briefing": (
            "This system has an unknown reaction occurring. "
            "Design experiments to discover what it is: "
            "set concentrations, run the simulation, and observe changes. "
            "Then submit your hypothesis about the reaction."
        ),
        "constitution": "Use the scientific method.",
        "interface": {
            "actions": {
                "set_concentration": {
                    "description": "Set a molecule's concentration",
                    "params": {"molecule": "str", "amount": "float"},
                    "cost": 1.0,
                },
                "submit_hypothesis": {
                    "description": "Submit hypothesis about the hidden reaction",
                    "params": {"reactants": "str", "products": "str"},
                    "cost": 0.0,
                },
            },
            "measurements": {
                "sample_substrate": {
                    "description": "Measure all concentrations",
                    "params": {"region": "str"},
                    "cost": 0,
                },
            },
            "budget": 100,
        },
        "sim": {"max_agent_steps": 30, "steps_per_action": 5},
        "containers": {
            "regions": {
                "lab": {"substrate": {"P": 0.0, "Q": 0.0, "R": 0.0}},
            },
        },
        "scoring": {},
        "passing_score": 0.5,
        "_ground_truth_": {
            "hidden_reaction": {"reactants": ["P", "Q"], "products": ["R"], "rate": 0.3},
        },
    }


ALL_HELLO_WORLD = [
    h1_representation_comprehension,
    h2_dynamics_prediction,
    h3_control_interface,
    h4_goal_directed,
    h5_hypothesis_formation,
]
