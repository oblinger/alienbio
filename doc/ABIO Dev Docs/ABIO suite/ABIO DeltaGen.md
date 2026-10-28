---
description: "`delta_gen`: the M31.3 Delta generator — a matched pair of worlds built off one template, `W_match` where the larger-supply signal drives `T` and `W_mismatch` where one edge is rewired onto the smaller signal, the six-child `_DeltaCruxBlock`, the node-id answer objective, and the simulate-both acceptance gate. Source: `src/alienbio/suite/delta_gen.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO DeltaGen](ha://p/ABIO%20DeltaGen) 
# ABIO DeltaGen
The generator of EXP-8's matched pair: two worlds identical in every id and rate except the one edge saying which of two signals drives `T`, checked by simulation to be solvable and to differ.

![ABIO DeltaGen](ABIO%20DeltaGen.svg) 
*The flipped edge* is the topic behind the dashed green and orange bindings (one per world, the only difference between them); *The gate* governs the cut worlds on the right, rebuilt once per world.

`suite/delta_gen.py` composes library blocks only (`SourceBlock`, `SinkBlock`, `ReactionBlock`, on [ABIO Blocks](ABIO%20Blocks.md)); the tree and `oracle` are [ABIO Skeleton](ABIO%20Skeleton.md). The drafter head `delta` in `drafters.py` picks one side by its `arm` dial (`match` or `mismatch`) and asks *which of the two signals drives T?*; `suite/delta.py` pairs the twin records into the Delta report section; the Expr head `delta_pair` returns both sides. `draft_delta_pair` is not re-exported from `alienbio.suite`. Its siblings in shape are [ABIO ConflictGen](ABIO%20ConflictGen.md) and [ABIO PressureGen](ABIO%20PressureGen.md).



## delta_gen Interface
Two public functions and six constants; the crux block and the gate are private.

