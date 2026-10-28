"""Module-doc findings on ``world.build_tree``: a duplicate compartment id
refuses, naming it.

Repro (before the fix): two compartments sharing an id were silently
overwritten in ``build_tree``'s id map and the world then failed with
``KeyError: 1`` building its compartment axis.
"""

from __future__ import annotations

import pytest

from alienbio.bio.world import Compartment, build_tree


def test_a_duplicate_compartment_id_refuses_naming_it() -> None:
    comps = (
        Compartment("root", None, "env", 1.0),
        Compartment("cell", "root", "cell", 1.0),
        Compartment("cell", "root", "cell", 1.0),
    )
    with pytest.raises(ValueError, match="duplicate compartment id 'cell'"):
        build_tree(comps)
