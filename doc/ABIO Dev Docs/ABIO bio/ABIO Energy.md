---
description: "`energy`: opt-in free-energy accounting over a chemistry — `reaction_delta_g` from assigned formation energies, the spontaneity check (`check_energy` / `validate_energy`, `EnergyViolation`, `EnergyError`) and the `total_free_energy` canary over a world state. Source: `src/alienbio/bio/energy.py`."
---
:>>
# ABIO Energy
The page for `bio/energy.py`: how a reaction's free-energy change is booked from its molecules' assigned formation energies, the one constraint the module can enforce (an uncoupled reaction runs downhill), and the whole-state canary.

![ABIO Energy](ABIO%20Energy.svg) 
*Heat-sink accounting* is the topic behind the ‡ on `total_free_energy`: the module books ΔG against an implicit reservoir it never records, so the canary falls on every legitimate downhill step.

`energy.py` is the scalar sibling of [ABIO Conservation](ABIO%20Conservation.md), whose boundary test it imports. Nothing in `src/` imports it: its callers are `tests/unit/test_energy.py` and nothing else, so it is a library waiting for the Skeleton block that F018 names (coupled uphill work). The formation energies it reads are [ABIO MoleculeImpl](ABIO%20MoleculeImpl.md)'s `formation_energy`, the reactions [ABIO ReactionImpl](ABIO%20ReactionImpl.md), the chemistry [ABIO ChemistryImpl](ABIO%20ChemistryImpl.md), and the amounts the canary sums [ABIO WorldStateImpl](ABIO%20WorldStateImpl.md)'s. The subsystem view is [ABIO-Bio-Engine](../../ABIO%20Architecture/ABIO-Bio-Engine.md).



## energy Interface
Module-level functions over a `ChemistryImpl` and one over a `WorldStateImpl`. Energy is booked, not constrained, until a caller opts into `spontaneity`.

| energy | |
| --- | --- |
| [reaction_delta_g](#^reaction-delta-g) | ΔG of one reaction |
| [check_energy](#^check-energy) | Every uphill uncoupled reaction |
| [validate_energy](#^validate-energy) | Raise on any violation |
| [total_free_energy](#^total-free-energy) | Whole-state canary |
| [EnergyError](#^energyerror) | The refusal |

**reaction_delta_g**`(reaction: ReactionImpl) -> float`
    `Σ stoich · formation_energy` over products minus the same over reactants. A molecule whose `formation_energy` is `None` contributes `0.0`; modifiers are not consulted. Negative is exothermic (downhill). ^reaction-delta-g

**check_energy**`(chemistry, *, spontaneity=False, exempt_boundary=True) -> List[EnergyViolation]`
    With the default `spontaneity=False`, returns `[]` without looking at a reaction. With `spontaneity=True`, one `EnergyViolation` per reaction whose ΔG exceeds `_TOL` (1e-9), skipping boundary reactions (`conservation.is_boundary_reaction`) unless `exempt_boundary` is off. Never raises for content. ^check-energy

**validate_energy**`(chemistry, **kwargs) -> None`
    `check_energy` with the same keywords; raises `EnergyError` naming every violation and its ΔG. Called with no keywords it can never raise, because the default applies no constraint; a misspelled `spontaneity` is a `TypeError` from the inner call. ^validate-energy

**total_free_energy**`(state: WorldStateImpl, per_index_formation: List[float]) -> float`
    `Σ state.amount(c, j) · per_index_formation[j]` over every compartment and molecule index, skipping zero amounts. The caller builds the list in molecule-index order with `0.0` for an energy-neutral molecule. § [The canary](#the-canary). ^total-free-energy

**EnergyError**`(ValueError)`
    Raised by `validate_energy`; nothing in `src/` catches it. ^energyerror



## EnergyViolation Interface
A frozen dataclass: one reaction that failed the spontaneity check.

| EnergyViolation | |
| --- | --- |
| [reaction](#^reaction) | The reaction's name in the chemistry |
| [delta_g](#^delta-g) | Its ΔG, positive |
| [reason](#^reason) | Always the uphill message |

**reaction**`: str`
    The key the reaction has in `chemistry.reactions`. ^reaction

**delta_g**`: float`
    The reaction's ΔG, above `_TOL`. ^delta-g

**reason**`: str`
    `"uncoupled reaction runs uphill (ΔG > 0)"`, the only violation the module defines. ^reason




# Energy Semantics

## Heat-sink accounting
Each reaction's ΔG is taken to flow to or from an implicit heat reservoir (F018 Q1, form A). The books are said to balance against that reservoir, but the module keeps no ledger of it: nothing records the heat a step released. The only constraint it offers is spontaneity, that an uncoupled internal reaction runs downhill. Formation energies are assigned scalars, never derived from atoms or bonds (F018 Q2), so ΔG is whatever the generator chose.



## Boundary reactions and modifiers
A source (`∅ → X`) or sink (`X → ∅`) exchanges with the environment and is skipped under `exempt_boundary`, by the same structural test the conservation check uses ([ABIO Conservation](ABIO%20Conservation.md) § Boundary reactions). Modifiers (catalysts, regulators) are not stoichiometric and never enter ΔG.



## The canary
`total_free_energy` is the extensive free energy of a state. Its docstring calls it invariant across steps for a closed, balanced system; that holds only when every reaction has ΔG = 0, which is what the module's own test builds. Under the heat-sink form a downhill reaction lowers the total by `extent · |ΔG|` each step, correctly: a single `A → B` with formation energies 2 and 1 took the total from 2.0 to 1.349 in ten steps at `038c399`. With no reservoir term to add back, the canary cannot tell that loss from a leak, so on any chemistry the spontaneity check would accept it reports drift.



## Coupling, not built
The docstring sketches the extension: an energy-carrier species (an ATP analogue) whose consumption lets an uphill reaction run, with a `couple(reaction, carrier, n)` helper computing the coupled ΔG and a way for `check_energy` to know which reactions are coupled. None of it exists; until it does, `spontaneity=True` refuses every uphill internal reaction.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`). Checked locally against the export: the default returning `[]` on an uphill reaction, the uphill violation under `spontaneity=True`, a misspelled keyword raising `TypeError`, and the canary's drift on a downhill `A → B` run through `WorldSimulatorImpl`. Callers found by grep over `src/` and `tests/`. Not determined: whether F018's coupling step is still planned. Findings filed on T088.
