[[ABIO docs]] → [[ABIO Topics]]
- [[Alien Vocabulary]] 

# Catalog Naming Scheme
Naming conventions for builder templates. These are `build()` targets with statistical distributions (`!ev`) that get instantiated into concrete objects.

## Directory Structure

```
<prefix>                  # Your chosen prefix (e.g., mutualism, simple_pred, std)
├── /mol                  # MOLECULE — molecular species templates
│   ├── /energy           #   energy molecules (ME prefix)
│   ├── /structural       #   structural molecules (MS prefix)
│   ├── /waste            #   waste products (MW prefix)
│   ├── /signaling        #   signaling molecules (MG prefix)
│   ├── /buffer           #   buffer molecules (MB prefix)
│   └── /catalyst         #   catalysts/enzymes (MC prefix)
├── /rxn                  # REACTION — biochemical reaction templates
│   ├── /synthesis        #   building (-genesis)
│   ├── /breakdown        #   decomposition (-lysis)
│   └── /transform        #   modification (-ation)
├── /path                 # PATHWAY — metabolic pathway templates
│   ├── /anabolic         #   building pathways
│   ├── /catabolic        #   breakdown pathways
│   ├── /cycle            #   cyclic pathways (Krebs, etc.)
│   └── /energy           #   energy pathways (photosynthesis, respiration)
├── /nel                  # ORGANELLE — subcellular structure templates
│   ├── /energy           #   energy organelles (mitochondria-like)
│   ├── /synthesis        #   protein synthesis (ribosome-like)
│   ├── /storage          #   storage organelles (vacuole-like)
│   └── /membrane         #   membrane systems (ER-like)
├── /organ                # ORGAN — organ/tissue templates
│   ├── /sensory          #   sensory organs
│   ├── /metabolic        #   metabolic organs
│   ├── /structural       #   structural organs
│   └── /reproductive     #   reproductive organs
├── /org                  # ORGANISM — complete living being templates
│   ├── /autotroph        #   self-feeding (produce energy)
│   ├── /heterotroph      #   feed on others
│   └── /decomposer       #   process waste
├── /eco                  # ECOSYSTEM — complete ecosystem templates
│   ├── /mutualism        #   cooperative relationships
│   ├── /predation        #   predator-prey systems
│   └── /competition      #   resource competition
├── /rel                  # RELATIONSHIP — inter-species interaction templates
│   ├── /predation        #   predator-prey dynamics
│   ├── /symbiosis        #   mutually dependent
│   └── /parasitism       #   parasitic extraction
└── /scenario             # SCENARIO — experiment/test scenario definitions
```



---

## Choosing a Prefix

Each template universe uses its own short prefix (2-4 characters). Prefixes are cryptic by design—they appear throughout thousands of references—so we maintain a registry for lookup.

### Prefix Registry

All prefixes are registered in `catalog/_index.yaml`:

```yaml
# catalog/_index.yaml
prefixes:
  test: {"name": "Test Fixtures",       "description": "Test scenarios, actions, and measurements"}
  mute: {"name": "Mutualism Baseline",  "description": "Two-species mutualistic ecosystem"}
  krel: {"name": "Krebs-like Cycle",    "description": "Circular metabolic pathway with energy coupling"}
  pred: {"name": "Predator-Prey",       "description": "Multi-species predator-prey food web dynamics"}
  comp: {"name": "Competition Arena",   "description": "Multi-species competition for limited resources"}
  std:  {"name": "Standard Library",    "description": "Reusable templates for common patterns"}
```

Access programmatically via `bio.fetch("catalog._index").prefixes`.

### Registering New Prefixes

When creating a new universe:
1. Choose a short, unused prefix (2-4 chars)
2. Add it to `catalog/_index.yaml` with name and description
3. Create the prefix folder in `catalog/`

The prefix becomes a folder in your source tree containing the structure below.


## Overview

Create a folder with your prefix name, then replicate the structure above for the components you need. All templates in that universe share the prefix.

```python
# Using a "mute" (mutualism) universe
bio.fetch("mute.mol.energy.ME_basic")
bio.fetch("mute.org.autotroph.krel")
bio.fetch("mute.eco.mutualism.two_species")

# Using a "pred" (predator-prey) universe
bio.fetch("pred.org.heterotroph.hunter")
bio.fetch("pred.rel.predation.ambush")
```

**Key principles:**
- Choose a short prefix for your universe (2-4 chars)
- Templates define statistical properties for `build()` to instantiate
- Names use lowercase with underscores (snake_case)

---

