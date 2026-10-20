:>> [[ABIO]] → [ABIO Log](ha://p/ABIO%20Log) 
# ABIO Log
The dated working log of the Alien Biology project, newest entry last.

## 2025-12-10



  Sources:
  - https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
  - https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk
  - https://www.anthropic.com/news/agent-capabilities-api
  - https://venturebeat.com/ai/anthropic-says-it-solved-the-long-running-ai-agent-problem-with-a-new-multi


## 2025-12-10  H3

### 2025-07-07  Plan


**Goal**:  Build templated test problems.

TEMPLATED GENERATORS:
- TEST: Sequence of test problems, each with an objective and laboratory
	- OBJECTIVE - Measurable outcome, success threshold, defined setup, with natural language description.
	- LABORATORY - Repeatable MCP protocol with
		- EQUIPMENT - Mass Spectrometer, Scalar Measurements (temperature, pressure, ph level, light level)
		- MATERIAL - Substrates, Strains, Compounds
- WORLD
	- ORGANISM - One or more behaviors and some distractors
	- BEHAVIOR - Homeostasis, Control, Sense/Act, Sense/Act Pair
	- PROCESSES - Anabolic, Catabolic, Metabolic
	- CHEMISTRY
	- BIOMOLECULES
	- ATOMS









1. [1d] TEMPLATES—Define the parametric pathway, e.g., the number of cycles and shunt paths, the steps in each, and the reactions in each step.
2. [1d] REACTIONS - Define goal-directed parametric chem reaction generator:  num inputs, outputs, tiny molecules, catalysts, bio-molecule reuse.
3. [2d] CODE GENERATORS -
4. [1d] HACK DATA - Eyeball terrestrial data to configure generators.
5. [2d] CODE INTERPRETER -
6. [1d] CODE SIMULATOR -
7. [??] CODE SIM TWEAKER -
- [ ] [??] Code: Task Generator with variable complexity (discovery only tasks)
- [ ] [3d] Code: MCP interface & API
- [ ] [2d] Code: Experiment #1


### 2025-05-13  KEGG Loader Instructions

yes, please provide a caching wrapper that I can re-run to retry. formulate it as a module with a main that I can run from command line to loads all required data printing basic progress. re-running should restart from where it left off.

Update Instructions:
Please use these updated classes to produce the BioMolecule/BioReaction DAG from local KEGG data, then scan that DAG to fill in bdepth and energy terms for molecules and reactions.  The idea is to produce a huge DAG over all KEGG data.
Please output code as a single module file

please use these updated classes in order to produce the BioMolecule/BioReaction DAG from local KEGG data, then scan that DAG to fill in bdepth and energy terms for molecules and reactions.  The idea is to produce a very large DAG over all KEGG data.

```


```
### 2025-05-13  KEGG Generation

Produce the Python code that we can use to parse the KEGG database into a DAG of BioMolecule and BioReaction classes, as shown below.  The write a function that traverses this DAG to fill in the bdepth of all BioMolecules.  Together we will download the data and run this code.

```Python

class BioMolecule(BaseModel):
    english_name: str
    chemical_name: str
    bdepth: int
    produced_by: List['BioReaction']
    consumed_by: List['BioReaction']


"""BDEPTH

Biosynthetic Depth (bdepth) is a measure of the complexity of a
  biomolecule as measured
by its shortest construction pathway from the organism's bio inputs.

- All bio inputs have a bdepth of 0.  These include: Essential
  Nutrients, Conditional
  Nutrients, Exogenous Compounds (signaling molecules, exenobiotics,
    food bioactives,  microbial/external metabolites, opportunistic
    molecular cues)- Each BioReaction has a bdepth that is 1 greater
    than the max bdepth of all of its
  reactants.
- The bdepth for all non-input BioMolecules is minimum bdepth of all
  BioReactions
  that produce this BioMolecule."""


class BioReaction(BaseModel):
    """A chemical reaction is a process that
        - consumes molecular input 'reactants' in order to        -
          produce the resultant molecular output 'products'.        - If
          multiple instances of a reactant or product are used/produced
          they are simply          listed repeatedly in the reactant /
          product lists.        - 'activation_energy' indicates the
          energy required to trigger the reaction        - 'net_energy'
          indicates the net energy produce or consumed by the reaction
          - 'effectors' are not consumed in the reaction but affect its
          reaction rate.lower required activation energy          These
          include: Catalysts, Enzymes, Co-Enzymes a kind of Co-Factor,
          Activators, Inhibitors, Alosteric Effectors, Co-Factors, Co-
          Enzyme,        - 'reaction_name' is the name typically used to
          refer to the reaction.        - Reactions that do not have an
          energy_source are typically exergonic while          those
          with a source are energonic.    """    reaction_name: str
    reactants: List[BioMolecule]        # All molecular inputs for a
      reaction
    products: List[BioMolecule]         # All molecular outputs for a
      reaction
    # solvent: List[BioMolecule]    # primary_reactants:
      List[BioMolecule]    # primary_products: List[BioMolecule]    #
      context: Temperature range, Ph range    effector:
      List[BioMolecule]         #
    activation_energy: Optional[float]
    delta_g: Optional[float]            # Expected negative change in
      gibbs free energy, Kj/mol
    energy_source: Optional['BioReaction']
    reaction_rate: Optional[ReactionRate]

```




### 2025-05-12  Brainstorm behavior generators

**Goal**:  build hard-structured behavior generators using gen-AI
**Example**:  Energy pathway generators.

- Learn about MCP interfaces and systems.


1. [1d] TEMPLATES—Define the parametric pathway, e.g., the number of cycles and shunt paths, the steps in each, and the reactions in each step.
2. [1d] REACTIONS - Define goal-directed parametric chem reaction generator:  num inputs, outputs, tiny molecules, catalysts, bio-molecule reuse.
3. [2d] CODE GENERATORS -
4. [1d] HACK DATA - Eyeball terrestrial data to configure generators.
5. [2d] CODE INTERPRETER -
6. [1d] CODE SIMULATOR -
7. [??] CODE SIM TWEAKER -
- [ ] [??] Code: Task Generator with variable complexity (discovery only tasks)
- [ ] [3d] Code: MCP interface & API
- [ ] [2d] Code: Experiment #1

#### BDEPTH

yes lets define biosynthetic depth (bdepth) recursively. Essential nutrients, small molecules, etc. have a bdepth of 0. Derived molecules have a depth 1 greater than the max bdepth of all inputs for the reaction that gives it the smallest possible depth.



-_biosynthetic depth_ or _metabolic tier_.
Essential Nutrient List
Derived Nutrients
Small molecules & Inputs
#### Molecular Generators
-
#### Anabolic Generators

- Pick one primary reactant
- 0, 1, or occasionally more other reactants
-


### 2025-05-07 Fast Path
- [ ] Code:  	Reactions Web Generator
- [ ] Code:  	Behavior Generators:  (1) Energy Transport,  (2) Anabolic Pathways,  (3) Cantbolic Pathways
- [ ] Code:	Simulators (just runs reactions and scripts)
- [ ] Code:	World Spec Generator.  Hard-coded generator of system behavioral targets
- [ ] Code:	Full world weaver, uses inputs above and simulator to produce full world system, and edit system until it behaves as expected.
- [ ] Code:	Disease Generator.  Systematically damages working behaviors io induce pathologies
- [ ] Code:	Task Generator with variable complexity
- [ ] Experiment #1:  Compare 10 Chat systems' ability to model production rates give changes of inputs
- [ ] Experiment #2:  Cure a disease.  Measure sthe system's performance at adjusting diseased systems to correct them.


### 2025-05-02  Nina Discussion


OpenAI -
Anthrompic
Collaborate a Bioligist
Systems Biology
Microsoft -




### [[ABIO Task Example]] 
### [[Measuring Intelligence]] 
### OUT TAKES


**Problem**: Because LLMs are constructed from such colossal training sets, it's hard to find tasks to assess their ability to perform truly novel reasoning as opposed to some sophisticated form copying from its training data.

**Problem**:  It is difficult to assess the learning/inference performance of LLMs over novel tasks since nearly any complex task we might use likely already has connections to texts used to train that model.  Perhaps all of its learning and inference are just sophisticated forms of copying.  How can we tell?


**Problem**: It's difficult to assess complex LLM reasoning since nearly any complex test task is tainted by likely but unknown relation to the texts used to train the LLM.
