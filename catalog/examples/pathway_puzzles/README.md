# Pathway puzzles — the suite-construction pipeline, end to end

A neutral world and every stage of the M27 suite-construction pipeline on it, in the order the pipeline runs: a **host** drafted with distractor nodes around a hidden chain (`identify_pathway`, `suite.augment`); a **pattern** — the four-role chain — **carved** into that host so every role binds to one of the host's own molecules; an **identify objective** whose key is read off the binding and whose grader awards longest-correct-prefix partial credit; an opaque **vocabulary** over the host's node ids with the question rendered through it and parsed back to the same structure; a **coverage plan** that packs puzzle features into containers under an admissibility rule; and **reject-sampling** (`!verify`) that redraws the host until throttling its first reaction visibly changes the trajectory. An experiment runs the puzzle over the chain length.

## Run it

    bio suite run catalog/examples/pathway_puzzles/puzzles.yaml --dry
    bio suite run catalog/examples/pathway_puzzles/puzzles.yaml

From Python, the pieces:

    from alienbio.expr import Env
    v = Env.standard(seed=11, trusted=True).load("catalog/examples/pathway_puzzles/puzzles.yaml").force_all()
    v["puzzle"].objective.key.value    # the ordered chain, four host molecule ids
    v["half_credit"]                   # 0.5 — the first two nodes right
    v["question_text"]                 # the endpoints, in alien phrases
    v["plan"].containers               # the coverage plan

## What it covers

| Capability dimension | Where |
|---|---|
| a generative host with distractors (B-generation, `augment`) | `draft`, `host` |
| pattern + carve on a drafted host (M27.1, `carve`) | `chain`, `carved` |
| an identify objective with partial-credit grading (`grade`) | `puzzle`, `full_credit` / `half_credit` / `no_credit` |
| the fixed-vocabulary render / parse round trip (M27.2, `render`) | `vocab`, `question_text`, `question_back` |
| coverage planning under an admissibility rule (`cover`) | `plan` |
| reject-sampling on a validity predicate (M27.3, `verify` + `validity`) | `checked` |
| an experiment over a task-side dial | `puzzles` drafter, `pathway_length` axis |

Deliberately absent: every AI-safety dial (roadmap M48.9).

## Test

`tests/expr/test_pathway_puzzles_example.py`.
