---
description: "`jax_core`: the pure JAX kernels behind `JaxWorldSimulator` — padding reactions, modulators and compiled rate laws into tensors, the simultaneous rationed reaction update over a `[compartments, molecules]` array, the native-flow transfer, and the jitted step and `fori_loop` run builders. Source: `src/alienbio/bio/jax_core.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO bio](ABIO%20bio.md) → [ABIO JaxCore](ha://p/ABIO%20JaxCore) 
# ABIO JaxCore
The page for the kernel module under the JAX simulator: what each builder lowers a reaction list into, the one reaction update every JAX path runs, its non-negativity argument, and how the step and run functions are put together.

![ABIO JaxCore](ABIO%20JaxCore.svg) 
*The reaction kernel* is the topic behind `apply_reactions`, whose formula runs along the bottom of the figure; *Compartment ids* governs the ‡ on `build_reaction_tensors`, the one place the kernel and the reference read a reaction's compartment list differently.

`jax_core.py` has no class: it is a set of pure functions over a dense state `S` of shape `[C, M]`, written so `jit`, `fori_loop` and `vmap` compose without a host round trip. Its one caller in `src/` is [ABIO JaxWorldSimulator](ABIO%20JaxWorldSimulator.md), whose page already carries the lowering table (§ Lowering a world), what each run path accepts, the parity contract with its clamps, native flows, and compilation; this page does not repeat them and covers the functions themselves. The reference it must match is [ABIO WorldSimulatorImpl](ABIO%20WorldSimulatorImpl.md); the rate-law lowering and the shared constants `RATE_CAP` and `ROUNDING_FLOOR` come from [ABIO RateExpr](ABIO%20RateExpr.md); the subsystem view is [ABIO-Bio-Engine](../../ABIO%20Architecture/ABIO-Bio-Engine.md).



## jax_core Interface
Every builder runs once per simulator on the host and returns device arrays; every kernel is a pure `S -> S` or `S -> array` function. Without JAX installed the module still imports (`HAS_JAX` is false and `jax`/`jnp` are `None`); calling a kernel then fails on the first `jnp` use, so the simulator checks `HAS_JAX` first.

