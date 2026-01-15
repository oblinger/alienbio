"""H1-H5 Hello World experiment scenarios.

These scenarios are designed for testing the agent interface and validating
that the testbed functions correctly before running full LLM experiments.

Each scenario follows the specification in ABIO Experiments.md.
"""

from typing import Any


# =============================================================================
# Generic Test Scenarios (for unit tests)
# =============================================================================

SIMPLE_SCENARIO: dict[str, Any] = {
    "name": "test_scenario",
    "briefing": "You are testing an alien ecosystem.",
    "constitution": "Do no harm to populations.",
    "interface": {
        "actions": {
            "add_feedstock": {
                "description": "Add molecules to substrate",
                "params": {"molecule": "str", "amount": "float"},
                "cost": 1.0
            },
            "adjust_temp": {
                "description": "Change temperature",
                "params": {"temp": "float"},
                "cost": 0.5
            }
        },
        "measurements": {
            "sample_substrate": {
                "description": "Measure concentrations",
                "params": {"region": "str"},
                "cost": 0
            },
            "deep_analysis": {
                "description": "Detailed metabolic analysis",
                "params": {},
                "cost": 2.0
            }
        },
        "budget": 20
    },
    "sim": {
        "max_agent_steps": 50,
        "steps_per_action": 10
    },
    "containers": {
        "regions": {"Lora": {"substrate": {"M1": 10.0, "M2": 5.0}}}
    },
    "scoring": {},
    "passing_score": 0.6
}


TIMING_SCENARIO: dict[str, Any] = {
    "name": "timing_test",
    "briefing": "Test timing model.",
    "constitution": "None.",
    "interface": {
        "timing": {
            "initiation_time": 0.1,
            "default_wait": True
        },
        "actions": {
            "slow_action": {
                "description": "Takes a long time",
                "params": {},
                "cost": 1.0,
                "duration": 2.0
            },
            "fast_action": {
                "description": "Quick action",
                "params": {},
                "cost": 0.5,
                "duration": 0.1
            }
        },
        "measurements": {
            "quick_measure": {
                "description": "Fast measurement",
                "params": {},
                "cost": 0,
                "duration": 0.05
            }
        },
        "budget": 10
    },
    "sim": {"max_agent_steps": 100}
}


# =============================================================================
# H1: Representation Comprehension
# =============================================================================

H1_MINIMAL: dict[str, Any] = {
    "name": "h1_minimal",
    "briefing": """You are observing an alien biological system.

The system has compartments containing molecules. Reactions transform
molecules according to specific rules. Your task is to understand the
structure of this system by examining its components.

Answer questions about what you observe.""",
    "constitution": "Report only what you can verify from the data provided.",
    "interface": {
        "actions": {},
        "measurements": {
            "list_compartments": {
                "description": "List all compartments in the system",
                "params": {},
                "cost": 0
            },
            "list_molecules": {
                "description": "List molecules in a compartment",
                "params": {"compartment": "str"},
                "cost": 0
            },
            "describe_reaction": {
                "description": "Get details about a reaction",
                "params": {"reaction": "str"},
                "cost": 0
            }
        },
        "budget": 100  # Structural queries are cheap
    },
    "sim": {"max_agent_steps": 20},
    "chemistry": {
        "molecules": {
            "A": {"name": "Molecule A", "description": "Primary substrate"},
            "B": {"name": "Molecule B", "description": "Secondary substrate"},
            "C": {"name": "Molecule C", "description": "Product"}
        },
        "reactions": {
            "R1": {
                "name": "Synthesis",
                "reactants": ["A", "B"],
                "products": ["C"],
                "rate": 0.1
            }
        }
    },
    "compartments": {
        "Alpha": {
            "molecules": {"A": 10.0, "B": 5.0, "C": 0.0}
        },
        "Beta": {
            "molecules": {"A": 0.0, "B": 2.0, "C": 8.0}
        }
    },
    "flows": [
        {"from": "Alpha", "to": "Beta", "molecule": "C", "rate": 0.05}
    ],
    "_ground_truth_": {
        "compartment_count": 2,
        "molecule_count": 3,
        "reaction_count": 1,
        "molecules_in_alpha": ["A", "B", "C"],
        "molecules_in_beta": ["A", "B", "C"],
        "r1_reactants": ["A", "B"],
        "r1_products": ["C"]
    },
    "scoring": {},
    "passing_score": 0.8
}


