# Pathway puzzles — the suite-construction pipeline, end to end

*The suite-construction pipeline end to end: draft with distractors, carve a pattern, grade with partial credit, render and parse through an alien vocabulary, plan coverage, reject-sample.*

A neutral world and every stage of the M27 suite-construction pipeline on it, in the order the pipeline runs: a **host** drafted with distractor nodes around a hidden chain, every id opaque and dealt from the seed (`helpers.opaque_host`); a **pattern** — the four-role chain — **carved** into that host so every role binds to one of the host's own molecules; an **identify objective** whose key is read off the binding and whose grader awards longest-correct-prefix partial credit; an opaque **vocabulary** over the host's node ids with the question rendered through it and parsed back to the same structure; a **coverage plan** that packs puzzle features into containers under an admissibility rule; and **reject-sampling** (`!verify`) that redraws the host until throttling its first reaction visibly changes the trajectory. An experiment runs the puzzle over the chain length.

## Before and after the opaque host (T096)

Before, the host came from the `identify_pathway` drafter, which names the chain's molecules after its roles (`r0`, `r1`, …) and its reactions after their ends (`r0_r1`, …): the key was `['r0', 'r1', 'r2']` on every seed and spelled in the ids the agent sees, so committing it blind scored 1.000. Now `helpers.opaque_host` deals the chain and the distractors a seed-drawn permutation of `m1` … `mN` and the reactions one of `x1` …; the route is in the stoichiometry alone. Over seeds 200–259 at length 3 the key takes 52 distinct values (none more than twice), and the blind modal key is right on none of them. The shipped `survey_commit` zero runs out of turns before committing and scores 0.000 before and after (4 trials); no scripted solver.

## Run it

    bio suite run catalog/examples/pathway_puzzles/puzzles.yaml --dry
    bio suite run catalog/examples/pathway_puzzles/puzzles.yaml

From Python, the pieces:

    from alienbio.expr import Env
    v = Env.standard(seed=11, trusted=True).load("catalog/examples/pathway_puzzles/puzzles.yaml").force_all()
    v["puzzle"]["objective"].key.value # the ordered chain, four opaque host ids (['m5', 'm7', 'm6', 'm4'] at seed 11)
    v["prefix_credit"]                 # 1/3 — the first two of four nodes right (the given start earns none)
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
| reject-sampling on a validity predicate (M27.3, `verify` + `validity`) | `checked` |
| an experiment over a task-side dial | `puzzles` drafter, `pathway_length` axis |

Deliberately absent: every AI-safety dial (roadmap M48.9).

## Test

`tests/expr/test_pathway_puzzles_example.py`.
