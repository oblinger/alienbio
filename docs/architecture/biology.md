# Biology - Biological System Description

All classes that describe a biological system: the molecules, reactions, pathways, and structures that make up alien life.

**Parent**: [[alienbio]]

## Molecules
Chemical compounds in the alien biology.
- **[[BioMolecule]]** - Chemical compound with atoms, bonds, and properties. Organized by biosynthetic depth.
- **[[MoleculeGenerator]]** - Factory that produces molecules matching statistical distributions from KEGG.

## Reactions
Transformations between molecules.
- **[[BioReaction]]** - Transformation with reactants, products, effectors, and rate functions.
- **[[ReactionGenerator]]** - Factory that produces reactions matching template distributions.

## Pathways
Connected sequences of reactions.
- **[[Pathway]]** - Connected subgraph forming a metabolic function: linear chains, branching paths, cycles, or signaling cascades.

## Systems
Compartmentalized biological structures.
- **[[BioSystem]]** - DAG of bioparts with molecule concentrations per compartment.
- **[[SystemGenerator]]** - Factory that assembles complete systems from molecules and reactions.

## Organisms
Complete biological entities.
- **[[BioOrganism]]** - Complete organism with hierarchical compartments, cross-compartment transport, and homeostatic targets.