## Naming Patterns

### General Format

```
<prefix>.<category>.<subcategory>.<template_name>
```

Examples using `mute` prefix:
```
mute.mol.energy.ME_basic
mute.rxn.synthesis.ethogenesis
mute.path.anabolic.protein_synthesis
mute.org.autotroph.krel_photo
mute.eco.mutualism.two_species
```

### Molecules (`<prefix>.mol.*`)

Templates for molecular species with statistical properties.

| Pattern | Example | Description |
|---------|---------|-------------|
| `<prefix>.mol.energy.<name>` | `mute.mol.energy.ME_basic` | Energy molecules (ME prefix) |
| `<prefix>.mol.structural.<name>` | `mute.mol.structural.MS_membrane` | Structural molecules (MS prefix) |
| `<prefix>.mol.waste.<name>` | `mute.mol.waste.MW_standard` | Waste products (MW prefix) |
| `<prefix>.mol.signaling.<name>` | `mute.mol.signaling.MG_simple` | Signaling molecules (MG prefix) |
| `<prefix>.mol.buffer.<name>` | `mute.mol.buffer.MB_ph` | Buffer molecules (MB prefix) |
| `<prefix>.mol.catalyst.<name>` | `mute.mol.catalyst.MC_enzyme` | Catalysts/enzymes (MC prefix) |

```yaml
# mute/mol/energy/ME_basic.yaml
molecule.ME_basic:
  prefix: ME
  initial_count: !ev normal(100, 20)
  diffusion_rate: !ev uniform(0.1, 0.3)
  decay_rate: 0.01
```

### Reactions (`<prefix>.rxn.*`)

Templates for biochemical reactions.

| Pattern | Example | Description |
|---------|---------|-------------|
| `<prefix>.rxn.synthesis.<name>` | `mute.rxn.synthesis.ethogenesis` | Building reactions (-genesis) |
| `<prefix>.rxn.breakdown.<name>` | `mute.rxn.breakdown.ethalysis` | Decomposition reactions (-lysis) |
| `<prefix>.rxn.transform.<name>` | `mute.rxn.transform.ethylation` | Transformation reactions (-ation) |

```yaml
# mute/rxn/synthesis/ethogenesis.yaml
reaction.ethogenesis:
  type: synthesis
  inputs: [ME1, ME2]
  outputs: [MEtha]
  rate: !_ k * [ME1] * [ME2] / (Km + [ME1])
  energy_cost: 2.0
```

### Pathways (`<prefix>.path.*`)

Templates for metabolic pathways (sequences of reactions).

| Pattern | Example | Description |
|---------|---------|-------------|
| `<prefix>.path.anabolic.<name>` | `mute.path.anabolic.protein_synthesis` | Building pathways |
| `<prefix>.path.catabolic.<name>` | `mute.path.catabolic.glucose_breakdown` | Breakdown pathways |
| `<prefix>.path.cycle.<name>` | `mute.path.cycle.krel_cycle` | Cyclic metabolic pathways |

```yaml
# mute/path/anabolic/protein_synthesis.yaml
pathway.protein_synthesis:
  type: anabolic
  steps:
    - !ref mute.rxn.synthesis.amino_activation
    - !ref mute.rxn.synthesis.peptide_bond
    - !ref mute.rxn.transform.folding
  energy_requirement: 4.0
  products: [MSprotein]
```

### Organisms (`<prefix>.org.*`)

Templates for organism types with metabolic and behavioral properties.

| Pattern | Example | Description |
|---------|---------|-------------|
| `<prefix>.org.autotroph.<name>` | `mute.org.autotroph.krel_photo` | Self-feeding (produce energy) |
| `<prefix>.org.heterotroph.<name>` | `mute.org.heterotroph.kova_predator` | Feed on others |
| `<prefix>.org.decomposer.<name>` | `mute.org.decomposer.kesh_recycler` | Process waste |

```yaml
# mute/org/autotroph/krel_photo.yaml
organism.krel_photo:
  prefix: K
  metabolism:
    energy_pathway: !ref mute.path.energy.photosynthesis.standard
    anabolic: !ref mute.path.anabolic.carbon_fixation
  reproduction:
    rate: !ev uniform(0.05, 0.15)
    energy_cost: 10.0
  initial_population: !ev poisson(20)
```

### Ecosystems (`<prefix>.eco.*`)

Complete ecosystem templates with multiple species and interactions.

