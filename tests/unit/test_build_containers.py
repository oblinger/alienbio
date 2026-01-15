"""Tests for Generator M2.10: Container Generation.

These tests define expected behavior for generating regions and organism
populations from parameters.

Test categories:
- M2.10.1: Container parameter parsing
- M2.10.2: Region generation
- M2.10.3: Organism population generation
"""

from __future__ import annotations

import pytest


# =============================================================================
# M2.10.1 - Container Parameter Parsing
# =============================================================================


class TestContainerParsing:
    """Tests for parsing parameters.containers: section."""

    
    def test_parse_container_parameters(self):
        """Parse container parameters section."""
        from alienbio.build import parse_containers

        containers = parse_containers({
            "regions": {"count": 3},
            "populations": {
                "per_species_per_region": "!ev uniform(5, 15)"
            }
        })

        assert containers["regions"]["count"] == 3
        assert "per_species_per_region" in containers["populations"]


# =============================================================================
# M2.10.2 - Region Generation
# =============================================================================


class TestRegionGeneration:
    """Tests for region generation."""

    
    def test_generate_regions(self):
        """Generate N regions from regions.count parameter."""
        from alienbio import Bio, bio
        from alienbio.build import TemplateRegistry

        spec = {
            "parameters": {
                "containers": {
                    "regions": {"count": 3}
                }
            }
        }

        scenario = bio.build(spec, seed=42, registry=TemplateRegistry())

        # Should have 3 regions
        assert len(scenario.regions) == 3

    
    def test_regions_have_ids(self):
        """Generated regions have unique IDs."""
        from alienbio import Bio, bio
        from alienbio.build import TemplateRegistry

        spec = {
            "parameters": {
                "containers": {
                    "regions": {"count": 5}
                }
            }
        }

        scenario = bio.build(spec, seed=42, registry=TemplateRegistry())

        region_ids = [r.id for r in scenario.regions]
        assert len(region_ids) == len(set(region_ids))  # All unique

    
    def test_regions_have_substrate_concentrations(self):
        """Generated regions have initial substrate concentrations."""
        from alienbio import Bio, bio
        from alienbio.build import TemplateRegistry

        spec = {
            "parameters": {
                "containers": {
                    "regions": {
                        "count": 2,
                        "initial_substrates": {"nutrient": 100.0}
                    }
                }
            }
        }

        scenario = bio.build(spec, seed=42, registry=TemplateRegistry())

        for region in scenario.regions:
            assert "nutrient" in region.substrates


# =============================================================================
# M2.10.3 - Organism Population Generation
# =============================================================================


class TestPopulationGeneration:
    """Tests for organism population generation."""

    
    def test_generate_populations(self):
        """Generate organism populations in regions."""
        from alienbio import Bio, bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("species", parse_template({
            "molecules": {"M1": {}}
        }))

        spec = {
            "_instantiate_": {
                "_as_ Krel": {"_template_": "species"},
            },
            "parameters": {
                "containers": {
                    "regions": {"count": 2},
                    "populations": {
                        "per_species_per_region": 10
                    }
                }
            }
        }

        scenario = bio.build(spec, seed=42, registry=registry)

        # Should have organisms assigned to regions
        total_organisms = sum(len(r.organisms) for r in scenario.regions)
        assert total_organisms > 0

    
    def test_populations_sampled_from_distribution(self):
        """Populations sampled from distribution."""
        from alienbio import Bio, bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("species", parse_template({
            "molecules": {"M1": {}}
        }))

        spec = {
            "_instantiate_": {
                "_as_ Krel": {"_template_": "species"},
            },
            "parameters": {
                "containers": {
                    "regions": {"count": 1},
                    "populations": {
                        "per_species_per_region": "!ev normal(10, 2)"
                    }
                }
            }
        }

        # Run multiple times to check variation
        counts = []
        for seed in range(42, 52):
            scenario = bio.build(spec, seed=seed, registry=registry)
            count = sum(len(r.organisms) for r in scenario.regions)
            counts.append(count)

        # Should have variation
        assert len(set(counts)) > 1

    
    def test_populations_assigned_to_correct_species(self):
        """Populations assigned to correct species."""
        from alienbio import Bio, bio
        from alienbio.build import parse_template, TemplateRegistry

        registry = TemplateRegistry()
        registry.register("producer", parse_template({
            "molecules": {"product": {}}
        }))
        registry.register("consumer", parse_template({
            "molecules": {"input": {}}
        }))

        spec = {
            "_instantiate_": {
                "_as_ Krel": {"_template_": "producer"},
                "_as_ Kova": {"_template_": "consumer"},
            },
            "parameters": {
                "containers": {
                    "regions": {"count": 1},
                    "populations": {
                        "per_species_per_region": 5
                    }
                }
            }
        }

        scenario = bio.build(spec, seed=42, registry=registry)

        # Should have organisms of both species
        species_names = set()
        for region in scenario.regions:
            for org in region.organisms:
                species_names.add(org.species)

        assert "Krel" in species_names
        assert "Kova" in species_names
