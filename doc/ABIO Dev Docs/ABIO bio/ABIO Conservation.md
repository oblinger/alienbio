---
description: "`conservation`: the opt-in atom-balance check over a chemistry's reactions (`check_conservation` / `validate_conservation`, `BalanceViolation`, `ConservationError`), the `conservation_outcome` verdict that names a vacuous pass, the boundary-reaction exemption, and the `total_quantity` canary over a world state. Source: `src/alienbio/bio/conservation.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO Conservation](ha://p/ABIO%20Conservation) 
# ABIO Conservation
The page for `bio/conservation.py`: how a reaction's conserved-quantity vector is booked, which reactions are exempt, what the one gate that calls it (`Skeleton.validate`) actually checks and records, and the whole-state canary nothing in `src/` runs.

![ABIO Conservation](ABIO%20Conservation.svg) 
*Boundary reactions* is the topic behind the dotted exemption edge; *What the gate proves* governs the ‡ on the `Skeleton.validate` edge, which passes the defaults and so lets an atom-free reaction through; `conservation_outcome` (not drawn) is what says so.

`conservation.py` is a static check plus one reader of a state: it never runs inside a simulator step. Its only caller in `src/` is `Skeleton.validate` ([ABIO Skeleton](../ABIO%20suite/ABIO%20Skeleton.md)); `bio/energy.py` imports its boundary test; `bio/population.py` cites the canary in prose as the thing a population law deliberately breaks ([ABIO PopulationLaw](ABIO%20PopulationLaw.md)). The molecules it reads atoms from are [ABIO MoleculeImpl](ABIO%20MoleculeImpl.md) objects, the reactions [ABIO ReactionImpl](ABIO%20ReactionImpl.md), the chemistry [ABIO ChemistryImpl](ABIO%20ChemistryImpl.md), and the extensive `amount` the canary sums is [ABIO WorldStateImpl](ABIO%20WorldStateImpl.md)'s. Its scalar sibling for free energy is [ABIO Energy](ABIO%20Energy.md); the subsystem view is [ABIO-Bio-Engine](../../ABIO%20Architecture/ABIO-Bio-Engine.md).



## conservation Interface
Module-level functions over a `ChemistryImpl` and its reactions, and one over a `WorldStateImpl`. The conserved quantity is a callable argument, so atoms are only the default instance; a count-based quantity (biomass, headcount) plugs in without a change here.