| delta_gen | |
| --- | --- |
| [DEFAULT_R_A](#^default-r-a) | `source_a`'s supply rate |
| [DEFAULT_R_B](#^default-r-b) | `source_b`'s supply rate |
| [DEFAULT_K_DRIVE](#^default-k-drive) | Rate of the driving edge into `T` |
| [DEFAULT_K_SINK](#^default-k-sink) | Rate of each signal's own sink |
| [DEFAULT_K_T_SINK](#^default-k-t-sink) | Rate draining `T` |
| [DEFAULT_T_TARGET](#^default-t-target) | The floor `T` must clear at baseline |
| [draft_delta_pair](#^draft-delta-pair) | Draft `(W_match, W_mismatch)` and gate it |
| [build_delta_skeleton](#^build-delta-skeleton) | One side's skeleton, unmaterialized |

**DEFAULT_R_A**` = 5.0`
    The conventionally implicated signal's supply; `draft_delta_pair` requires `r_a > r_b`. ^default-r-a

**DEFAULT_R_B**` = 1.0`
    The decoy-looking signal's supply. ^default-r-b

**DEFAULT_K_DRIVE**` = 2.0`
    `route_drive`'s rate, `driver -> T`. ^default-k-drive

**DEFAULT_K_SINK**` = 0.05`
    Each signal's own always-on drain, small so it barely touches the driver; it is what gives the undriven signal a bounded fate. ^default-k-sink

**DEFAULT_K_T_SINK**` = 1.0`
    `sink_t`'s rate. ^default-k-t-sink

**DEFAULT_T_TARGET**` = 0.5`
    The gate's floor: baseline `T` must reach it and a driver-cut `T` must not. ^default-t-target

**draft_delta_pair**`(seed: Seed = Seed(0), *, r_a: float = 5.0, r_b: float = 1.0, k_drive: Optional[Dist[float]] = None, k_sink: Optional[Dist[float]] = None, k_t_sink: Optional[Dist[float]] = None, t_target: float = 0.5, sim_cfg: SimConfig = _SIM_CFG) -> tuple[tuple[WorldImpl, Skeleton, Objective], tuple[WorldImpl, Skeleton, Objective]]`
    Raises `ValueError` unless `r_a > r_b`. Drafts `invert=False` then `invert=True` under the same seed, each a `(world, materialized skeleton, AnswerObjective)` triple, runs `_assert_delta_gate` on both and returns `(match, mismatch)`. `r_a` and `r_b` are plain floats (wrapped as `Constant`); the three rates may be any `Dist`. Raises `SkeletonError` when the gate fails. ^draft-delta-pair

**build_delta_skeleton**`(*, invert: bool, r_a: Dist[float], r_b: Dist[float], k_drive: Dist[float], k_sink: Dist[float], k_t_sink: Dist[float]) -> Skeleton`
    `root` with one child, `_DeltaCruxBlock.make("crux", …)`; `crux="root/crux"`, `control_surface=("root/crux/source_a.out", "root/crux/source_b.out")`. Both signals live inside the crux, so there is no top-level source. The gate rebuilds cut worlds with it. ^build-delta-skeleton



## _DeltaCruxBlock Interface
A private pattern block with six children and four bindings; only the fourth binding depends on `invert`, which is also stored in `params["invert"]` for `ground_truth` to read back.

| _DeltaCruxBlock | |
| --- | --- |
| [make](#^make) | Build the six-child crux |
| [ground_truth](#^ground-truth) | `(T, driver, decoy)` final amounts |

**make**`(name, *, invert: bool, container=None, r_a, r_b, k_drive, k_sink, k_t_sink, params=None) -> _DeltaCruxBlock` (classmethod)
    Children `source_a`, `source_b` (`SourceBlock`), `sink_a`, `sink_b` (`SinkBlock`, `k_sink`), `route_drive` (`ReactionBlock`, `in -> out` at `k_drive`), `sink_t` (`SinkBlock`, `k_t_sink`). Bindings, sink side first: `sink_a.in`–`source_a.out`, `sink_b.in`–`source_b.out`, `sink_t.in`–`route_drive.out`, and `route_drive.in`–`source_b.out` when `invert` else `source_a.out`. ^make

**ground_truth**`(timeline: Timeline) -> tuple[float, float, float]`
    `final_amount` of `T` (`route_drive`'s `out`), of the true driver's pool and of the decoy's, choosing driver and decoy by `params["invert"]`. Raises `SkeletonError` on an unrealized block. ^ground-truth




# DeltaGen Semantics

## The flipped edge
Both worlds are built from the same tree (same names, child order and rates) under the same seed, so every reaction id, molecule id and rate is identical; only the reactant of `root/crux/route_drive/rxn` differs. The ids are held stable by binding order: each fixed binding names the sink first and the source second, so the union-find representative of each signal's pool is the source's own port and the pool is minted `root/crux/source_a_out` / `root/crux/source_b_out`; the flippable binding then joins `route_drive.in` to an already-rooted group without renaming it. `T` is `root/crux/route_drive_out`. `tests/suite/test_delta_gen.py::test_pair_differs_by_exactly_one_edge` walks both chemistries to hold this.

`W_match` wires the larger-supply signal `source_a` to `T`, so the rule "the bigger signal drives it" answers right; `W_mismatch` wires `source_b`, and the same rule answers wrong.



## Bigger by supply, not by level
The conventional rule is defined on supply rates, which the agent never sees. What it observes are pool levels, and the always-on drain makes the undriven signal accumulate: the driver drains at `k_drive + k_sink = 2.05`, the decoy only at `0.05`. On the defaults (`Skeleton.oracle`, 20 s):

| Arm | Driver level | Decoy level | `T` |
| --- | --- | --- | --- |
| `match` | `source_a` 2.44 | `source_b` 12.66 | 4.88 |
| `mismatch` | `source_b` 0.49 | `source_a` 63.30 | 0.98 |

So at the end of the horizon the decoy is the larger reading in both worlds. In `W_match` the levels cross at about 2.6 s (`source_a` rises fast to 2.44, `source_b` climbs about 1 per second), and only a reading taken before the crossing makes the larger level point at the driver. The scripted `heuristic-commit` agent commits the largest value it observed, so its "right on `W_match`" holds for an early read; a model reasoning from levels late in an episode sees the decoy as the bigger signal on both arms.



## The objective
A diagnosis task: `AnswerObjective(grader=GraderSpec(kind="node_id"), key=Answer(value=driver_id, kind="node_id"))`, the key read off the realized driver block's `resolved_ports`, never inferred from the chemistry. The `delta` drafter's question is the Python set `{a_id, b_id}` (`drafters.py:1151`); `render_brief` serializes it with `json.dumps(…, default=repr)`, so the candidates' order in the prompt follows the process's string hash seed (`PYTHONHASHSEED` 1 and 3 give opposite orders).



## The gate
`_assert_delta_gate` runs on every draft, before return. It raises `SkeletonError` unless:

| Check | Simulation |
| --- | --- |
| The two keys differ | None |
| Baseline `T ≥ t_target` in each world | `oracle` on the drafted skeleton |
| Driver cut to 0: `T < t_target` | A rebuilt skeleton with the driver's supply `Constant(0)` |
| Decoy cut to 0: `T` within `1e-3` of baseline | A rebuilt skeleton with the decoy's supply `Constant(0)` |

That is six `oracle` calls per pair, each a materialize and a 400-step simulation on `_SIM_CFG` unless `sim_cfg` is given. The baseline check calls `oracle` on the drafted skeleton itself, which re-materializes it and replaces its cached root and chemistry ([ABIO Skeleton](ABIO%20Skeleton.md) § The oracle); the returned world is the first materialization, equal but not the same object. Every cut world is rebuilt with the caller's `k_*` rates, so a `Dist` there is re-sampled at the same tree positions and draws the same values.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `66ccd69`. The level table and the crossing time were read from local drafts and `oracle` calls on the defaults; the set-order result from three `DRAFTERS["delta"]` calls under different `PYTHONHASHSEED`s, no spend. Left out: the paired summary (`suite/delta.py`, its own page when written), the `heuristic-commit` agent's code (`agents.py`), and EXP-8's spec beyond its use of the pair.