| jax_core | |
| --- | --- |
| [HAS_JAX](#^has-jax) | Whether JAX imported |
| [Array](#^array) | Annotation alias |
| [enable_x64](#^enable-x64) | Turn on 64-bit floats |
| [build_reaction_tensors](#^build-reaction-tensors) | Stoichiometry, rates, compartment mask |
| [MOD_KINDS](#^mod-kinds) | Modulation kind codes |
| [build_modulation_tensors](#^build-modulation-tensors) | Padded modulator slots |
| [modulation_factors](#^modulation-factors) | Per-reaction, per-compartment factor |
| [LawFn](#^lawfn) | A lowered rate law |
| [build_rate_laws](#^build-rate-laws) | Lower every `rate_law` |
| [apply_reactions](#^apply-reactions) | One simultaneous reaction update |
| [apply_native_flows](#^apply-native-flows) | Linear transfers, in list order |
| [make_step_fn](#^make-step-fn) | Reactions then native flows |
| [make_run_fn](#^make-run-fn) | Jitted `fori_loop` over a step |

**HAS_JAX**`: bool`
    True when `jax` imported at module load. ^has-jax

**Array**` = Any`
    A JAX array in annotations, `Any` so the module type-checks without JAX. ^array

**enable_x64**`() -> None`
    Sets JAX's process-wide `jax_enable_x64` flag; a no-op without JAX. Every later JAX computation in the process, not just this simulator's, then defaults to 64-bit. ^enable-x64

**build_reaction_tensors**`(reactions, num_molecules, num_compartments, dtype) -> (r_stoich, p_stoich, k, comp_mask)`
    Pads a list of `ReactionSpec`-like objects into reactant and product stoichiometry `[Rn, M]` (a repeated molecule adds), rate constants `[Rn]` and an active-compartment mask `[Rn, C]` (all ones for `compartments=None`, else ones at the listed ids). Zero reactions give empty arrays of the right widths. Molecule and compartment ids are used as Python list indices without a range check (§ [Compartment ids](#compartment-ids)). ^build-reaction-tensors

**MOD_KINDS**`: Tuple[str, ...] = ("", "activator", "inhibitor", "michaelis", "hill")`
    Kind codes 0–4 for the modulation tensors; 0 is a padded or inert slot. ^mod-kinds

**build_modulation_tensors**`(reactions, dtype) -> Optional[(mod_mol, mod_kind, mod_params)]`
    `None` when no reaction has a modulator, the fast path. Otherwise pads every reaction's `modulators` to the widest count `Mn`: molecule index `[Rn, Mn]` (int32), kind code `[Rn, Mn]` (int32) and parameters `[Rn, Mn, 3]` (`a` or `Ki` in slot 0; `K`, `Vmax`, `n` for the saturable kinds). A kind outside `MOD_KINDS`, or a known kind missing a parameter it needs, is left at code 0 and contributes a factor of 1, as the reference's `_modulation_factor` does. ^build-modulation-tensors

**modulation_factors**`(S, mod_mol, mod_kind, mod_params) -> Array`
    The `[Rn, C]` product over each reaction's slots of its kind's term, read off the modifier's own concentration: activator `1 + a·m`, inhibitor `1 / (1 + m/Ki)`, michaelis `Vmax·m / (K + m)` and hill `Vmax·mⁿ / (Kⁿ + mⁿ)`, each saturable term 0 when its denominator is not positive. Every branch is computed for every slot and selected by `_where`, a typed three-argument `jnp.where`. ^modulation-factors

**LawFn**` = Tuple[int, Callable[[Array], Array], bool]`
    A lowered rate law: the reaction's index, `S -> [C]`, and whether it multiplies mass action (`implicit_mass_action`). ^lawfn

**build_rate_laws**`(reactions) -> List[LawFn]`
    One `LawFn` per reaction carrying a `rate_law`, its function calling `rate_expr.lower_jax(law, S, int)`; the law's species must already be molecule ids. Reactions without one are skipped. ^build-rate-laws

**apply_reactions**`(S, r_stoich, p_stoich, k, comp_mask, dt, modulation=None, laws=()) -> Array`
    Runs every reaction at once from the frozen `S` and returns the updated array (§ [The reaction kernel](#the-reaction-kernel)). With zero reactions returns `S` unchanged. ^apply-reactions

**apply_native_flows**`(S, flows, dt) -> Array`
    For each `(src, dst, mol, rate)` in list order, moves `max(min(dt·rate, 1)·S[src, mol], 0)` from `src` to `dst`. Sequential, concentration-based, and clamped at the whole pool; how that differs from `apply_flows` is on [ABIO JaxWorldSimulator](ABIO%20JaxWorldSimulator.md) § Native flows. ^apply-native-flows

**make_step_fn**`(r_stoich, p_stoich, k, comp_mask, dt, native_flows, modulation=None, laws=()) -> Callable`
    A pure `S -> S` closing over every tensor: `apply_reactions`, then `apply_native_flows` when there are any. Not jitted here; the simulator jits it. ^make-step-fn

**make_run_fn**`(step_fn) -> Callable`
    `jax.jit` of `(S0, steps) -> fori_loop(0, steps, step_fn)`, with `steps` static, so the trajectory stays on the device and each distinct `steps` compiles its own loop. ^make-run-fn




# JaxCore Semantics

## The reaction kernel
One step, for reactions `r`, compartments `c` and molecules `m`, every term read from the frozen `S`:

```
rate[r,c]    = k[r] * prod_m S[c,m] ** R[r,m]
rate[i,c]    = law_i(S)[c] * mass_action[i,c]   (implicit law)
rate[i,c]    = law_i(S)[c]                      (law names a reactant)
rate        *= modulation_factors(S)            (when modulated)
desired      = max(min(rate * dt, RATE_CAP), 0) * comp_mask, NaN -> 0
demand[c,m]  = sum_r desired[r,c] * R[r,m]
ratio[c,m]   = min(1, S[c,m] / demand[c,m])     (1 where demand = 0)
scale[r,c]   = min over reactants m of r of ratio[c,m]
S'           = S + (desired * scale)^T (P - R)
S'[c,m]      = 0  where -ROUNDING_FLOOR < S'[c,m] < 0
```

`0 ** 0` is 1 in `jnp`, so a molecule that is not a reactant contributes a factor of 1, and a reaction with no reactant has `scale = 1`. A rate law replaces row `i` of the mass-action rate before modulation, so a modulated reaction with a law is modulated on top of its law, as in the reference.



## Non-negativity
For any compartment and molecule, the amount consumed is `Σ_r desired·scale·R ≤ ratio·demand ≤ S`, because each reaction's `scale` is at most the `ratio` of every one of its reactants. Exact arithmetic therefore never drives a reactant below zero, whatever the order or number of competing reactions, and the snap catches float residue down to `-1e-12`. The argument assumes `S ≥ 0` on entry: a concentration already below `-ROUNDING_FLOOR` gives a negative ratio and a negative extent, which runs the reaction backwards; nothing in the step produces one.



## Compartment ids
`build_reaction_tensors` marks a reaction active by indexing a Python list, `comp_mask[i][c] = 1.0` for each listed `c`. The reference asks `comp in reaction.compartments` while looping over the real ids. The two agree for every id in `0..C-1` and for `None` (the only value `WorldSimulatorImpl.from_chemistry` writes), and disagree otherwise: a negative id marks a compartment from the end on the kernel and none on the reference, and an id at or past `C` raises `IndexError` on the kernel and is ignored by the reference. A local run at `038c399` with `compartments=[-1]` on a two-compartment tree left the reference untouched and ran the reaction in compartment 1 on JAX. No production path builds such a spec.



## Modulation slots
Slots are padded per reaction to the widest modulator count, and the padded slot reads molecule 0 under kind 0, whose term is the constant 1. Because every branch is evaluated for every slot before selection, an undefined branch (a hill power of a negative concentration, an inhibitor with `Ki = 0`) computes NaN or infinity in a slot that may not use it; `_where` discards it, so it reaches the product only when the slot's own kind is that branch. A real inhibitor with `Ki = 0` and no inhibitor present reads `0/0` and stops the reaction, on both backends alike.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084) from the source at alienbio HEAD `038c399` (read from a `git archive` export, a concurrent worker editing `src/`), with the reference's `_desired_extent`, `_modulation_factor` and `_apply_reactions` read beside it. [ABIO JaxWorldSimulator](ABIO%20JaxWorldSimulator.md) was written when this module had no page and named its functions only as far as the class drives them; the two pages now split as class and kernels, and the parity and native-flow material stays there. Checked locally against the export: the `[-1]` and out-of-range compartment divergence, and the `Ki = 0` inhibitor stopping the reaction on both backends. Findings filed on T088.
