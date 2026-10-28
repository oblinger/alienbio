---
description: "`render`: the FT08 template renderer — `render` writes a `Question` or `Answer` as fixed-template text over a `Vocabulary` (an injective token-to-phrase map), `parse` inverts it, and the pair is the round-trip guard `build_suite` runs on every task; verb framings for questions. Source: `src/alienbio/suite/render.py`."
---
:>> [ABIO](../../ABIO.md) → [ABIO Dev Docs](../ABIO%20Dev%20Docs.md) → [ABIO suite](ABIO%20suite.md) → [ABIO Render](ha://p/ABIO%20Render) 
# ABIO Render
A deterministic templater that turns a structured question or answer into one sentence over a controlled vocabulary, with an exact inverse used to prove the sentence carries the structure.

![ABIO Render](ABIO%20Render.svg) 
*Losslessness* is the topic behind the `parse(render(x)) == x` loop (‡: it holds for vocabularies `build_vocabulary` makes, not for every one the constructor accepts).

`suite/render.py` has no domain logic and no randomness: each `(answer?, kind)` has one prefix and suffix, questions may take a verb framing, and the payload's tokens are swapped for phrases. Its only run-path caller is `pipeline._assert_task_consistent` inside `build_suite`, which renders and parses each task's question and answer key and raises on a mismatch; the rendered text is then discarded, so no agent ever reads it (the agent's names come from [ABIO NameMap](ABIO%20NameMap.md) and the brief from [ABIO TaskBrief](ABIO%20TaskBrief.md)). The vocabulary comes from `vocab.build_vocabulary`; `Question` and `Answer` are [ABIO Types](ABIO%20Types.md)'s. `Vocabulary`, `render` and `parse` are re-exported from `alienbio.suite`. The design is [ABIO Suite Construction](../../ABIO%20Architecture/ABIO%20Suite%20Construction.md).



## Vocabulary Interface
A frozen dataclass: a token-to-phrase bijection, checked at construction.

| Vocabulary | |
| --- | --- |
| [phrases](#^phrases) | Token to surface phrase |
| [phrase_for](#^phrase-for) | A token's phrase |
| [token_for](#^token-for) | A phrase's token |

**phrases**`: Mapping[str, str]`
    `__post_init__` raises `ValueError` when two tokens share a phrase, a phrase contains `SEP`, or a phrase equals `EMPTY`; the inverse map is cached on the instance. ^phrases

**phrase_for**`(token: str) -> str`
    `KeyError` for a token not covered. ^phrase-for

**token_for**`(phrase: str) -> str`
    `ValueError` for a phrase not covered. ^token-for



## render Interface
Two constants and two functions.

| render | |
| --- | --- |
| [SEP](#^sep) | Separator between phrases |
| [EMPTY](#^empty) | Text of an empty set or path |
| [render](#^render) | Structure to one sentence |
| [parse](#^parse) | One sentence back to structure |

**SEP**` = " | "`
    Joins a `node_set` (sorted by phrase) or an `ordered_path`. ^sep

**EMPTY**` = "(none)"`
    The middle of an empty collection. ^empty

**render**`(node: Question | Answer, vocabulary: Vocabulary, *, verb: Optional[str] = None) -> str`
    `prefix + middle + suffix`. Answers use the statement templates (`"The node is …."`); questions use the `(verb, kind)` framing when one exists (`("identify", "ordered_path")` → `"Which pathway connects: …?"`) else the generic question. `scalar` and `json` payloads are embedded as canonical JSON with no vocabulary lookup. `ValueError` on an unsupported kind, `KeyError` on an uncovered token. ^render

**parse**`(text: str, vocabulary: Vocabulary, *, kind: str, as_answer: bool = False, verb: Optional[str] = None) -> Question | Answer`
    Checks the prefix and suffix, splits the middle on `SEP`, maps phrases back, and returns a `node_set` as a `set`, an `ordered_path` as a `list`, and JSON as parsed. `ValueError` on a template mismatch or an unknown phrase. ^parse




# Render Semantics

## Losslessness
Round-tripping holds when the payload's types are the ones `parse` returns and the phrases cannot be confused once joined. Measured counter-cases, none of which `build_vocabulary` produces: an `ordered_path` of `("p",)` as a tuple parses back as a list and compares unequal; a `scalar` NaN round-trips as NaN, which is unequal to itself; and phrases `{"x": "a |", "y": "b", "z": "a", "w": "| b"}` render the path `[x, y]` as `"a | | b"`, which parses as `[z, w]`, since the constructor checks that a phrase does not contain `" | "` but not that it does not start or end with half of it. Alien phrases are drawn from letters, `-`, `'` and `.`, so none of these arise on the run path.




# BRIEF
- 2026-10-28 — written as an ABIO module doc (T084), from the source at alienbio HEAD `64988be` and `pipeline._assert_task_consistent`; the three round-trip counter-cases confirmed on the HEAD export, no spend.