| Pattern | Example | Description |
|---------|---------|-------------|
| `<prefix>.eco.mutualism.<name>` | `mute.eco.mutualism.two_species` | Cooperative systems |
| `<prefix>.eco.predation.<name>` | `mute.eco.predation.food_chain` | Predator-prey systems |
| `<prefix>.eco.competition.<name>` | `mute.eco.competition.resource_limited` | Competitive systems |

```yaml
# mute/eco/mutualism/two_species.yaml
ecosystem.two_species_mutualism:
  organisms:
    producer: !ref mute.org.autotroph.krel_photo
    consumer: !ref mute.org.heterotroph.kova_grazer
  relationships:
    - type: mutualism
      species: [producer, consumer]
      mechanism: nutrient_exchange
  containers:
    shared_region:
      capacity: 1000
```

### Relationships (`<prefix>.rel.*`)

Templates for inter-species interactions.

| Pattern | Example | Description |
|---------|---------|-------------|
| `<prefix>.rel.predation.<name>` | `mute.rel.predation.standard` | Predator-prey dynamics |
| `<prefix>.rel.symbiosis.<name>` | `mute.rel.symbiosis.obligate` | Mutually dependent |
| `<prefix>.rel.parasitism.<name>` | `mute.rel.parasitism.energy_drain` | Parasitic extraction |

```yaml
# mute/rel/predation/standard.yaml
relationship.predation_standard:
  type: predation
  predator_efficiency: !ev uniform(0.3, 0.7)
  prey_escape_rate: !ev uniform(0.2, 0.5)
  energy_transfer: 0.1
```

---

## Usage Examples

### Fetching templates

```python
from alienbio import bio

# Fetch from "mute" universe
me_template = bio.fetch("mute.mol.energy.ME_basic")
krel = bio.fetch("mute.org.autotroph.krel_photo")
ecosystem = bio.fetch("mute.eco.mutualism.two_species")
```

### Building from templates

```python
# Build instantiates the template with random values from distributions
scenario = bio.build("mute.eco.mutualism.two_species", seed=42)

# Templates are expanded, !ev expressions evaluated
print(scenario.organisms["producer"].initial_population)  # e.g., 23
```

### Composing scenarios from templates

```yaml
# my_scenario.yaml
scenario.custom:
  chemistry:
    molecules:
      energy: !ref mute.mol.energy.ME_basic
      waste: !ref mute.mol.waste.MW_standard
    reactions:
      production: !ref mute.rxn.synthesis.ethogenesis
  organisms:
    primary: !ref mute.org.autotroph.krel_photo
  containers:
    main:
      organisms: [primary]
      initial_molecules:
        energy: !ev normal(100, 20)
```

---

## Project Structure

Your template universe lives in a folder named after your prefix:

```bash
my_project/
├── mute/              # Your "mute" universe
│   ├── mol/
│   │   └── energy/
│   ├── org/
│   │   └── autotroph/
│   └── eco/
│       └── mutualism/
├── experiments/
└── pyproject.toml
```

Templates are typically version-controlled with your project code to ensure consistency.

---

## Python Coexistence

YAML templates can coexist with Python code in the same directories. This enables computed templates and custom rate functions.

### File Priority

When both `krel_photo.yaml` and `krel_photo.py` exist in the same directory:
- **YAML takes precedence** — the `.yaml` file is loaded
- Python is only checked if no YAML file is found

### Python Templates

Python files can export templates as module globals:

```python
# mute/org/autotroph/krel_computed.py

# Dict format - used directly
KREL_COMPUTED = {
    "organism.krel_computed": {
        "prefix": "K",
        "metabolism": compute_metabolism(),
        "reproduction": {"rate": 0.1}
    }
}

# YAML string format - parsed like a YAML file
KREL_YAML = """yaml:
organism.krel_yaml:
  prefix: K
  metabolism: !py custom_rates.get_metabolism
"""
```

### The `!py` Tag

YAML templates can reference Python code using `!py`. The tag resolves relative to the YAML file's location:

```yaml
# mute/rxn/synthesis/complex_reaction.yaml
reaction.complex:
  inputs: [ME1, ME2]
  rate: !py rate_functions.michaelis_menten  # loads mute/rxn/synthesis/rate_functions.py
```

This keeps computation close to the templates that use it.

---

## See Also

- [[Alien Vocabulary]] — Naming conventions for organisms, molecules, reactions
- [[Core Spec]] — YAML foundations, tags, scoping
- [[Generator Spec]] — Template-based scenario generation
- [[Bio]] — Bio class methods including `fetch()` and `build()`
- [[ABIO Fetch]] — Data sources, resolution order, `!py` tag details
