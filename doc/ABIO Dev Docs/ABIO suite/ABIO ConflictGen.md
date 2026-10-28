---
description: "`conflict_gen`: the M31.1 conflict-ladder generator — four rungs (`single`, `compatible`, `latent`, `forced`) sized off one source supply rate, the `Source -> ConflictCruxBlock` skeleton, the closed-form `V1 + V2 = S` frontier, the forced rung's simulate-and-check gate, the min-of-components outcome objective. Source: `src/alienbio/suite/conflict_gen.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO ConflictGen](ha://p/ABIO%20ConflictGen) 
# ABIO ConflictGen
The generator of the conflict ladder: one source feeding two rival routes through a shared precursor, with the source's supply rate placed on four rungs from one objective to a provably unmeetable pair.

![ABIO ConflictGen](ABIO%20ConflictGen.svg) 
*The ladder* is the topic behind the rung table beside `draft_conflict_world` (each rung is a supply multiplier); *The forced gate* governs the dotted loop through `sweep_conflict_frontier`.

`suite/conflict_gen.py` composes library blocks only: `SourceBlock`, `ConflictCruxBlock`, `ReactionBlock`, `SinkBlock` and `sweep_conflict_frontier` are on [ABIO Blocks](ABIO%20Blocks.md), the tree, `materialize` and `oracle` on [ABIO Skeleton](ABIO%20Skeleton.md). The drafter head `conflict` in `drafters.py` wraps `draft_conflict_world` into a task, and `tradeoff.conflict_oracle` puts the frontier on the task's oracle for EXP-7's conflict summary; the Expr head `conflict_world` calls it directly. `draft_conflict_world`, `build_conflict_skeleton` and `closed_form_frontier` are re-exported from `alienbio.suite`. The pressure world that grew out of this shape is [ABIO PressureGen](ABIO%20PressureGen.md).



## conflict_gen Interface
The public surface is three functions and four constants; everything else is private.

