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


# =============================================================================
# H3 - Deterministic per-species seed derivation
# =============================================================================


class TestSeedDeterminism:
    """Tests that per-species population seeds are stable (not PYTHONHASHSEED-dependent)."""

    def test_stable_hash_is_deterministic_and_not_builtin_hash(self):
        """_stable_hash gives a fixed, reproducible value independent of builtin hash()."""
        from alienbio.build.pipeline import _stable_hash

        # Same input always yields the same output within/across runs.
        assert _stable_hash("Krel") == _stable_hash("Krel")

        # Pinned expected value computed via sha256, independent of PYTHONHASHSEED.
        import hashlib

        expected = int(hashlib.sha256("Krel".encode("utf-8")).hexdigest(), 16) % 1000
        assert _stable_hash("Krel") == expected

    def test_population_seed_reproducible_across_hash_seeds(self):
        """Same seed must yield identical organism populations regardless of PYTHONHASHSEED.

        Regression test for H3: builtin hash(str) is salted per-process, so
        deriving per-species seeds from it made worlds non-reproducible across
        processes/machines even with a fixed seed.
        """
        import os
        import subprocess
        import sys
        from pathlib import Path

        script = (
            "from alienbio import bio\n"
            "from alienbio.build import parse_template, TemplateRegistry\n"
            "registry = TemplateRegistry()\n"
            "registry.register('producer', parse_template({'molecules': {'product': {}}}))\n"
            "registry.register('consumer', parse_template({'molecules': {'input': {}}}))\n"
            "spec = {\n"
            "    '_instantiate_': {\n"
            "        '_as_ Krel': {'_template_': 'producer'},\n"
            "        '_as_ Kova': {'_template_': 'consumer'},\n"
            "    },\n"
            "    'parameters': {\n"
            "        'containers': {\n"
            "            'regions': {'count': 1},\n"
            "            'populations': {'per_species_per_region': '!ev normal(10, 2)'},\n"
            "        }\n"
            "    },\n"
            "}\n"
            "scenario = bio.build(spec, seed=42, registry=registry)\n"
            "by_species = {}\n"
            "for region in scenario.regions:\n"
            "    for org in region.organisms:\n"
            "        by_species[org.species] = by_species.get(org.species, 0) + 1\n"
            "print(sorted(by_species.items()))\n"
        )

        def run_with_hashseed(hashseed: str) -> str:
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = hashseed
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(Path(__file__).resolve().parents[2]),
            )
            assert result.returncode == 0, result.stderr
            return result.stdout.strip()

        out_seed_1 = run_with_hashseed("1")
        out_seed_2 = run_with_hashseed("2")

        assert out_seed_1 == out_seed_2
