---
description: "`validity`: M27.3's two world-validity gates — `non_obvious_causal` returns a verify predicate that passes when a perturbation moves the trajectory by more than an absolute L2 threshold, `is_shortcut_resistant` fails a world whose answer set equals a degree or two-hop top-k. Source: `src/alienbio/suite/validity.py`."
---
:>>
# ABIO Validity
Two predicates meant to reject worlds whose answer is readable without reasoning: one asks that a perturbation visibly move the trajectory, the other that no cheap centrality ranking reproduce the answer.

![ABIO Validity](ABIO%20Validity.svg) 
*What each gate measures* is the topic behind the two branches (‡: each tests less than its name; see the Semantics).

`suite/validity.py` is opaque machinery: `non_obvious_causal` fits the `verify_with=(perturbation, predicate)` seam of `pipeline.build_suite` and the Expr `verify` head ([ABIO Verify](ABIO%20Verify.md)), `is_shortcut_resistant` reads a chemistry's `neighbors` ([ABIO ChemistryImpl](../ABIO%20bio/ABIO%20ChemistryImpl.md)). Neither is called by a drafter or the default pipeline; the Pathway puzzles example's `non_obvious` function wraps `non_obvious_causal(min_deviation=1e-3)` (`catalog/examples/pathway_puzzles/helpers.py`), and `is_shortcut_resistant` has no caller outside `tests/suite/test_validity.py`. Both are re-exported from `alienbio.suite`. The design is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## validity Interface
Two gates; the heuristic battery is the private `_HEURISTICS = (_degree, _two_hop)`.

| validity | |
| --- | --- |
| [non_obvious_causal](#^non-obvious-causal) | Perturbation must move the trajectory |
| [is_shortcut_resistant](#^is-shortcut-resistant) | Answer must not be a centrality top-k |

**non_obvious_causal**`(min_deviation: float = 1e-3) -> Callable[[Timeline, Timeline], bool]`
    The returned predicate stacks each timeline into `[samples × compartments × species]` and passes when the shapes match, are non-empty, and the total L2 distance between them exceeds `min_deviation`. Unequal shapes (a perturbation that adds or removes a molecule) fail. ^non-obvious-causal

**is_shortcut_resistant**`(chemistry: ChemistryImpl, answer_nodes: Iterable[NodeId], top_k: int | None = None) -> bool`
    For each heuristic, ranks every molecule and reaction by score (descending, ties by id) and fails when the top `k` (default the answer's size) equals the answer set exactly. An empty answer passes. ^is-shortcut-resistant




# Validity Semantics

## What each gate measures
`non_obvious_causal` reads only how far the perturbed run lies from the baseline; it never examines the baseline for whether the structure is already visible there, which is half of what its docstring promises. The threshold is absolute over all samples and species, so on worlds at concentrations near 100 almost any perturbation passes.

`is_shortcut_resistant` rejects only an exact match. On a five-molecule world whose hub `h` has degree 3, the answer `{h}` was rejected while `{h, d}` passed, though the degree ranking's first pick is half of it. A heuristic that recovers all but one answer node leaves the world "resistant".




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be`; the partial-overlap pass confirmed on a hand-built hub world from the HEAD export, no spend. Consumer census: the Pathway puzzles helper and the tests; no drafter.