| conservation | |
| --- | --- |
| [ConservedVector](#^conservedvector) | A label → amount mapping |
| [molecule_quantity](#^molecule-quantity) | A molecule's atoms as a vector |
| [is_boundary_reaction](#^is-boundary-reaction) | True when one side is empty |
| [reaction_imbalance](#^reaction-imbalance) | Net vector, products minus reactants |
| [check_conservation](#^check-conservation) | Every unbalanced reaction |
| [validate_conservation](#^validate-conservation) | Raise on any violation |
| [conservation_outcome](#^conservation-outcome) | What a clean pass established |
| [BALANCED / VACUOUS](#^balanced-vacuous) | The two fixed verdicts |
| [total_quantity](#^total-quantity) | Whole-state canary vector |
| [ConservationError](#^conservationerror) | The refusal |

**ConservedVector**` = Dict[str, float]`
    A conserved-quantity vector: an element symbol (or any other label a custom quantity uses) to its amount. ^conservedvector

**molecule_quantity**`(molecule: MoleculeImpl) -> ConservedVector`
    `{atom.symbol: float(count)}` over the molecule's atom composition; `{}` for a molecule with no atoms, which is every molecule a skeleton block mints. The default `quantity` of the two checks. ^molecule-quantity

**is_boundary_reaction**`(reaction: ReactionImpl) -> bool`
    True when the reaction has no reactants (a source, `∅ → X`) or no products (a sink, `X → ∅`). Such a reaction exchanges with the environment and is skipped by both checks when `exempt_boundary` is on, and by `energy.check_energy` too. § [Boundary reactions](#boundary-reactions). ^is-boundary-reaction

**reaction_imbalance**`(reaction, quantity=molecule_quantity) -> ConservedVector`
    Sums `stoich · quantity(mol)` over products minus the same over reactants, label by label, and returns only the labels whose net magnitude exceeds `_TOL` (1e-9, absolute). Empty means balanced. Modifiers are not consulted: they are neither consumed nor produced. ^reaction-imbalance

**check_conservation**`(chemistry, *, quantity=molecule_quantity, require_atoms=False, exempt_boundary=True) -> List[BalanceViolation]`
    One `BalanceViolation` per reaction of `chemistry.reactions` that is not balanced, `reason="not balanced"`. With `require_atoms`, a non-boundary reaction any of whose reactants or products carries an empty quantity is a violation instead (`reason` names them, `imbalance` is `{}`), so an atom-free molecule cannot pass by carrying nothing. With the default `False`, it does pass (§ [What the gate proves](#what-the-gate-proves)). Never raises for content. ^check-conservation

**validate_conservation**`(chemistry, **kwargs) -> None`
    `check_conservation` with the same keywords; raises `ConservationError` naming every violation (`"N reaction(s) violate conservation: …"`) when the list is non-empty. A misspelled keyword is a `TypeError` from the inner call. ^validate-conservation

**conservation_outcome**`(chemistry, *, quantity=molecule_quantity, exempt_boundary=True) -> str`
    Runs `check_conservation` with the defaults' `require_atoms=False` and names what the pass established: `"violated: N reaction(s)"` on any imbalance; `VACUOUS` when every checked internal reaction has no participant carrying a quantity; `"partial: K of N internal reactions carry no atoms"` when only some have none; `BALANCED` otherwise, including a chemistry with no internal reaction. `Skeleton.validate` stores it on `Skeleton.conservation`. Since `40c5c09`. § [What the gate proves](#what-the-gate-proves). ^conservation-outcome

**BALANCED**` = "balanced"`, **VACUOUS**` = "vacuous: no atoms"`
    The two fixed strings `conservation_outcome` returns; the `violated` and `partial` verdicts carry counts. ^balanced-vacuous

**total_quantity**`(state: WorldStateImpl, per_index_quantity: List[ConservedVector]) -> ConservedVector`
    Sums `state.amount(c, j) · per_index_quantity[j][label]` over every compartment and molecule index, skipping zero amounts. The caller builds `per_index_quantity` in molecule-index order; a shorter list raises `IndexError` only when a nonzero amount sits past its end. Called by tests only. § [The canary](#the-canary). ^total-quantity

**ConservationError**`(ValueError)`
    Raised by `validate_conservation`. `Skeleton.validate` catches it and folds its message into the `SkeletonError` it returns. ^conservationerror



## BalanceViolation Interface
A frozen dataclass: one reaction that failed the check.

| BalanceViolation | |
| --- | --- |
| [reaction](#^reaction) | The reaction's name in the chemistry |
| [imbalance](#^imbalance) | Net vector, `{}` for a missing quantity |
| [reason](#^reason) | Why it failed |

**reaction**`: str`
    The key the reaction has in `chemistry.reactions`. ^reaction

**imbalance**`: ConservedVector`
    The labels that do not net to zero, products minus reactants; `{}` on a `require_atoms` violation. ^imbalance

**reason**`: str`
    `"not balanced"`, or `"participants carry no conserved quantity: [names]"`. ^reason




# Conservation Semantics

## Boundary reactions
A reaction with an empty side is read as an exchange with the environment and skipped. The test is purely structural: a source, a sink, and an internal reaction whose product list was lost when it was authored (`A + B → ∅`) all look the same, and all pass. Every generated world carries sources and sinks (`SourceBlock`, `SinkBlock`, the feed inlets), so on those worlds the check covers the internal reactions only, which is the intent.



## What the gate proves
`Skeleton.validate` calls `validate_conservation(self.chemistry)` with the defaults (`skeleton.py:681`). Skeleton-minted molecules carry no atoms, so `molecule_quantity` is `{}` for every one, every internal reaction nets to `{}`, and the gate passes whatever the stoichiometry: `A → 2 B` and `A → ∅` read the same. A local check at `038c399` returned `[]` for an atom-free `X → Y` with the defaults and one violation with `require_atoms=True`. Since `40c5c09` the pass no longer reads as proof: `Skeleton.validate` still returns `None` on a clean pass, then records `conservation_outcome(self.chemistry)` on `Skeleton.conservation` (`compare=False`, not persisted), and every skeleton-minted world reads `vacuous: no atoms` there ([ABIO Skeleton](../ABIO%20suite/ABIO%20Skeleton.md)). The remedy that would make the check bite — per-tag atoms on minted pools — needs no change here.



## The canary
`total_quantity` is the extensive amount of each label in a state. Its docstring calls it invariant across steps for a world whose internal reactions balance and whose flows conserve, and since `40c5c09` names the exceptions; three things move it legitimately: boundary reactions (which the check exempts and which nearly every world has), population laws (growth creates biomass by design), and anything a caller does to a state between steps. So the canary is a test instrument for closed worlds; no simulator, preflight or report calls it, and a world with a source cannot use it as is.



## Tolerance
`_TOL = 1e-9` is absolute, applied per label after summing. Stoichiometries and atom counts are small integers in every caller today, so the scale question does not arise.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`). Checked locally against that export: the atom-free pass under the defaults and the `require_atoms` refusal. Callers found by grep over `src/` and `tests/`. Not determined: whether any planned caller means to run `total_quantity` on an open world. Findings filed on T088.
- 2026-10-28 — T088 bio and operator round: `conservation_outcome` (`balanced` / `vacuous: no atoms` / `partial: …` / `violated: …`) added and `Skeleton.validate` records it on `Skeleton.conservation` — every skeleton-minted world reads `vacuous: no atoms`; `total_quantity`'s docstring names what moves it legitimately (boundary reactions, population laws).
- 2026-10-28 — refreshed against 0eb23e5: `conservation_outcome`, `BALANCED` and `VACUOUS` given blocks and index rows; *What the gate proves* now says `Skeleton.conservation` records the vacuous verdict; *The canary* notes the docstring names its exceptions. Figure still true (‡ legend kept).
