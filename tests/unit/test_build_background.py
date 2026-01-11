"""Tests for Generator M2.9: Background Generation.

These tests define expected behavior for generating random filler molecules
and reactions that respect guards.

Test categories:
- M2.9.1: Background section parsing
- M2.9.2: Background molecule generation
- M2.9.3: Background reaction generation with guards
"""

from __future__ import annotations

import pytest


# =============================================================================
# M2.9.1 - Background Section Parsing
# =============================================================================


class TestBackgroundParsing:
    """Tests for parsing background: section."""

    @pytest.mark.skip(reason="M2.9 not yet implemented")
    def test_parse_background_section(self):
        """Parse background section with molecule and reaction counts."""
        from alienbio.build import parse_background

        bg = parse_background({
            "molecules": {"count": 10},
            "reactions": {"count": 5}
        })

        assert bg["molecules"]["count"] == 10
        assert bg["reactions"]["count"] == 5

    @pytest.mark.skip(reason="M2.9 not yet implemented")
    def test_parse_background_with_distribution(self):
        """Parse background with distribution for count."""
        from alienbio.build import parse_background

        bg = parse_background({
            "molecules": {"count": "!ev normal(10, 2)"},
            "reactions": {"count": "!ev uniform(3, 8)"}
        })

        assert "count" in bg["molecules"]
        assert "count" in bg["reactions"]


# =============================================================================
# M2.9.2 - Background Molecule Generation
# =============================================================================


class TestBackgroundMolecules:
    """Tests for background molecule generation."""

    @pytest.mark.skip(reason="M2.9 not yet implemented")
    def test_background_generates_molecules(self):
        """Background generates approximately N molecules."""
        from alienbio import Bio, bio
        from alienbio.build import TemplateRegistry

        spec = {
            "background": {
                "molecules": {"count": 10}
            }
        }

        scenario = bio.build(spec, seed=42, registry=TemplateRegistry())

        # Should have approximately 10 background molecules
        gt = scenario._ground_truth_
        bg_mols = [m for m in gt["molecules"] if m.startswith("m.bg.")]
        assert len(bg_mols) == 10

    @pytest.mark.skip(reason="M2.9 not yet implemented")
    def test_background_molecules_use_bg_namespace(self):
        """Background molecules use m.bg.* namespace."""
        from alienbio import Bio, bio
        from alienbio.build import TemplateRegistry

        spec = {
            "background": {
                "molecules": {"count": 5}
            }
        }

        scenario = bio.build(spec, seed=42, registry=TemplateRegistry())

        gt = scenario._ground_truth_
        for mol in gt["molecules"]:
            if "bg" in mol:
                assert mol.startswith("m.bg.")

    @pytest.mark.skip(reason="M2.9 not yet implemented")
    def test_background_molecule_count_from_distribution(self):
        """Background molecule count sampled from distribution."""
        from alienbio import Bio, bio
        from alienbio.build import TemplateRegistry

        spec = {
            "background": {
                "molecules": {"count": "!ev normal(10, 2)"}
            }
        }

        # Run multiple times to check variation
        counts = []
        for seed in range(42, 52):
            scenario = bio.build(spec, seed=seed, registry=TemplateRegistry())
            gt = scenario._ground_truth_
            bg_mols = [m for m in gt["molecules"] if m.startswith("m.bg.")]
            counts.append(len(bg_mols))

        # Should have variation (not all same)
        assert len(set(counts)) > 1


# =============================================================================
# M2.9.3 - Background Reaction Generation with Guards
# =============================================================================


class TestBackgroundReactions:
    """Tests for background reaction generation."""

    @pytest.mark.skip(reason="M2.9 not yet implemented")
    def test_background_generates_reactions(self):
        """Background generates reactions between background molecules."""
        from alienbio import Bio, bio
        from alienbio.build import TemplateRegistry

        spec = {
            "background": {
                "molecules": {"count": 5},
                "reactions": {"count": 3}
            }
        }

        scenario = bio.build(spec, seed=42, registry=TemplateRegistry())

        gt = scenario._ground_truth_
        bg_rxns = [r for r in gt["reactions"] if r.startswith("r.bg.")]
        assert len(bg_rxns) == 3

    @pytest.mark.skip(reason="M2.9 not yet implemented")
    def test_background_reactions_use_bg_molecules(self):
        """Background reactions only use background molecules."""
        from alienbio import Bio, bio
        from alienbio.build import TemplateRegistry

        spec = {
            "background": {
                "molecules": {"count": 5},
                "reactions": {"count": 3}
            }
        }

        scenario = bio.build(spec, seed=42, registry=TemplateRegistry())

        gt = scenario._ground_truth_
        for rxn_name, rxn_data in gt["reactions"].items():
            if rxn_name.startswith("r.bg."):
                for reactant in rxn_data.get("reactants", []):
                    assert reactant.startswith("m.bg.")
                for product in rxn_data.get("products", []):
                    assert product.startswith("m.bg.")

    @pytest.mark.skip(reason="M2.9 not yet implemented")
    def test_background_respects_no_species_dependencies(self):
        """Background reactions don't link different species."""
        from alienbio import Bio, bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("species", parse_template({
            "molecules": {"M1": {}}
        }))

        spec = {
            "_instantiate_": {
                "_as_ Krel": {"_template_": "species"},
                "_as_ Kova": {"_template_": "species"},
            },
            "background": {
                "molecules": {"count": 5},
                "reactions": {"count": 3}
            },
            "_guards_": ["no_new_species_dependencies"]
        }

        scenario = bio.build(spec, seed=42, registry=registry)

        # Background reactions should not link Krel and Kova
        gt = scenario._ground_truth_
        for rxn_name, rxn_data in gt["reactions"].items():
            if rxn_name.startswith("r.bg."):
                all_mols = rxn_data.get("reactants", []) + rxn_data.get("products", [])
                species = set()
                for mol in all_mols:
                    parts = mol.split(".")
                    if len(parts) >= 2 and parts[1] not in ("bg",):
                        species.add(parts[1])
                # Should not have molecules from multiple species
                assert len(species) <= 1
