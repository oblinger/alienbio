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
Two public functions and seven constants; the crux block and the gate are private.

| delta_gen | |
| --- | --- |
| [DEFAULT_R_A](#^default-r-a) | `source_a`'s supply rate |
| [DEFAULT_R_B](#^default-r-b) | `source_b`'s supply rate |
| [DEFAULT_K_DRIVE](#^default-k-drive) | Rate of the driving edge into `T` |
| [DEFAULT_K_SINK](#^default-k-sink) | Rate of `source_a`'s own sink |
| [DEFAULT_K_SINK_B](#^default-k-sink-b) | Rate of `source_b`'s own sink |
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
    `sink_a`'s always-on drain on `source_a`, small so it barely touches the driver on `W_match`; on `W_mismatch` it is the decoy's only drain, so the decoy reads larger there throughout. ^default-k-sink

**DEFAULT_K_SINK_B**` = 1.0`
    `sink_b`'s drain on `source_b`: large enough that on `W_match` the decoy's steady level `r_b / k_sink_b` (1.0) sits below the driver's `r_a / (k_drive + k_sink)` (≈ 2.44), while on `W_mismatch` `T` still clears the floor (steady ≈ 0.67). ^default-k-sink-b

**DEFAULT_K_T_SINK**` = 1.0`
    `sink_t`'s rate. ^default-k-t-sink

**DEFAULT_T_TARGET**` = 0.5`
    The gate's floor: baseline `T` must reach it and a driver-cut `T` must not. ^default-t-target

**draft_delta_pair**`(seed: Seed = Seed(0), *, r_a: float = 5.0, r_b: float = 1.0, k_drive: Optional[Dist[float]] = None, k_sink: Optional[Dist[float]] = None, k_sink_b: Optional[Dist[float]] = None, k_t_sink: Optional[Dist[float]] = None, t_target: float = 0.5, sim_cfg: SimConfig = _SIM_CFG) -> tuple[tuple[WorldImpl, Skeleton, Objective], tuple[WorldImpl, Skeleton, Objective]]`
    Raises `ValueError` unless `r_a`, `r_b` and `t_target` are positive finite numbers and `r_a > r_b`. Drafts `invert=False` then `invert=True` under the same seed, each a `(world, materialized skeleton, AnswerObjective)` triple, runs `_assert_delta_gate` on both and returns `(match, mismatch)`. `r_a` and `r_b` are plain floats (wrapped as `Constant`); the four rates may be any `Dist`. Raises `SkeletonError` when the gate fails. ^draft-delta-pair

**build_delta_skeleton**`(*, invert: bool, r_a: Dist[float], r_b: Dist[float], k_drive: Dist[float], k_sink: Dist[float], k_sink_b: Dist[float], k_t_sink: Dist[float]) -> Skeleton`
    `root` with one child, `_DeltaCruxBlock.make("crux", …)`; `crux="root/crux"`, `control_surface=("root/crux/source_a.out", "root/crux/source_b.out")`. Both signals live inside the crux, so there is no top-level source. The gate rebuilds cut worlds with it. ^build-delta-skeleton



## _DeltaCruxBlock Interface
A private pattern block with six children and four bindings; only the fourth binding depends on `invert`, which is also stored in `params["invert"]` for `ground_truth` to read back.

| _DeltaCruxBlock | |
| --- | --- |
| [make](#^make) | Build the six-child crux |
| [ground_truth](#^ground-truth) | `(T, driver, decoy)` final amounts |

**make**`(name, *, invert: bool, container=None, r_a, r_b, k_drive, k_sink, k_sink_b, k_t_sink, params=None) -> _DeltaCruxBlock` (classmethod)
    Children `source_a`, `source_b` (`SourceBlock`), `sink_a` (`SinkBlock`, `k_sink`), `sink_b` (`SinkBlock`, `k_sink_b`), `route_drive` (`ReactionBlock`, `in -> out` at `k_drive`), `sink_t` (`SinkBlock`, `k_t_sink`). Bindings, sink side first: `sink_a.in`–`source_a.out`, `sink_b.in`–`source_b.out`, `sink_t.in`–`route_drive.out`, and `route_drive.in`–`source_b.out` when `invert` else `source_a.out`. ^make

**ground_truth**`(timeline: Timeline) -> tuple[float, float, float]`
    `final_amount` of `T` (`route_drive`'s `out`), of the true driver's pool and of the decoy's, choosing driver and decoy by `params["invert"]`. Raises `SkeletonError` on an unrealized block. ^ground-truth




# DeltaGen Semantics

## The flipped edge
Both worlds are built from the same tree (same names, child order and rates) under the same seed, so every reaction id, molecule id and rate is identical; only the reactant of `root/crux/route_drive/rxn` differs. The ids are held stable by binding order: each fixed binding names the sink first and the source second, so the union-find representative of each signal's pool is the source's own port and the pool is minted `root/crux/source_a_out` / `root/crux/source_b_out`; the flippable binding then joins `route_drive.in` to an already-rooted group without renaming it. `T` is `root/crux/route_drive_out`. `tests/suite/test_delta_gen.py::test_pair_differs_by_exactly_one_edge` walks both chemistries to hold this.

`W_match` wires the larger-supply signal `source_a` to `T`, so the rule "the bigger signal drives it" answers right; `W_mismatch` wires `source_b`, and the same rule answers wrong.



## Bigger by supply, and by level
The conventional rule is defined on supply rates, which the agent never sees; what it observes are pool levels. Since `719261e` (T088 Q4 = A) the two signals drain at their own rates: on `W_match` the driver drains at `k_drive + k_sink = 2.05` and the decoy at `k_sink_b = 1.0`; on `W_mismatch` the driver `source_b` drains at `k_drive + k_sink_b = 3.0` and the decoy `source_a` at `k_sink = 0.05` alone. On the defaults (`Skeleton.oracle`, 20 s):

| Arm | Driver level | Decoy level | `T` |
| --- | --- | --- | --- |
| `match` | `source_a` 2.44 | `source_b` 1.0 | 4.88 |
| `mismatch` | `source_b` 0.33 | `source_a` 63.30 | 0.67 |

Both pools start empty and each level is `r/λ · (1 − e^{−λt})`, so the steady-state order is the order at every `t > 0`: on `W_match` the larger supply is the larger level throughout, on `W_mismatch` the decoy reads larger throughout. A "largest observed level" rule, the scripted `heuristic-commit` agent's, is right on `W_match` and wrong on `W_mismatch` whenever it reads. The gate checks both orders (§ [The gate](#the-gate)).



## The objective
A diagnosis task: `AnswerObjective(grader=GraderSpec(kind="node_id"), key=Answer(value=driver_id, kind="node_id"))`, the key read off the realized driver block's `resolved_ports`, never inferred from the chemistry. The `delta` drafter's question is `tuple(sorted([a_id, b_id]))` (`drafters.py` ~1152), so the candidates' order in the prompt is fixed whatever the process's hash seed (it was a set, whose order followed `PYTHONHASHSEED`, until `c2bfa3c`).



## The gate
`_assert_delta_gate` runs on every draft, before return. It raises `SkeletonError` unless:

| Check | Simulation |
| --- | --- |
| The two keys differ | None |
| Level order: on `W_match` driver > decoy, on `W_mismatch` decoy > driver, at the closed-form steady state and at every sample after `t = 0` (`_assert_level_order`) | A dense simulation of the drafted world (`sample_every=1`) |
| Baseline `T ≥ t_target` in each world | The same dense simulation's final `T` |
| Driver cut to 0: `T < t_target` | A rebuilt skeleton with the driver's supply `Constant(0)` |
| Decoy cut to 0: `T` within `1e-3` of baseline | A rebuilt skeleton with the decoy's supply `Constant(0)` |

That is two dense simulations of the drafted worlds and four cut-world `oracle` calls per pair, each a 400-step simulation on `_SIM_CFG` unless `sim_cfg` is given. The baseline simulates the drafted world itself rather than calling `oracle` on its skeleton, so the skeletons are not re-materialized and the chemistry and tree cached on them stay the returned worlds' (since `719261e`). Every cut world is rebuilt with the caller's `k_*` rates, so a `Dist` there is re-sampled at the same tree positions and draws the same values.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `66ccd69`. The level table and the crossing time were read from local drafts and `oracle` calls on the defaults; the set-order result from three `DRAFTERS["delta"]` calls under different `PYTHONHASHSEED`s, no spend. Left out: the paired summary (`suite/delta.py`, its own page when written), the `heuristic-commit` agent's code (`agents.py`), and EXP-8's spec beyond its use of the pair.
- 2026-10-28 — refreshed against 0eb23e5 (`719261e`, `c2bfa3c`): `k_sink_b`/`DEFAULT_K_SINK_B` added, so the driver reads larger on `W_match` at every time (level table recomputed, section renamed); the gate checks the level order on a dense simulation of the drafted worlds; rates validated; the question is a sorted tuple; figure labels follow.
