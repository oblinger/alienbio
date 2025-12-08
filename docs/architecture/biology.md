# Biology - Biological System Description

All classes that describe a biological system: the molecules, reactions, pathways, and structures that make up alien life.

**Parent**: [[alienbio]]

## Molecules (Rust)
Chemical compounds in the alien biology.
- **[[BioMolecule]]** - Chemical compound with atoms, bonds, and properties. Organized by biosynthetic depth.
- **[[MoleculeGenerator]]** - Factory that produces molecules matching statistical distributions from KEGG.

## Reactions (Rust)
Transformations between molecules.
- **[[BioReaction]]** - Transformation with reactants, products, effectors, and rate functions.
- **[[ReactionGenerator]]** - Factory that produces reactions matching template distributions.

## Pathways (Rust)
Connected sequences of reactions.
- **[[Pathway]]** - Connected subgraph forming a metabolic function: linear chains, branching paths, cycles, or signaling cascades.

## Containers (Rust)
Nestable biological structures from organelles to organisms.
- **[[BioContainer]]** - Nestable container for molecules, reactions, and child containers. Kind labels: organism, organ, cell, organelle.
- **[[SystemGenerator]]** - Factory that assembles complete container hierarchies from molecules and reactions.