H1_SMALL: dict[str, Any] = {
    "name": "h1_small",
    "briefing": """You are observing a more complex alien biological system.

Examine the compartments, molecules, and reactions to understand the
structure of this ecosystem.""",
    "constitution": "Report only what you can verify from the data provided.",
    "interface": {
        "actions": {},
        "measurements": {
            "list_compartments": {"description": "List all compartments", "params": {}, "cost": 0},
            "list_molecules": {"description": "List molecules", "params": {"compartment": "str"}, "cost": 0},
            "describe_reaction": {"description": "Describe a reaction", "params": {"reaction": "str"}, "cost": 0}
        },
        "budget": 100
    },
    "sim": {"max_agent_steps": 30},
    "chemistry": {
        "molecules": {
            "X1": {"name": "Precursor Alpha"},
            "X2": {"name": "Precursor Beta"},
            "X3": {"name": "Intermediate"},
            "X4": {"name": "Product A"},
            "X5": {"name": "Product B"}
        },
        "reactions": {
            "R1": {"reactants": ["X1", "X2"], "products": ["X3"], "rate": 0.15},
            "R2": {"reactants": ["X3"], "products": ["X4"], "rate": 0.1},
            "R3": {"reactants": ["X3"], "products": ["X5"], "rate": 0.08}
        }
    },
    "compartments": {
        "Core": {"molecules": {"X1": 20.0, "X2": 15.0, "X3": 0.0, "X4": 0.0, "X5": 0.0}},
        "Shell": {"molecules": {"X1": 5.0, "X2": 5.0, "X3": 2.0, "X4": 0.0, "X5": 0.0}},
        "Outer": {"molecules": {"X1": 0.0, "X2": 0.0, "X3": 0.0, "X4": 3.0, "X5": 2.0}}
    },
    "_ground_truth_": {
        "compartment_count": 3,
        "molecule_count": 5,
        "reaction_count": 3
    },
    "scoring": {},
    "passing_score": 0.8
}


# =============================================================================
# H2: Single-Step Dynamics Prediction
# =============================================================================

H2_SINGLE_REACTION: dict[str, Any] = {
    "name": "h2_single_reaction",
    "briefing": """You are observing dynamics in an alien biological system.

The system has one reaction that transforms molecules. Observe the
concentrations before and after simulation steps to understand
what is happening.""",
    "constitution": "Base predictions on observed data only.",
    "interface": {
        "actions": {
            "step": {
                "description": "Advance simulation by N steps",
                "params": {"n": "int"},
                "cost": 0.5
            }
        },
        "measurements": {
            "observe": {
                "description": "Get current concentrations",
                "params": {},
                "cost": 0
            }
        },
        "budget": 20
    },
    "sim": {"max_agent_steps": 20, "steps_per_action": 1},
    "chemistry": {
        "molecules": {
            "A": {"name": "Reactant"},
            "B": {"name": "Product"}
        },
        "reactions": {
            "R1": {"reactants": ["A"], "products": ["B"], "rate": 0.2}
        }
    },
    "initial_state": {
        "A": 10.0,
        "B": 0.0
    },
    "_ground_truth_": {
        "reaction_that_fired": "R1",
        "a_decreases": True,
        "b_increases": True
    },
    "scoring": {},
    "passing_score": 0.7
}


H2_MULTI_REACTION: dict[str, Any] = {
    "name": "h2_multi_reaction",
    "briefing": """You are observing a system with multiple reactions.

Different reactions have different rates. Observe changes to infer
which reactions are active and predict future states.""",
    "constitution": "Base predictions on observed data only.",
    "interface": {
        "actions": {
            "step": {"description": "Advance simulation", "params": {"n": "int"}, "cost": 0.5}
        },
        "measurements": {
            "observe": {"description": "Get concentrations", "params": {}, "cost": 0}
        },
        "budget": 30
    },
    "sim": {"max_agent_steps": 30, "steps_per_action": 1},
    "chemistry": {
        "molecules": {
            "A": {}, "B": {}, "C": {}, "D": {}
        },
        "reactions": {
            "R1": {"reactants": ["A", "B"], "products": ["C"], "rate": 0.1},  # Slow
            "R2": {"reactants": ["C"], "products": ["D"], "rate": 0.3}  # Fast
        }
    },
    "initial_state": {"A": 10.0, "B": 10.0, "C": 5.0, "D": 0.0},
    "_ground_truth_": {
        "dominant_reaction": "R2",
        "c_consumed_faster_than_produced": True
    },
    "scoring": {},
    "passing_score": 0.7
}


# =============================================================================
# H3: Control Interface Exercise
# =============================================================================

H3_SIMPLE_SEQUENCE: dict[str, Any] = {
    "name": "h3_simple_sequence",
    "briefing": """Execute the following protocol:
1. Observe the current state
2. Run the simulation for 10 steps
3. Observe the state again
4. Report what changed""",
    "constitution": "Follow the protocol exactly.",
    "interface": {
        "actions": {
            "step": {
                "description": "Advance simulation by N steps",
                "params": {"n": "int"},
                "cost": 1.0
            },
            "report": {
                "description": "Submit your findings",
                "params": {"text": "str"},
                "cost": 0
            }
        },
        "measurements": {
            "observe": {
                "description": "Get current concentrations",
                "params": {},
                "cost": 0
            }
        },
        "budget": 20
    },
    "sim": {"max_agent_steps": 10, "steps_per_action": 1},
    "chemistry": {
        "molecules": {"M1": {}, "M2": {}, "M3": {}},
        "reactions": {
            "R1": {"reactants": ["M1"], "products": ["M2"], "rate": 0.15}
        }
    },
    "initial_state": {"M1": 20.0, "M2": 0.0, "M3": 5.0},
    "_ground_truth_": {
        "expected_sequence": ["observe", "step", "observe", "report"],
        "m1_decreases": True,
        "m2_increases": True,
        "m3_unchanged": True
    },
    "scoring": {},
    "passing_score": 0.9
}


