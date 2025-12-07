# Biology - Biological System Description

All classes that describe a biological system: the molecules, reactions, pathways, and structures that make up alien life.

**Parent**: [[alienbio|ALIEN BIO]]

## Molecules

Chemical compounds in the alien biology.

### [[bio_molecule|BioMolecule]]
Chemical compound with atoms, bonds, and properties. Organized by biosynthetic depth (bdepth).

### [[molecule_generator|MoleculeGenerator]]
Factory that produces molecules matching statistical distributions from KEGG.

## Reactions

Transformations between molecules.

### [[bio_reaction|BioReaction]]
Transformation with reactants, products, effectors, and rate functions. Classified as anabolic, catabolic, or energy.

### [[reaction_generator|ReactionGenerator]]
Factory that produces reactions matching template distributions.

## Pathways

Connected sequences of reactions.

### [[pathway|Pathway]]
Connected subgraph forming a metabolic function: linear chains, branching paths, cycles, or signaling cascades.

## Systems

Compartmentalized biological structures.

### [[bio_system|BioSystem]]
DAG of bioparts with molecule concentrations per compartment.

### [[system_generator|SystemGenerator]]
Factory that assembles complete systems from molecules and reactions.

## Organisms

Complete biological entities.

### [[bio_organism|BioOrganism]]
Complete organism with hierarchical compartments, cross-compartment transport, and homeostatic targets.
