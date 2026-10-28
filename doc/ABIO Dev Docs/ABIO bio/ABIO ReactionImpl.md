---
description: "`ReactionImpl` and `Modulation`: one reaction's stoichiometry, its non-consumed modifiers, its numeric rate and its optional compiled rate law. Source: `src/alienbio/bio/reaction.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO ReactionImpl](ha://p/ABIO%20ReactionImpl) 
# ABIO ReactionImpl
One reaction of a chemistry: reactant and product molecules with their coefficients, non-consumed modifiers each carrying a `Modulation`, a numeric rate constant, and optionally a compiled `rate_expr` tree that replaces it.

![[ABIO ReactionImpl.svg|2400]] 
*The numeric rate and the rate law* is the topic that governs the hub's dashed box: when a `rate_law` is set the numeric `rate` is unused, while `Modulation` modifiers still multiply in.

This page covers the reaction entity, the `Modulation` record its modifiers carry, and how both serialize. The container that holds reactions by id is [[ABIO ChemistryImpl]]; the tree a `rate_law` is, and its evaluation, is [[ABIO RateExpr]]; how a reaction becomes a `ReactionSpec` and an extent per step is [[ABIO WorldSimulatorImpl]] (`from_chemistry`, `_desired_extent`, `_modulation_factor`) and, vectorised, [[ABIO JaxWorldSimulator]]; where it sits in the substrate is [[ABIO-Bio-Engine]].



## ReactionImpl Interface
The `Reaction` Protocol's implementation (`protocols/bio.py`, held to it by `protocols/_conformance.py` under `pyright src/`), registered as Entity head `"Reaction"`. It owns five slots — `_reactants`, `_products`, `_modifiers`, `_rate`, `_rate_law` — and exposes them as properties that return copies of the dicts, so a caller cannot mutate a reaction through what it reads; the four `set_`/`add_` methods are the only writers. Molecules are dict keys by identity (`MoleculeImpl` defines no equality), shared by reference with the chemistry, never Entity children of the reaction. From `Entity` it inherits `local_name`, `head`, `dat()`, `full_name`, `to_dict()` and the rest, and requires a `parent` or a `dat`.

