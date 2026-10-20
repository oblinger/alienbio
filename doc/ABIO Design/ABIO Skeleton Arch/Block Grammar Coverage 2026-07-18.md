---
description: "Adversarial stress-test of the Skeleton block grammar against 20 concrete biological situations — what it encodes cleanly, what needs an idiom, and the ranked gaps that drive which blocks/engine-features to add before freezing the roster."
---
:>> [[ABIO]] → [[ABIO Design]] → [[ABIO Skeleton Arch]] → [Block Grammar Coverage 2026-07-18](ha://p/Block%20Grammar%20Coverage%202026-07-18) 
# Block Grammar Coverage — 20 biological situations (2026-07-18)
A stress-test of the reduced grammar (reaction-primitive over pool-ports + recursive patterns + conservation/boundedness invariants) against 20 real biological situations, to find missing blocks **before** freezing the roster. Legend: **✓** clean · **◑** encodable via idiom (verbose/indirect) · **✗** gap (not expressible even with the two pending engine features).

## Three structural bounds that everything turns on

1. **Mass-action rates are monotonically *increasing* in every reactant.** "More X → slower R" is impossible except by having X *sequester* something R needs. **Negative regulation is always an idiom, never a primitive** — and you **cannot inhibit a Source inflow** (nothing to sequester).
2. **A species cannot sit on both sides of one reaction** (the pending catalytic-modulation feature). A true non-consumed catalyst must be faked as `E+S⇌ES→E+P` — 3 reactions + 1 pool per enzyme.
3. **Topology, compartment count, and volume are static.** No pool-kind or compartment created/destroyed at runtime; volume never changes.

## The 20 situations

| # | Situation | Key piece(s) | Verdict | Gap |
|---|---|---|---|---|
| 1 | Glycolysis + PFK feedback | metabolite cascade + ATP; allosteric inhibition | ◑ | G1, G2 |
| 2 | Michaelis–Menten catalysis | saturating non-consumed enzyme | ◑ | G1 |
| 3 | Hemoglobin cooperative O₂ | sigmoidal/Hill, concerted allostery | ◑ | G7 |
| 4 | lac operon | repressor sequesters operator; inducer de-represses | ◑ | G1, G2 |
| 5 | MAPK cascade | catalytic tiers + ultrasensitivity | ◑/✗ | G1, G7 |
| 6 | Threonine→Ile feedback | end-product inhibits committed enzyme | ◑ | G1, G2 |
| 7 | Circadian / repressilator | negative feedback + delay + nonlinearity | ◑ | G2, G7, G9 |
| 8 | Na⁺/K⁺ ATPase | ATP-driven ion flux; electrogenic | ✗/◑ | G3, G4 |
| 9 | Action potential (HH) | voltage-gated channels; regenerative spike | ✗ | **G4** |
| 10 | Bicarbonate pH buffer | fast reversible protonation | ✓ | — |
| 11 | Glucose homeostasis | opposing routes on shared glucose pool + feedback | ✓/◑ | G2 |
| 12 | Osmotic/volume regulation | water flux; volume changes dilute solutes | ◑/✗ | G3, G6 |
| 13 | Chemotaxis perfect adaptation | integral (antithetic) feedback | ✓ | (sensing: G5) |
| 14 | Morphogen gradient / Turing | diffusion profile; reaction-diffusion | ◑ (painful) | G3, G5 |
| 15 | Cell-cycle bistable trigger | hysteresis switch; gates division | ◑/✗ | G7, G6 |
| 16 | Cell growth & division | dilution by growth; compartment fission | ✗ | **G6** |
| 17 | Immune clonal expansion | autocatalytic proliferation; new specificities | ✓/✗ | G8 |
| 18 | Clotting cascade | catalytic amplifying relay | ◑ | G1 |
| 19 | Viral / predator–prey | infection, lytic burst, clearance | ✓ | — |
| 20 | Electron transport + oxphos | redox chain; proton pumping; PMF drives ATP synthase | ✓/◑/✗ | G3, G4 |

## Gaps, ranked by breadth

| Gap | What | Breadth | Disposition |
|---|---|---|---|
| **G1** | Non-consumed catalytic rate modulation (activation) | ~12+ | The pending **S2** engine feature — highest breadth. Faked today via `E+S⇌ES→E+P`. **Ship first.** |
| **G2** | Inhibitory / negative rate modulation | ~8–10 | Genuinely new. Only expressible via sequestration idiom, which **can't inhibit a Source**. → make **S2 bidirectional** (activation *and* inhibition) + an `InhibitionBlock` pattern. |
| **G3** | Cross-compartment transport flux | ~6–7 | The pending **S3** engine feature. Prerequisite for G5. **Ship second.** |
| **G7** | Cooperativity / Hill / ultrasensitivity | ~5 | Convenience: a `CooperativeBindingBlock` (parameterized n) over existing reactions. |
| **G4** | Electrical / voltage state + voltage-dependent kinetics | ~4 | **Hard gap — new state *type*, not a pool.** Unlocks excitable cells / neuro / bioenergetics. **Owner scope call.** |
| **G5** | Spatial structure / diffusion | ~4 | Reducible to G3 + a `SpatialLatticeBlock` (stamp K compartments, wire neighbor transport). Blocked on G3. |
| **G6** | Structural/discrete events: division, variable volume, growth-dilution | ~4 | **Hard gap.** `GrowthBlock` (variable volume + dilution) tractable; true division = deep. **Owner scope call.** |
| **G9** | Explicit time delay | ~2 | Low priority; linear-chain distributed-delay idiom covers most. |
| **G8** | Combinatorial diversity (new species at runtime) | ~1–2 | Recommend **out of scope**. |
| **G10** | Mechanical / force variables | ~1 | **Out of scope.** |

## Bottom line

- **The core grammar is sound** — clean fits: viral/predator–prey (19), pH buffering (10), integral-feedback adaptation (13), glucose ConflictCrux (11). Gaps are all at the edges.
- **The two pending engine features (S2 catalytic modulation, S3 transport) are the two highest-breadth gaps by far — build both before adding blocks.** S2 alone underlies ~12/20.
- **Refine S2 to be bidirectional** (activation + inhibition) — that absorbs G2, the negative-feedback half of biology.
- **Add three idiom-wrapping pattern blocks:** `EnzymeBlock` (catalysis), `InhibitionBlock` (negative regulation), `CooperativeBindingBlock` (Hill). Each hides a verbose reaction idiom behind one block.
- **Two owner scope calls:** G4 (voltage/electrophysiology) and G6 (division/variable-volume) — each unlocks a whole biology domain but is a new state-type/structural-mutation, not an idiom.