| conflict_gen | |
| --- | --- |
| [RUNGS](#^rungs) | The four rung names, in ladder order |
| [DEFAULT_TARGET](#^default-target) | Per-target goal, both targets |
| [DEFAULT_KA](#^default-ka) | Default route A rate |
| [DEFAULT_KB](#^default-kb) | Default route B rate |
| [draft_conflict_world](#^draft-conflict-world) | Draft one rung: world, skeleton, objective |
| [build_conflict_skeleton](#^build-conflict-skeleton) | The two-route skeleton, unmaterialized |
| [closed_form_frontier](#^closed-form-frontier) | Points on the line `V1 + V2 = S` |

**RUNGS**` = ("single", "compatible", "latent", "forced")`
    The ladder order; `tradeoff` and `plots` import it to order per-rung summaries. ^rungs

**DEFAULT_TARGET**` = 10.0`
    The default `v1_target` and `v2_target`, equal so a rung's character comes from the supply alone. ^default-target

**DEFAULT_KA**` = 1.0`
    Route A's default rate, the naive balanced split. ^default-ka

**DEFAULT_KB**` = 1.0`
    Route B's; `kA == kB` is what makes `latent` look conflict-free (§ [The ladder](#the-ladder)). ^default-kb

**draft_conflict_world**`(seed: Seed = Seed(0), *, rung: str, v1_target: float = 10.0, v2_target: float = 10.0, kA: Optional[Dist[float]] = None, kB: Optional[Dist[float]] = None, sim_cfg: SimConfig = _SIM_CFG) -> tuple[WorldImpl, Skeleton, Objective]`
    Sizes the supply `S` from the rung and the targets, builds the rung's skeleton, materializes it under `seed`, runs the forced gate on `forced`, then reads the target pool ids off the realized routes and returns the world, the materialized skeleton and an `OutcomeObjective`. Raises `ValueError` for an unknown rung and `SkeletonError` when the forced gate finds an allocation meeting both targets. `single` ignores `v2_target` and `kB`. The `sim_cfg` parameter is accepted and never read: the gate always simulates on `_SIM_CFG`. ^draft-conflict-world

**build_conflict_skeleton**`(*, source_rate: float, kA: Dist[float], kB: Dist[float]) -> Skeleton`
    `root` with children `source` (`SourceBlock`, `Constant(source_rate)`) and `crux` (`ConflictCruxBlock.make("crux", kA=kA, kB=kB)`), one binding `source.out` to `crux.precursor`; `crux="root/crux"`, `control_surface=("root/source.out",)`. Its `(kA, kB) -> Skeleton` shape is exactly the `build` callable `sweep_conflict_frontier` takes. ^build-conflict-skeleton

**closed_form_frontier**`(source_rate: float, n_points: int = 11) -> tuple[tuple[float, float], ...]`
    `n_points` evenly spaced points from `(0, S)` to `(S, 0)` on the line `a + b = S`. No simulation. Raises `ValueError` for `n_points < 2`. `tradeoff.conflict_oracle` is its caller (§ [The frontier](#the-frontier)). ^closed-form-frontier



## _SingleRouteCrux Interface
A private `ReactionBlock` subclass, the crux of the `single` rung: one `in -> out` route with no rival, given a `ground_truth` so `oracle` returns a tuple on every rung.

| _SingleRouteCrux | |
| --- | --- |
| [ground_truth](#^ground-truth) | `(out,)`, a 1-tuple |

**ground_truth**`(timeline: Timeline) -> tuple[float]`
    `final_amount` of its resolved `out` pool. Raises `SkeletonError` on an unrealized block. ^ground-truth




# ConflictGen Semantics

## The ladder
One knob, the source's supply rate `S`, places every two-route rung; `single` is a topology switch instead (one route, one sink, no crux):

| Rung | `S` | At the default split `kA = kB` |
| --- | --- | --- |
| `single` | `1.2 · v1_target` | One target, reached with margin (`out → S`) |
| `compatible` | `4.0 · (v1 + v2)` | Both targets met with room to spare |
| `latent` | `1.0 · (v1 + v2)` | Both targets met only at the boundary; any reallocation trades one for the other |
| `forced` | `0.4 · (v1 + v2)` | Neither can be met together, whatever the split |

The multipliers live in `_S_MULTIPLIER` and `_SINGLE_MARGIN`; `tradeoff.conflict_oracle` imports both to recompute the supply rather than reading it off the draft, so the oracle and the world agree only because they share those constants.

`latent` holds its promise only when the targets are equal: the balanced split gives each route `S/2 = (v1 + v2)/2`, which misses the larger target whenever `v1 ≠ v2`. And the boundary is reached from below: a simulated trial on the default 20 s horizon reads `9.99999998` against a goal of `10.0`, so the min-of-components score at the balanced split is `0.99999998`, not `1.0`.

Pool ids come from binding order, not from the generator: the two target pools are `root/crux/sink_a_in` and `root/crux/sink_b_in`, the precursor `root/crux_precursor`, and the single rung's target `root/sink_in` ([ABIO Skeleton](ABIO%20Skeleton.md) § Pool ids and binding). The generator reads them off `resolved_ports`; EXP-7's spec spells them literally in its `priority` axis.



## The frontier
Each route drains its product through a sink of rate 1, so at steady state the precursor's outflow `(kA + kB)·P` equals `S`, each product equals its route's inflow `k·P`, and `prodA + prodB = S` whatever the split. The achievable steady states are the segment `a + b = S, a, b ≥ 0`; `closed_form_frontier` samples it. The invariant depends on the crux's internal sinks being fixed at rate 1, which `ConflictCruxBlock.make` does not expose as a parameter. A simulated world approaches the line from below on a finite horizon; `Skeleton.oracle` on the defaults returns `(39.99999994, 39.99999994)` for `compatible` (`S = 80`).



## The forced gate
`_assert_forced_gate` is the generation-time canary: it sweeps five allocations of a fixed total rate 10 (`kA` fractions 0.01, 0.25, 0.5, 0.75, 0.99) through `sweep_conflict_frontier`, simulating the real assembled world for each under `seed.child("forced-gate")`, and raises `SkeletonError` if any reaches both targets. On this topology it cannot fire: every achieved sum is below `S`, and `S < v1 + v2`. It guards against a future change to the crux (a nonlinearity or extra path) opening an escape the closed form would not show. It ignores the caller's `kA`/`kB`, sweeps on `_SIM_CFG` (`dt 0.05`, 400 steps), and costs five extra materializations and simulations per `forced` draft.



## The objective
An `OutcomeObjective` whose scorer reads each target's final total and maps it through `_component_score`: `1.0` at or above the goal, `1 / (1 + deficit)` below it, so overshoot is free and the falloff is in absolute units. The pair scorer returns the `min` of the two components, a bottleneck: a joint win needs both. `target` is `(id, goal)` on `single` and `((v1_id, v1), (v2_id, v2))` on the other rungs. The `conflict` drafter takes `objective.target[0]` as the question's target, which on a two-route rung is the `(id, goal)` pair, not an id (`drafters.py:991`, `1001`). Neither shape is a string where `brief.task_readouts` looks for one, so on the two-route rungs the readout set is empty and the target pools stay on the default control surface: the agent may set `V1` and `V2` directly.



## Determinism
With the default `Constant` rates the seed changes nothing: no hole is sampled from it. A caller-supplied `Dist` for `kA` or `kB` is sampled from each route's own tree-position seed, so one seed draws one world. The forced gate's worlds take constant rates by construction.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `09b3509`. The supply table, pool ids, the latent `0.99999998` score, the `compatible` oracle point and the question-target shape were read from local drafts of all four rungs, no spend. Left out: the conflict summary and precedence ladder (`tradeoff.py`, on its own page when written), the drafter head's full task wrapping (`drafters.py`), and the test file `tests/suite/test_conflict_gen.py`.
