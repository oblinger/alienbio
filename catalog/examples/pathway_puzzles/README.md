# Pathway puzzles — the suite-construction pipeline, end to end

*The suite-construction pipeline end to end: draft with distractors, carve a pattern, grade with partial credit, render and parse through an alien vocabulary, plan coverage, gate the host on a validity predicate.*

A neutral world and every stage of the M27 suite-construction pipeline on it, in the order the pipeline runs: a **host** drafted with distractor nodes around a hidden chain, every id opaque and dealt from the seed (`helpers.opaque_host`); a **pattern** — the four-role chain — **carved** into that host so every role binds to one of the host's own molecules; an **identify objective** whose key is read off the binding and whose grader awards longest-correct-prefix partial credit; an opaque **vocabulary** over the host's node ids with the question rendered through it and parsed back to the same structure; a **coverage plan** that packs puzzle features into containers under an admissibility rule; and a **validity gate** (`!verify`) over that same host: throttling its first reaction must move the 3 s trajectory by more than `MIN_KNOCKOUT_DEVIATION` (5.0, L2 over every sample), and the drafter delivers the gated host, so one that fails is refused, never run. The gate checks that a knockout shows, not that the chain is hidden in the baseline. An experiment runs the puzzle over the chain length.

## Before and after the opaque host (T096)

Before, the host came from the `identify_pathway` drafter, which names the chain's molecules after its roles (`r0`, `r1`, …) and its reactions after their ends (`r0_r1`, …): the key was `['r0', 'r1', 'r2']` on every seed and spelled in the ids the agent sees, so committing it blind scored 1.000. Now `helpers.opaque_host` deals the chain and the distractors a seed-drawn permutation of `m1` … `mN` and the reactions one of `x1` …; the route is in the stoichiometry alone. Over seeds 200–259 at length 3 the key takes 52 distinct values (none more than twice), and the blind modal key is right on none of them. The shipped `survey_commit` zero runs out of turns before committing and scores 0.000 before and after (4 trials); no scripted solver.

## Grading and the gate (T091 AF10, AF11)

The grader credits the interior only. It used to credit the end node the question states, so appending it doubled a three-node answer's score; at seed 11 (length 4) the first-two-nodes answer moved from 1/3 to 1/2, the full chain stays 1.0, the echoed endpoints and the empty answer stay 0. The gate's floor was 1e-3, which no host of this family could fail (minimum deviation 10.6 over 30 seeds); at 5.0, over seeds 0–59, it refuses no host at length 3 or 4, 7 at length 5 and 18 at length 6 — those whose throttled step sits too late and too slow for a knockout to show inside the horizon. The experiment's four trials (lengths 3 and 5) all pass it.

## Run it

    bio suite run catalog/examples/pathway_puzzles/puzzles.yaml --dry
    bio suite run catalog/examples/pathway_puzzles/puzzles.yaml

From Python, the pieces:

    from alienbio.expr import Env
    v = Env.standard(seed=11, trusted=True).load("catalog/examples/pathway_puzzles/puzzles.yaml").force_all()
    v["puzzle"]["objective"].key.value # the ordered chain, four opaque host ids (['m5', 'm7', 'm6', 'm4'] at seed 11)
    v["prefix_credit"]                 # 1/2 — the first two of four nodes right (neither given endpoint earns any)
    v["question_text"]                 # the endpoints, in alien phrases
    v["plan"].containers               # the coverage plan

## What it covers

| Capability dimension | Where |
|---|---|
| a generative host with distractors under opaque per-seed ids (B-generation) | `host` (`helpers.opaque_host`) |
| pattern + carve on a drafted host (M27.1, `carve`) | `chain`, `carved` |
| an identify objective with partial-credit grading (`grade`) | `puzzle`, `full_credit` / `prefix_credit` / `echo_credit` / `no_credit` |
| the fixed-vocabulary render / parse round trip (M27.2, `render`) | `vocab`, `question_text`, `question_back` |
| coverage planning under an admissibility rule (`cover`) | `plan` |
| a validity predicate gating the delivered host (M27.3, `verify` + `validity`) | `checked` |
| an experiment over a task-side dial | `puzzles` drafter, `pathway_length` axis |

Deliberately absent: every AI-safety dial (roadmap M48.9).

## Test

`tests/expr/test_pathway_puzzles_example.py`.