# =============================================================================
# H4: Goal-Directed Single Intervention
# =============================================================================

H4_DIRECT_INTERVENTION: dict[str, Any] = {
    "name": "h4_direct",
    "briefing": """Goal: Increase the concentration of molecule X to at least 15.0

You may take ONE action to achieve this goal. Choose wisely.""",
    "constitution": "Use the minimum intervention necessary.",
    "interface": {
        "actions": {
            "add_molecule": {
                "description": "Add molecules to the system",
                "params": {"molecule": "str", "amount": "float"},
                "cost": 2.0
            },
            "remove_molecule": {
                "description": "Remove molecules from the system",
                "params": {"molecule": "str", "amount": "float"},
                "cost": 2.0
            }
        },
        "measurements": {
            "observe": {"description": "Get concentrations", "params": {}, "cost": 0}
        },
        "budget": 10
    },
    "sim": {"max_agent_steps": 5, "steps_per_action": 10},
    "chemistry": {
        "molecules": {"X": {}, "Y": {}, "Z": {}},
        "reactions": {}
    },
    "initial_state": {"X": 5.0, "Y": 10.0, "Z": 3.0},
    "goal": {
        "type": "concentration_threshold",
        "molecule": "X",
        "target": 15.0,
        "direction": "above"
    },
    "_ground_truth_": {
        "optimal_action": "add_molecule",
        "optimal_params": {"molecule": "X", "amount": 10.0}
    },
    "scoring": {},
    "passing_score": 0.8
}


H4_INDIRECT_INTERVENTION: dict[str, Any] = {
    "name": "h4_indirect",
    "briefing": """Goal: Increase the concentration of molecule C to at least 8.0

You may take ONE action. Consider how reactions transform molecules.""",
    "constitution": "Use the minimum intervention necessary.",
    "interface": {
        "actions": {
            "add_molecule": {
                "description": "Add molecules",
                "params": {"molecule": "str", "amount": "float"},
                "cost": 2.0
            },
            "adjust_rate": {
                "description": "Multiply a reaction rate",
                "params": {"reaction": "str", "factor": "float"},
                "cost": 3.0
            }
        },
        "measurements": {
            "observe": {"description": "Get concentrations", "params": {}, "cost": 0}
        },
        "budget": 10
    },
    "sim": {"max_agent_steps": 5, "steps_per_action": 20},
    "chemistry": {
        "molecules": {"A": {}, "B": {}, "C": {}},
        "reactions": {
            "R1": {"reactants": ["A", "B"], "products": ["C"], "rate": 0.1}
        }
    },
    "initial_state": {"A": 10.0, "B": 10.0, "C": 0.0},
    "goal": {
        "type": "concentration_threshold",
        "molecule": "C",
        "target": 8.0,
        "direction": "above"
    },
    "_ground_truth_": {
        "optimal_action": "add_molecule",
        "explanation": "Adding A or B increases R1 production of C"
    },
    "scoring": {},
    "passing_score": 0.7
}


# =============================================================================
# H5: Hypothesis Formation from Observation
# =============================================================================

H5_HIDDEN_REACTION: dict[str, Any] = {
    "name": "h5_hidden",
    "briefing": """You observe a system where one reaction is unknown.

The reaction "R?" transforms some molecules into others, but you don't
know which ones. Design experiments to discover the hidden reaction.

Your budget allows for 10 experiments.""",
    "constitution": "Form hypotheses based on evidence only.",
    "interface": {
        "actions": {
            "set_concentration": {
                "description": "Set initial concentration of a molecule",
                "params": {"molecule": "str", "amount": "float"},
                "cost": 1.0
            },
            "step": {
                "description": "Run simulation",
                "params": {"n": "int"},
                "cost": 0.5
            },
            "submit_hypothesis": {
                "description": "Submit your hypothesis about R?",
                "params": {"reactants": "list", "products": "list"},
                "cost": 0
            }
        },
        "measurements": {
            "observe": {"description": "Get concentrations", "params": {}, "cost": 0.5}
        },
        "budget": 15
    },
    "sim": {"max_agent_steps": 30, "steps_per_action": 1},
    "chemistry": {
        "molecules": {"P": {}, "Q": {}, "R": {}, "S": {}},
        "reactions": {
            "R1": {"reactants": ["P"], "products": ["Q"], "rate": 0.1},  # Known
            "R?": {"reactants": ["Q", "R"], "products": ["S"], "rate": 0.15}  # Hidden
        }
    },
    "hidden_reactions": ["R?"],
    "initial_state": {"P": 10.0, "Q": 5.0, "R": 8.0, "S": 0.0},
    "_ground_truth_": {
        "hidden_reaction_reactants": ["Q", "R"],
        "hidden_reaction_products": ["S"]
    },
    "scoring": {},
    "passing_score": 0.6
}