| ReactionImpl | |
| --- | --- |
| [[#^reactionimpl\|ReactionImpl]] | Build from molecule dicts, a rate and an optional rate law |
| [[#^hydrate\|hydrate]] | Build from a dict, resolving molecule names |
| [[#^reactants\|reactants]] | Consumed molecules and their coefficients |
| [[#^products\|products]] | Produced molecules and their coefficients |
| [[#^modifiers\|modifiers]] | Non-consumed molecules and their Modulation or role tag |
| [[#^rate\|rate]] | The numeric rate constant |
| [[#^rate-law\|rate_law]] | The compiled rate tree, or None for mass action |
| [[#^name\|name]] | The reaction's id, equal to its local name |
| [[#^symbol\|symbol]] | Formula string, reactants -> products |
| [[#^set-rate\|set_rate]] | Replace the rate constant |
| [[#^add-reactant\|add_reactant]] | Set one reactant's coefficient |
| [[#^add-product\|add_product]] | Set one product's coefficient |
| [[#^add-modifier\|add_modifier]] | Set one modifier's Modulation or role tag |
| [[#^attributes\|attributes]] | The reaction as a plain dict |

**ReactionImpl**`(name: str, *, reactants: Optional[Dict[MoleculeImpl, float]] = None, products: Optional[Dict[MoleculeImpl, float]] = None, modifiers: Optional[Mapping[MoleculeImpl, ModifierValue]] = None, rate: RateValue = 1.0, rate_law: Optional[Any] = None, parent: Optional[Entity] = None, dat: Optional[DatLike] = None, description: str = "") -> None`
    Initialize the `Entity` (`ValueError` without a `parent` or `dat`, or with a space in `name`), then store a shallow copy of each molecule dict (an absent one is `{}`) and `rate`, which must be a real number (`ValueError` for anything else — a string, `None`, a `bool`, a callable; accepted unchecked until 2026-10). `rate_law` passes through `rate_expr.from_json`: a nested-list tree becomes tuples, a tuple tree passes through once its tags and arities are checked, and anything else — including rate-grammar text such as `"k * A"` — raises `ValueError`; the text form must be compiled first ([[#The numeric rate and the rate law]]). Nothing checks `rate`'s type, the coefficients, or that the tree's species are molecules of this reaction. ^reactionimpl

**hydrate**`(data: dict[str, Any], *, molecules: dict[str, MoleculeImpl], dat: Optional[DatLike] = None, parent: Optional[Entity] = None, local_name: Optional[str] = None) -> Self` (classmethod)
    Build from a dict, resolving every molecule name through `molecules`; an unknown reactant, product or modifier raises `KeyError` naming the reaction and the molecule. `reactants`/`products` are a `{name: coef}` mapping (what `attributes` writes) or a list whose entries are a bare name (coefficient 1) or a `{name: coef}` dict; `modifiers` is a `{name: role}` dict or a list of names (role `""`) and `{name: role}` dicts, every key kept; any other entry type is `TypeError`; and a role that is itself a dict becomes `Modulation(**role)` (an unknown key raises `TypeError`). `rate` defaults to `1.0`, `rate_law` is passed to the constructor, the name is `local_name`, else `data["name"]`, else `"reaction"`, and with neither `dat` nor `parent` it mints `MockDat("rxn/<name>")`. It is the inverse of `attributes`: see [[#Serialization]]. ^hydrate

**reactants**`: Dict[MoleculeImpl, float]` (property)
    A copy of the consumed molecules mapped to their stoichiometric coefficients — the exponents of mass action and the amounts each extent removes. An empty dict makes the reaction a boundary source; see [[#Stoichiometry and modifiers]]. ^reactants

**products**`: Dict[MoleculeImpl, float]` (property)
    A copy of the produced molecules mapped to their coefficients. An empty dict makes the reaction a boundary sink. ^products

**modifiers**`: Dict[MoleculeImpl, ModifierValue]` (property)
    A copy of the molecules that act on the rate without being consumed, each mapped to a `Modulation` or a bare role-tag `str` (`"catalyst"`). A bare string is rate-inert; `from_chemistry` coerces it with `Modulation.from_value` ([[#Modulation kinds and defaults]]). ^modifiers

**rate**`: RateValue` (property)
    The rate constant `k` of mass action, `rate · Π [reactant]^coef`. A real number, checked at construction and by `set_rate` (`ValueError` otherwise); `from_chemistry` keeps its own check. Unused whenever `rate_law` is set. ^rate

**rate_law**`: Optional[Any]` (property)
    The compiled `rate_expr` tree with species named by molecule `name`, or `None` for plain mass action. Read by `from_chemistry`, which re-keys its species to molecule ids with `map_species` (a name outside the chemistry raises `KeyError`). ^rate-law

**name**`: str` (property)
    The reaction's `local_name`, returned as is. A chemistry keys reactions by this value, so it shares the molecules' id namespace ([[#Reaction ids]]). ^name

**symbol**`: str` (property)
    The formula `"A + 2B -> C"`: molecules by `name` in dict order, a coefficient prefixed only when it is not `1` (written as Python prints it, so `2.0B` for a float). Modifiers and the rate are not shown. ^symbol

**set_rate**`(rate: RateValue) -> None`
    Replace the rate constant in place; a non-number refuses with `ValueError` and leaves the old rate. Does not touch `rate_law`, so it has no effect on a reaction that has one. ^set-rate

**add_reactant**`(molecule: MoleculeImpl, coefficient: float = 1.0) -> None`
    Set `molecule`'s reactant coefficient, overwriting any earlier one. Does not check that the molecule is in the chemistry or absent from the products. ^add-reactant

**add_product**`(molecule: MoleculeImpl, coefficient: float = 1.0) -> None`
    Set `molecule`'s product coefficient, overwriting any earlier one. ^add-product

**add_modifier**`(molecule: MoleculeImpl, role: ModifierValue = "") -> None`
    Map `molecule` to `role` (a `Modulation` or a string), overwriting any earlier entry. The default `""` is a rate-inert label. ^add-modifier

**attributes**`() -> Dict[str, Any]`
    The Entity attributes (`name`, `description` when set) plus `reactants` and `products` as `{local_name: coef}` and `modifiers` as `{local_name: role}` — each only when non-empty, a `Modulation` written through `to_dict()` and a string as is — then `rate` always and `rate_law` (via `rate_expr.to_json`) when set. `to_dict()` and `ChemistryImpl.attributes()` serialize through this. ^attributes



## Modulation Interface
A frozen dataclass carrying one modifier's effect on its reaction's rate: a `kind` and the parameters that kind reads. It has no behaviour of its own — the arithmetic lives in `WorldSimulatorImpl._modulation_factor` and `jax_core.modulation_factors`, evaluated from the frozen start-of-step state. Every parameter defaults to `None`, and a kind whose required parameters are not all set contributes a factor of exactly `1.0`, as does any kind outside the four ([[#Modulation kinds and defaults]]). Built by `ModulationSpec.sample` in `suite/rate_law.py`, by `w2_gen` and the drafters directly, and by `ReactionImpl.hydrate` from a dict.

| Modulation | |
| --- | --- |
| [[#^kind\|kind]] | activator, inhibitor, michaelis, hill — or an inert label |
| [[#^a\|a]] | Activator gain |
| [[#^ki\|Ki]] | Inhibitor constant |
| [[#^vmax\|Vmax]] | Saturable ceiling |
| [[#^k\|K]] | Saturable half-point |
| [[#^n\|n]] | Hill exponent |
| [[#^from-value\|from_value]] | Coerce a role-tag string into an inert Modulation |
| [[#^to-dict\|to_dict]] | The set fields as a dict |

**kind**`: str = ""`
    Which formula applies: `"activator"`, `"inhibitor"`, `"michaelis"` or `"hill"`. Any other value, including the default `""` and role tags such as `"catalyst"`, is a documentation label. Not validated. ^kind

**a**`: Optional[float] = None`
    The activator gain: the factor is `1 + a·[modifier]`. ^a

**Ki**`: Optional[float] = None`
    The inhibitor constant: the factor is `1 / (1 + [modifier]/Ki)`. `Ki = 0` reads as IEEE division does — inf, so a factor of 0, at `[modifier] > 0`; NaN, so no reaction, at 0 — on both simulators. ^ki

**Vmax**`: Optional[float] = None`
    The ceiling of the two saturable kinds. Required by both in the simulators — no default is applied here ([[#Modulation kinds and defaults]]). ^vmax

**K**`: Optional[float] = None`
    The half-saturation point of `"michaelis"` (`Vmax·m / (K + m)`) and `"hill"` (`Vmax·mⁿ / (Kⁿ + mⁿ)`), where `m` is the modifier's own concentration. ^k

**n**`: Optional[float] = None`
    The Hill cooperativity exponent; read only by `"hill"`, which is inert without it. ^n

**from_value**`(value: Union[Modulation, str]) -> Modulation` (classmethod)
    Return a `Modulation` unchanged, or wrap a string as `Modulation(kind=value)` with every parameter `None` — rate-inert unless the string happens to be one of the four kinds, which with no parameters is still inert. Called by `from_chemistry` on every modifier value. ^from-value

**to_dict**`() -> Dict[str, Any]`
    `{"kind": kind}` plus each parameter that is not `None`, under its field name; `Modulation(**d)` rebuilds an equal record. ^to-dict



## reaction Interface
The module exports `ReactionImpl` and `Modulation`, both re-exported from `alienbio.bio` (and `ReactionImpl` from `alienbio`), plus two type aliases used in the signatures above and nowhere else in `src/`.

| reaction | |
| --- | --- |
| [[#^ratevalue\|RateValue]] | The type of a reaction's rate |
| [[#^modifiervalue\|ModifierValue]] | The type of a modifier's value |

**RateValue**` = float`
    A rate constant. The alias once admitted a callable for the M1 single-compartment simulator; since T056 it is `float` alone. ^ratevalue

**ModifierValue**` = Union[Modulation, str]`
    What a modifier maps to: a `Modulation`, or a bare role-tag string kept for backward compatibility (F015 Q2). ^modifiervalue




# ReactionImpl Semantics

## Stoichiometry and modifiers
Reactants and products are `{MoleculeImpl: coefficient}` dicts; modifiers are `{MoleculeImpl: Modulation | str}`. What each reader takes from them:

| Reader | Reads | Ignores |
| --- | --- | --- |
| `WorldSimulatorImpl.from_chemistry` | all three, each molecule looked up by `name` in `chemistry.molecules` (`KeyError` if absent); `rate`, `rate_law` | `description` |
| `_desired_extent` | reactant coefficients as mass-action exponents, modulators as factors | products (applied after rationing) |
| `conservation.reaction_imbalance` | reactants, products, each molecule's `atoms` | modifiers, rate |
| `energy.reaction_delta_g` | reactants, products, each molecule's `formation_energy` | modifiers, rate |
| `conservation.is_boundary_reaction` | whether reactants or products is empty | — |
| `ChemistryImpl` graph queries | all three, as bipartite edges | rate, rate law |

The reaction stores no ΔG, reversibility or direction: `delta_g` is computed on demand by `energy.py`, and a reverse reaction is a second reaction. A boundary reaction (`∅ → X` or `X → ∅`) is exempt from both the conservation and the spontaneity check. A molecule may appear on both sides or as both reactant and modifier; nothing here forbids it.



## The numeric rate and the rate law
Since M47 there is one rate grammar. A `rate:` slot in Expr is a number, a `Dist`, or quoted rate-grammar text; `compile_rate` (`suite/rate_law.py`) turns it into a `RateLaw`, and `RateLawBlock.realize` (`suite/expr_heads.py`) draws it onto a reaction in one of two shapes:

- **Product form** — `k * hill(M, K) * inhibitor(I, Ki)`: `rate = k`, each modulation becomes a `Modulation` modifier on its pool, and `rate_law` is `None`.
- **Expression form** — anything else the grammar admits (a sum, a quotient, saturation over a reactant): `rate_law` is the drawn `rate_expr` tree over molecule names, every pool it reads that is not a reactant or product rides as an inert `Modulation(kind="")` modifier so the chemistry records the dependency, and `rate` is still set to the drawn `k`.

When `rate_law` is set, `_desired_extent` evaluates it and ignores `rate`: the tree is the whole rate if it names a reactant, else a factor on mass action. Modifier `Modulation`s multiply in either way, so a reaction that carries both a tree with `mod` nodes and parameterised `Modulation` modifiers is modulated twice; the compiler never produces that, but a hand-built reaction can. The `rate` itself is a number: before T056 a callable rate was silently downgraded to mass action 1.0; `from_chemistry` now refuses any non-number with `ValueError`, and this class still accepts one at construction.



## Modulation kinds and defaults

| kind | Needs | Factor | Missing parameter here | In a `rate_expr` `mod` node |
| --- | --- | --- | --- | --- |
| `activator` | `a` | `1 + a·m` | inert, 1.0 | `KeyError` |
| `inhibitor` | `Ki` | `1 / (1 + m/Ki)` | inert, 1.0 | `KeyError` |
| `michaelis` | `Vmax`, `K` | `Vmax·m / (K + m)`; 0 when `K + m ≤ 0` | inert, 1.0 | `Vmax = 1.0` |
| `hill` | `Vmax`, `K`, `n` | `Vmax·mⁿ / (Kⁿ + mⁿ)`; 0 when the denominator ≤ 0 | inert, 1.0 | `Vmax = 1.0`, `n = 2.0` |
| anything else | — | 1.0 | — | refused by `rate_expr.modulation` |

This module stores only what it is given: every parameter defaults to `None`, and both simulators (`world_simulator.py:317–332`, `jax_core.py:140–149`) skip a modulator whose required fields are not all set. The same incomplete modulation written as a `mod` node in a rate tree is not inert — `rate_expr.modulation_factor` defaults `Vmax` and `n`. Compiled worlds never meet the difference, because `rate_law._MODULATION_DEFAULTS` fills `Vmax = 1.0` (and `n = 2.0` for `hill`) before `ModulationSpec.sample` builds the `Modulation`; a hand-built `Modulation(kind="hill", K=0.5)` is inert. Factors from several modulators multiply: activators into a numerator, inhibitors into a denominator, saturable kinds as a separate product.



## Serialization
`attributes()` writes reactants and products as `{name: coef}` dicts, and `hydrate` reads that mapping form as well as the list form `!Reaction` builds, so `ReactionImpl.hydrate(r.attributes(), molecules=…)` for `A + 2B -> 3C` returns `A + 2B -> 3C`. Until 2026-10 `hydrate` iterated the mapping as a list, reading only its keys, so every coefficient came back as `1` and `ChemistryImpl.hydrate` inherited the loss. Modifiers round-trip — `hydrate` handles the dict form and rebuilds each `Modulation` from `to_dict()` output — and so does `rate_law` (`to_json` / `from_json`). A list-form modifier entry that is a dict with several keys contributes every key (it used to keep only its first). Pinned by `tests/bio/test_moddoc_findings_chemistry.py`.



## Construction paths

| Path | Calls | Rate law |
| --- | --- | --- |
| `mk.R(id, reactants, products, **kw)` (`bio/makers.py`) | the constructor, on `MockDat("rxn/<id>")` | whatever `kw` passes |
| `RateLawBlock.realize` (`suite/expr_heads.py`) | `mk.R` with sampled `Modulation`s | the drawn tree, expression form only |
| `!Reaction {…}` (`suite/expr_heads.py`) | `hydrate`, minting unknown molecules | a JSON tree in `rate_law:` |
| `ChemistryImpl.hydrate` | `hydrate` per entry | as given |
| Suite derivers — `carve`, `augment`, `perturbations`, the runner's `_chemistry_with_rate`, `ChemistryImpl.subgraph` | the constructor directly, sharing molecules | as each passes it |



## Reaction ids
A reaction's `name` is its `local_name`, and `ChemistryImpl` keys reactions by it in the same namespace as molecules: the chemistry's constructor refuses an id that names both, and `suite/naming.build_name_map` repeats the check, because the runner resolves an `Intervene` lever against reactions before molecules and the name map would otherwise give one surface token to two entities. Nothing in this module checks the id beyond `Entity`'s no-space rule. `symbol` reads molecules by `name`, `attributes()` and `__repr__` by `local_name`; they agree whenever a molecule's display name was not set apart from its local name.




# BRIEF
- 2026-10-18 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; every member traced to `bio/reaction.py`, readers to `world_simulator.py`, `jax_core.py`, `conservation.py`, `energy.py`, `suite/rate_law.py` and `suite/expr_heads.py`. The coefficient loss in § Serialization, the multi-key modifier drop, the unchecked `rate` and the pass-through of a malformed tuple `rate_law` were reproduced against the venv, not fixed. Left out: `__repr__` (a debug string; it prints a `Modulation` as its full dataclass repr), the members inherited unchanged from `Entity`, and the published page `ABIO Reaction`, a separate older page this doc does not link. Drift noted, not fixed: the docstrings at `reaction.py:93`, `131`, `242` and `275` and the `Reaction` Protocol's `rate: Union[float, Callable]` (`protocols/bio.py:154`) still describe a callable rate; the Protocol has no `rate_law`; `Callable` is imported and unused. The constructor block id is `^reactionimpl`, matching [[ABIO ChemistryImpl]].
