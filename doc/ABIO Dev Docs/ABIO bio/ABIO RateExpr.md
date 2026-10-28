---
description: "`rate_expr`: the compiled rate-law tree both simulators run — node builders, `eval_rate`, `lower_jax`, serialization, `ROUNDING_FLOOR` / `RATE_CAP`. Source: `src/alienbio/bio/rate_expr.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO RateExpr](ha://p/ABIO%20RateExpr) 
# ABIO RateExpr
The compiled form of a rate law: a small tree of tuples, built once from the rate grammar, that the reference simulator evaluates in Python and the JAX core lowers to array ops, so both read one law identically.

![[ABIO RateExpr.svg|2400]] 
*One tree, two evaluators* is the topic that governs the two evaluator boxes (the same node arithmetic and the same division floor); *Rounding floor and rate cap* governs the red annotations.

`bio/rate_expr.py` has no class: a tree is a plain `tuple` (`RateNode` is an alias for it), so the node grammar is described under [[#The node grammar]] rather than as an Interface section, and the one Interface section below covers the module-level functions and constants. This page covers the tree, its two evaluators and its serialization. The compiler that produces trees is `compile_rate` in `suite/rate_law.py` (summarised in [[#From rate text to a tree]]); the stepper that consumes one is [[ABIO WorldSimulatorImpl]], the vectorised one [[ABIO JaxWorldSimulator]], and the reaction that stores one [[ABIO ChemistryImpl]]'s `ReactionImpl`. The subsystem view is [[ABIO-Bio-Engine]].



## rate_expr Interface
Pure functions over `RateNode` trees and three constants, with no state. Only the standard library at import: `lower_jax` imports `jax.numpy` inside the call, so the module loads without JAX. `__all__` lists `MODULATION_KINDS`, `RATE_CAP`, `ROUNDING_FLOOR`, `RateNode` and the twelve functions (the two constants since 2026-10); the constants are imported by name by `world_simulator.py`, `jax_core.py`, `population.py` and `flow.py`, and are the one copy of each. The `ieee_*` helpers are module-level but not exported.

| rate_expr | |
| --- | --- |
| [[#^ratenode\|RateNode]] | Alias for a tree node: a tuple |
| [[#^const\|const]] | Build a constant leaf |
| [[#^species\|species]] | Build a concentration leaf |
| [[#^modulation\|modulation]] | Build a modulation leaf |
| [[#^modulation-kinds\|MODULATION_KINDS]] | The four modulation kinds |
| [[#^species-of\|species_of]] | Every species a tree reads |
| [[#^map-species\|map_species]] | The same tree over renamed species |
| [[#^implicit-mass-action\|implicit_mass_action]] | Whether mass action multiplies the law |
| [[#^modulation-factor\|modulation_factor]] | One modulation's factor at a concentration |
| [[#^eval-rate\|eval_rate]] | Evaluate a tree to a float |
| [[#^lower-jax\|lower_jax]] | Lower a tree to JAX ops over a state array |
| [[#^to-text\|to_text]] | The tree as inline Expr text |
| [[#^to-json\|to_json]] | The tree as nested lists |
| [[#^from-json\|from_json]] | Nested lists back to a tree |
| [[#^rounding-floor\|ROUNDING_FLOOR]] | Below this magnitude a value is zero |
| [[#^rate-cap\|RATE_CAP]] | The largest desired extent per step |

**RateNode**`= tuple`
    A type alias only, for annotations; nothing checks a tree's shape when it is built by hand. The tags and arities are in [[#The node grammar]]. ^ratenode

**const**`(value: float) -> RateNode`
    Returns `("const", float(value))`. Raises whatever `float()` raises on a non-numeric value. ^const

**species**`(name: Hashable) -> RateNode`
    Returns `("species", name)`. The name is not checked: it is a pool name straight out of the compiler, a molecule name on a `ReactionImpl`, or a molecule id on a `ReactionSpec`, depending on which [[#^map-species|map_species]] pass the tree has been through. ^species

**modulation**`(kind: str, pool: Hashable, params: Mapping[str, float]) -> RateNode`
    Returns `("mod", kind, pool, params)` with every parameter coerced to `float` into a new dict. `ValueError` when `kind` is not in `MODULATION_KINDS`. Does not check that the kind's required parameter is present and fills no defaults; a missing `a`, `Ki` or `K` surfaces as `KeyError` at evaluation ([[#Modulation factors]]). ^modulation

**MODULATION_KINDS**`= ("activator", "inhibitor", "michaelis", "hill")`
    The kinds [[#^modulation|modulation]] accepts, the same four `Modulation` kinds `bio/reaction.py` implements and `suite/rate_law.py`'s `MODULATION_HEADS` compiles. ^modulation-kinds

**species_of**`(node: RateNode) -> set`
    The set of species the tree reads: every `species` leaf's name and every `mod` node's pool. A node with an unrecognised tag contributes nothing, so the compiler's not-yet-drawn `("dist", …)` leaves are skipped. ^species-of

**map_species**`(node: RateNode, fn: Callable[[Any], Any]) -> RateNode`
    A new tree with `fn` applied to every species name and modulation pool; constants, operators and parameters are unchanged (a `mod` node's parameter dict is copied). A node with an unrecognised tag is returned as is. Whatever `fn` raises propagates: `WorldSimulatorImpl.from_chemistry` passes a lookup that raises `KeyError` for a name not in the chemistry. ^map-species

**implicit_mass_action**`(node: RateNode, reactants: Iterable[Any]) -> bool`
    `True` when the tree reads none of `reactants` — mass action over the reactants is then implicit and the law multiplies it; `False` when the law is the whole rate ([[#Implicit mass action]]). The names in `node` and `reactants` must be in the same space (both ids, as `ReactionSpec` calls it). ^implicit-mass-action

**modulation_factor**`(kind: str, m: float, p: Mapping[str, float]) -> float`
    The factor one modulation contributes at modifier concentration `m`, with parameters `p`, per the table in [[#Modulation factors]]. `michaelis` and `hill` return 0.0 instead of dividing when their denominator is not positive. `KeyError` for a missing required parameter; `ValueError` for an unknown kind. `inhibitor` with `Ki = 0` and `hill` with `n < 0` at `m = 0` read as JAX reads them (inf or NaN, via `ieee_div`/`ieee_pow`); until 2026-10 both raised `ZeroDivisionError`. ^modulation-factor

**eval_rate**`(node: RateNode, conc: Callable[[Any], float]) -> float`
    Evaluate the tree, calling `conc(name)` for each `species` leaf and `mod` pool. Recursive; the per-node rules, including `log` of a non-positive value giving `-inf`, `sqrt` giving 0 and `div` by anything smaller than `ROUNDING_FLOOR` giving 0, are in [[#The node grammar]]. `pow` is `ieee_pow` and `exp` is `ieee_exp`: a zero base with a negative exponent or an overflow is inf, a negative base with a fractional exponent is NaN, as under JAX ([[#One tree, two evaluators]]); until 2026-10 they raised or returned a `complex`. Returns the law's value unclamped; the caller applies `dt`, mass action and `RATE_CAP`. ^eval-rate

**lower_jax**`(node: RateNode, S: Any, column: Callable[[Any], int]) -> Any`
    The same law as `jax.numpy` ops over a state array `S` of shape `[C, M]`, returning one rate per compartment, shape `[C]`; `column(name)` gives the molecule axis index. Meant to be traced once under `jit`: `jax_core.build_rate_laws` wraps each reaction's tree in a closure that calls it. Constants broadcast to `[C]` in `S.dtype`. `log`, `sqrt` and `div` mask their unsafe inputs with a second `where` so the untaken branch never produces `inf` or `nan`; modulations go through the private `_lower_modulation`, the same arithmetic as [[#^modulation-factor|modulation_factor]]. `ImportError` when JAX is not installed. ^lower-jax

**to_text**`(node: RateNode) -> str`
    The tree as inline Expr text, for messages and test assertions: constants by `repr(float)`, species by `str`, a modulation as `hill(M, K=0.5, n=2.0, Vmax=1.0)`, unary as `exp(…)` or `-(…)`, and every binary node parenthesised, `(a * b)`. `ValueError` on an unrecognised tag. ^to-text

**to_json**`(node: RateNode) -> list`
    The tree as nested lists, the form `ReactionImpl.attributes()` writes under `rate_law`. A `mod` node's parameter dict is copied. An unrecognised tag raises `ValueError` naming it (until 2026-10 it was treated as binary). ^to-json

**from_json**`(data: Any) -> RateNode`
    The inverse of `to_json`; `ReactionImpl.__init__` passes every `rate_law` through it, so a reaction accepts either form. A `tuple` passes through after a recursive check of every tag and arity (`ValueError` naming the bad node; unchecked until 2026-10). `ValueError` when `data` is not a non-empty list or carries an unknown tag. `mod` parameters are copied but not coerced to `float`. ^from-json

**ROUNDING_FLOOR**`: float = 1e-12`
    Below this magnitude a value is float residue of an exact zero. Read by `eval_rate`'s and `lower_jax`'s `div`, and imported by both simulators and the population pass to snap small negative residues ([[#Rounding floor and rate cap]]). ^rounding-floor

**RATE_CAP**`: float = 1e150`
    The largest desired extent a reaction may ask for in one step: an infinite rate means "all of it", and the rationing then bounds it by availability. Not applied in this module; `WorldSimulatorImpl._desired_extent` and `jax_core.apply_reactions` clamp to it ([[#Rounding floor and rate cap]]). ^rate-cap




# RateExpr Semantics

## The node grammar
A tree is built from five shapes. It carries only numbers, species and operators: every bound constant and every `Dist` was folded or drawn before the tree reached a reaction, so it serializes to JSON and evaluates without an environment.

| Tag | Shape | `eval_rate` | `lower_jax` |
| --- | --- | --- | --- |
| `const` | `("const", x)` | `x` | `x` broadcast to `[C]` |
| `species` | `("species", name)` | `conc(name)` | `S[:, column(name)]` |
| `mod` | `("mod", kind, pool, params)` | `modulation_factor(kind, conc(pool), params)` | same arithmetic, `jnp.where` guards |
| `neg`, `exp` | `(tag, a)` | `-a`, `exp(a)` | same |
| `log` | `("log", a)` | `log(a)`, `-inf` when `a ≤ 0` | same |
| `sqrt` | `("sqrt", a)` | `sqrt(a)`, 0 when `a ≤ 0` | same |
| `add`, `sub`, `mul` | `(tag, a, b)` | `a + b`, `a − b`, `a · b` | same |
| `div` | `("div", a, b)` | `a / b`, 0 when `\|b\| < ROUNDING_FLOOR` | same |
| `pow` | `("pow", a, b)` | `ieee_pow(a, b)`: inf / NaN where Python refuses | `a ** b`, unguarded |

Both evaluators recurse on the tag and check it before reading any operand, so an unknown tag raises `ValueError` naming it whatever its arity (until 2026-10 the binary children were evaluated first, and a short malformed node failed on indexing instead).



## From rate text to a tree
A reaction's `rate:` slot in an Expr world is a number, a `Dist` or a quoted form in the rate grammar. `compile_rate` (`suite/rate_law.py`) tries the **product form** first — `k` times modulations by non-consumed pools — which compiles to `RateLaw(k, modulations)` and becomes `Modulation` modifiers on the reaction, not a tree. Anything else the grammar admits (a sum, a quotient, `exp`/`log`/`sqrt`, saturation over a reactant) compiles to a tree in `RateLaw.expr`, over pool names, with `("dist", …)` leaves still to draw.

| Step | Where | What happens to the tree |
| --- | --- | --- |
| compile | `rate_law._compile_expr` | built from the node builders, defaults filled |
| realize | `RateLaw.realize_expr` | every `dist` leaf and `Dist` parameter drawn under the world seed |
| name | `expr_heads` reaction head | `map_species`: pool → molecule name |
| store | `ReactionImpl.__init__` | `from_json`; `attributes()` writes `to_json` back |
| index | `WorldSimulatorImpl.from_chemistry` | `map_species`: name → molecule id, `KeyError` if unknown |
| run | `_desired_extent`, `jax_core` | `eval_rate` per compartment, or `lower_jax` once per reaction |

At the name step, a species the law reads but the reaction does not consume is added as an inert modifier, so the chemistry records the dependency. `JaxWorldSimulator` takes the same id-keyed `ReactionSpec` list, so the tree it lowers is the one the reference evaluates.



## Implicit mass action
A law that names a reactant is the whole rate (`Vmax * S / (Km + S)` over substrate `S`); a law that names none is a factor on mass action over the reactants (`k * hill(M, K)`). `implicit_mass_action` decides once, when `ReactionSpec` is constructed, and both simulators read the stored flag: the reference multiplies `Π [reactant]^stoichiometry` into the law's value, `jax_core.apply_reactions` multiplies the precomputed mass-action term. In both cases `rate_constant` is ignored once a law is set; a law that should scale by `k` carries it as a constant.



## Modulation factors

| Kind | Needs | Factor at `m` | Default |
| --- | --- | --- | --- |
| `activator` | `a` | `1 + a·m` | — |
| `inhibitor` | `Ki` | `1 / (1 + m/Ki)` | — |
| `michaelis` | `K` | `Vmax·m / (K + m)`; 0 when `K + m ≤ 0` | `Vmax = 1.0` |
| `hill` | `K` | `Vmax·mⁿ / (Kⁿ + mⁿ)`; 0 when the denominator ≤ 0 | `Vmax = 1.0`, `n = 2.0` |

This module fills a missing `Vmax` or `n` with the default at evaluation. The product-form path does not run through here: a `Modulation` modifier is evaluated by `WorldSimulatorImpl._modulation_factor` (and `jax_core.modulation_factors`), which treats a modifier missing `Vmax`, `K` or `n` as inert, factor 1. The compiler fills the same defaults (`_MODULATION_DEFAULTS`) on both paths, so a compiled world always carries them; the two paths differ only for a hand-built `Modulation` or tree.



## Rounding floor and rate cap

| Constant | Applied in | Effect |
| --- | --- | --- |
| `ROUNDING_FLOOR` | `eval_rate` and `lower_jax`, `div` | a divisor smaller than 1e-12 in magnitude yields 0 on both backends |
| `ROUNDING_FLOOR` | reference reactant subtraction, `jax_core.apply_reactions` | a result in `(−1e-12, 0)` is written as 0 |
| `ROUNDING_FLOOR` | `population.py` | the same snap for pools and multiplicities |
| `RATE_CAP` | `_desired_extent`, `jax_core.apply_reactions` | the per-step desire is clamped to 1e150; NaN becomes 0 |

The floor lives here because the two backends once carried their own copies, and a `1/[x]` law turned a 1e-16 residue into a `RATE_CAP` extent on one of them while the other read exactly 0 (T051 box 4, T054). Only `div` is floored: `pow(x, -1)` reads the same residue as 1e16 on both backends, and reads an exact zero differently ([[#One tree, two evaluators]]).



## One tree, two evaluators
`eval_rate` and `lower_jax` walk the same tags with the same arithmetic, and `_lower_modulation` duplicates `modulation_factor` line for line, so for every finite, positive input the two agree to float64 rounding. Python refuses operations JAX reads as inf or NaN; `ieee_pow`, `ieee_div` and `ieee_exp` are the one place the reference reads them as JAX does (returning Python's own result wherever Python accepts the input), and both steppers then clamp alike. Until 2026-10 they parted:

| Input | `eval_rate` before 2026-10 | both now, after the clamps |
| --- | --- | --- |
| `pow`, base 0, exponent < 0 | `ZeroDivisionError` | `inf`, capped to `RATE_CAP` |
| `pow`, base < 0, fractional exponent | a `complex`, then `TypeError` in `_desired_extent` | `nan`, read as 0 |
| `hill` with `n < 0` at `m = 0` | `ZeroDivisionError` | `nan` (`inf / inf`), read as 0 |
| `inhibitor` with `Ki = 0` | `ZeroDivisionError` | `0` or `nan` |

The parity tests are `tests/expr/test_rate_grammar.py::test_jax_matches_reference_on_modulations_and_expression_laws` (a Michaelis–Menten quotient, a `sqrt`·`exp` sum and every modulation kind, to 1e-9) and `tests/capabilities/test_simulator_conformance.py`, whose generated laws use every operator — `add`, `sub`, `mul`, `div`, `pow` (exponents −1, 0.5, 1.5, 2, 3, over a species or a `sub` that can go negative), `sqrt`, `exp`, `log` — and `michaelis`, plus one pinned `1/[x]` case on an exhausted species; `tests/bio/test_moddoc_findings_rate_expr.py` pins each row of the table above.




# BRIEF
- 2026-10-18 — written as an ABIO module doc (T084, deep-scan box 3), from the source at alienbio HEAD 84f8190; every member and claim traced to `bio/rate_expr.py`, `suite/rate_law.py`, `suite/expr_heads.py`, `bio/reaction.py`, `bio/world_simulator.py`, `bio/jax_core.py` and the two parity tests. The node grammar has no class, so it is a Semantics section and the page has one Interface section. Left out: the private `_lower_modulation`, `_BINARY` and `_UNARY`, named in prose only. The edge cases in § One tree, two evaluators were reproduced against HEAD for `eval_rate` (`0.0 ** -1.0` raises, `(-1e-13) ** 0.5` is complex, `hill` with `n = -1` at 0 raises), not fixed; the JAX column is read from the code, not run. The module docstring's "the modulation math is exactly `WorldSimulatorImpl._modulation_factor`'s" holds for the arithmetic but not for a missing parameter: this module defaults `Vmax = 1.0`, `n = 2.0` (`rate_expr.py:108,110,113`) where the modulator path treats a missing field as inert (`world_simulator.py:317–332`); unreachable from compiled worlds because `rate_law._MODULATION_DEFAULTS` fills both. `suite/rate_law.py`'s numeric `hill`/`michaelis` heads guard with `if (K or m)` rather than this module's `denom > 0`, so they differ on a negative denominator.
- 2026-10-27 — the findings above fixed: `ieee_pow`/`ieee_div`/`ieee_exp` (the reference reads an undefined operation as JAX does), `from_json` checks a tuple tree, every walker refuses an unknown tag with `ValueError`, and `suite/rate_law.py`'s numeric `hill`/`michaelis` heads guard on `denom > 0` like this module.
